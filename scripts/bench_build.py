"""Fetch and build the benchmark apps, each at the commit F-Droid built.

    python scripts/bench_build.py                 # every app in bench/apps.tsv
    python scripts/bench_build.py <app-id> ...    # just these

Each app is cloned into its own repository under $GREMLIN_PROJECTS_ROOT/bench
(Tier 2 commits and reverts against the repo enclosing the app, so apps cannot
share one), checked out at the commit its F-Droid recipe names, and built as a
debug APK. Results are appended to bench/build-results.tsv.

A plain `flutter build` failed for most apps, for reasons their F-Droid recipes
already handle and this script repeats:

- **Pinned Flutter.** A recipe says `flutter@stable` and then checks out the
  exact version the app pins in pubspec.yaml (`environment: flutter: "3.32.0"`).
  That version is installed beside the default one through mise.
- **Generated code.** Apps using build_runner do not commit its output, so the
  build fails on missing `*.g.dart` / `*.store.dart` until it runs — in every
  package of the repo that uses it, not only the app.
- **Submodules over SSH.** Some repos carry packaging submodules on ssh:// URLs
  that an anonymous clone cannot fetch. Only non-SSH submodules are initialised.
- **Flavors.** An app with product flavors needs `--flavor`; `fdroid` is
  preferred when it exists, since that is the build F-Droid ships.

- **Gradle heap.** Some apps cap the Gradle daemon at 1.5 GB, which runs out of
  heap transforming Flutter's engine jars; recipes raise it with `sed`. Editing
  the app would leave its tree dirty, which Tier 2 refuses, so set it once in
  ~/.gradle/gradle.properties instead, which overrides every project's value:
  `org.gradle.jvmargs=-Xmx4g -XX:MaxMetaspaceSize=1g`.

What it deliberately does not repeat: recipe steps that need root (apt
installs), which this project never runs. Apps needing them are dropped from
the list rather than worked around.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
APPS = REPO / "bench" / "apps.tsv"
RESULTS = REPO / "bench" / "build-results.tsv"
ROOT = Path(os.environ.get("GREMLIN_PROJECTS_ROOT", Path.home() / "Projects")) / "bench"


def sh(cmd: list[str] | str, cwd: Path, log, timeout: int = 1800) -> int:
    log.write(f"\n$ {cmd if isinstance(cmd, str) else ' '.join(cmd)}\n")
    log.flush()
    try:
        return subprocess.run(cmd, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                              shell=isinstance(cmd, str), timeout=timeout).returncode
    except subprocess.TimeoutExpired:
        log.write("TIMEOUT\n")
        return 124


def pinned_flutter(app: Path) -> str | None:
    """The exact Flutter version pubspec.yaml pins, if it pins one."""
    m = re.search(r"^environment:\s*\n((?:[ \t]+.*\n?)+)", (app / "pubspec.yaml").read_text(), re.M)
    if not m:
        return None
    v = re.search(r"^\s+flutter:\s*['\"]?([0-9][0-9.]*)['\"]?\s*$", m[1], re.M)
    return v[1] if v else None


def fvm_flutter(repo: Path) -> str | None:
    """A Flutter version pinned for fvm in .fvmrc (Sossoldi's recipe reads it)."""
    for f in (repo / ".fvmrc", repo / ".fvm" / "fvm_config.json"):
        if f.exists():
            m = re.search(r'"(?:flutter|flutterSdkVersion)"\s*:\s*"([0-9][0-9.]*)"', f.read_text())
            if m:
                return m[1]
    return None


def ci_flutter(repo: Path) -> str | None:
    """A Flutter version pinned in CI (`flutter-version: "3.22.2"`), which is
    where some apps pin it instead of pubspec.yaml; Chrono's recipe reads it."""
    for wf in (repo / ".github" / "workflows").glob("*.y*ml"):
        m = re.search(r"flutter[-_]version:\s*['\"]?([0-9]+\.[0-9]+\.[0-9]+)", wf.read_text())
        if m:
            return m[1]
    return None


_RELEASES = "https://storage.googleapis.com/flutter_infra_release/releases/releases_linux.json"


def dated_flutter(repo: Path) -> str | None:
    """The stable Flutter that was current at the checked-out commit.

    What F-Droid's `flutter@stable` meant when it built the app; today's stable
    is too new for most of them (Gradle minimums, removed APIs). An installed
    release from the same minor line is reused rather than downloading another
    1.5 GB SDK, since patch releases do not change what builds.
    """
    import json
    import urllib.request
    date = subprocess.run(["git", "log", "-1", "--format=%cs", "HEAD"], cwd=repo,
                          capture_output=True, text=True).stdout.strip()
    try:
        with urllib.request.urlopen(_RELEASES, timeout=30) as r:
            releases = json.load(r)["releases"]
    except (OSError, ValueError):
        return None
    stable = sorted((x["release_date"][:10], x["version"]) for x in releases
                    if x["channel"] == "stable" and x["release_date"][:10] <= date)
    if not stable:
        return None
    want = stable[-1][1]
    installed = subprocess.run(["mise", "ls", "--installed", "flutter"], capture_output=True,
                               text=True).stdout.split()
    minor = ".".join(want.split(".")[:2]) + "."
    same = sorted((v for v in installed if v.startswith(minor)),
                  key=lambda v: [int(n) for n in v.split(".")])
    return same[-1] if same else want


def _wrapper_dir(url: str) -> str:
    """Gradle's own folder name for a distribution: base-36 MD5 of its URL."""
    h, out = int(hashlib.md5(url.encode()).hexdigest(), 16), ""
    while h:
        h, r = divmod(h, 36)
        out = "0123456789abcdefghijklmnopqrstuvwxyz"[r] + out
    return out


def prefetch_gradle(app: Path, log) -> bool:
    """Put the wrapper's Gradle distribution where it will look for it.

    The wrapper's own download never gives up on a stalled connection: one
    sat 38 minutes on 26 KB. curl resumes, gives up on a stall and retries,
    and the result is checked against Gradle's published SHA-256.
    """
    props = app / "android" / "gradle" / "wrapper" / "gradle-wrapper.properties"
    if not props.exists():
        return True
    m = re.search(r"^distributionUrl=(.*)$", props.read_text(), re.M)
    if not m:
        return True
    url = m[1].strip().replace("\\:", ":")
    name = url.rsplit("/", 1)[1]
    home = Path(os.environ.get("GRADLE_USER_HOME", Path.home() / ".gradle"))
    dest = home / "wrapper" / "dists" / name[:-4] / _wrapper_dir(url)
    if (dest / name).exists() or (dest / f"{name}.ok").exists():
        return True
    dest.mkdir(parents=True, exist_ok=True)
    part = dest / f"{name}.dl"
    for _ in range(5):
        if not sh(["curl", "-sSL", "-C", "-", "--speed-limit", "20000", "--speed-time", "30",
                   "-o", str(part), url], dest, log, timeout=1800):
            break
    want = subprocess.run(["curl", "-sSL", url + ".sha256"], capture_output=True, text=True).stdout.strip()
    got = hashlib.sha256(part.read_bytes()).hexdigest() if part.exists() else ""
    if not want or want != got:
        log.write(f"gradle checksum mismatch: want {want!r} got {got!r}\n")
        part.unlink(missing_ok=True)
        return False
    part.rename(dest / name)
    return True


def stub_signing(app: Path, log) -> None:
    """Write a dummy key.properties when the build script requires one.

    Some apps read signing values with `as String` while configuring, which
    fails even for a debug build when the file is absent. F-Droid's recipe for
    Cuppa deletes the line; a stub is used here instead because the file is
    git-ignored, so the app's tracked tree stays clean for Tier 2.
    """
    props = app / "android" / "key.properties"
    gradle = [p for p in (app / "android" / "app").glob("build.gradle*")]
    if props.exists() or not any("key.properties" in p.read_text() for p in gradle):
        return
    ignored = subprocess.run(["git", "check-ignore", "-q", str(props)], cwd=app).returncode == 0
    if ignored:
        props.write_text("storePassword=gremlin\nkeyPassword=gremlin\nkeyAlias=gremlin\n")
        log.write("wrote stub android/key.properties (git-ignored)\n")


def java_for(app: Path) -> str | None:
    """A newer JDK when the app compiles for one.

    EverydayTasks sets Java 21 source/target; built on JDK 17, Kotlin targets 17
    and Gradle refuses the mismatch. The default JDK (17) is kept otherwise.
    """
    wanted = []
    for f in (app / "android" / "app").glob("build.gradle*"):
        t = f.read_text()
        wanted += [int(n) for n in re.findall(r"JavaVersion\.VERSION_(\d+)\b", t)]
        wanted += [int(n) for n in re.findall(r"jvmToolchain\(\s*(\d+)\s*\)", t)]
    top = max(wanted, default=0)
    return f"java@temurin-{top}" if top > 17 else None


def flavor(app: Path) -> str | None:
    for name in ("build.gradle.kts", "build.gradle"):
        f = app / "android" / "app" / name
        if f.exists():
            text = f.read_text()
            if "productFlavors" not in text:
                return None
            block = text.split("productFlavors", 1)[1]
            names = re.findall(r'(?:create\(\s*"(\w+)"\s*\)|^\s+(\w+)\s*\{)', block, re.M)
            names = [a or b for a, b in names if (a or b) not in ("dimension",)]
            return "fdroid" if "fdroid" in names else (names[0] if names else None)
    return None


def build(app_id: str, url: str, commit: str, subdir: str, flutter: str, args: str,
          prep: str, log) -> tuple[str, str]:
    repo = ROOT / app_id
    if not (repo / ".git").exists():
        # One retry: on a flaky connection the first attempt can fail on DNS alone.
        clone = ["git", "clone", "-q", "--filter=blob:none", url, str(repo)]
        if sh(clone, ROOT, log) and (time.sleep(10) or sh(clone, ROOT, log)):
            return "CLONE-FAIL", ""
    if sh(["git", "checkout", "-q", "-f", commit], repo, log):
        return "CHECKOUT-FAIL", ""
    # Submodules: GitHub ones listed by SSH address are fetched over HTTPS
    # (EverydayTasks keeps its own widget forks that way); other SSH hosts are
    # packaging (WHPH's AUR repo) and are skipped.
    https = ["-c", "url.https://github.com/.insteadOf=git@github.com:",
             "-c", "url.https://github.com/.insteadOf=ssh://git@github.com/"]
    subs = subprocess.run(["git", "config", "-f", ".gitmodules", "--get-regexp", r"submodule\..*\.url"],
                          cwd=repo, capture_output=True, text=True).stdout.splitlines()
    for line in subs:
        key, sub_url = line.split(None, 1)
        if "github.com" in sub_url or not sub_url.startswith(("ssh://", "git@")):
            path = subprocess.run(["git", "config", "-f", ".gitmodules", key.replace(".url", ".path")],
                                  cwd=repo, capture_output=True, text=True).stdout.strip()
            sh(["git", *https, "submodule", "update", "--init", "--recursive", path], repo, log)

    app = repo / (subdir if subdir not in ("", ".") else "")
    # The version F-Droid would use: an override from apps.tsv (for apps built
    # on "stable" at the time, which is today something else), the app's own
    # pin, or its CI's.
    version = ((flutter if flutter not in ("", "-") else None) or pinned_flutter(app)
               or fvm_flutter(repo) or ci_flutter(repo) or dated_flutter(repo))
    tool = f"flutter@{version}" if version else "flutter"
    # An hour: each Flutter SDK is ~1.5 GB, and a slow link took 30 min for half.
    if version and sh(["mise", "install", tool], app, log, timeout=3600):
        return "FLUTTER-INSTALL-FAIL", version
    java = java_for(app)
    if java and sh(["mise", "install", java], app, log, timeout=1800):
        return "JAVA-INSTALL-FAIL", java
    tools = [tool] + ([java] if java else [])
    run = lambda *a: ["mise", "exec", *tools, "--", *a]

    if prep and sh(prep, app, log):
        return "PREP-FAIL", version or "default"
    # Code generation in every package that uses build_runner, deepest first so
    # a path dependency's output exists before the app that imports it. Not
    # when the repo commits its generated code: AuthPass does, and its pinned
    # build_runner predates Dart 3, so running it fails on every Flutter 3.x.
    committed = subprocess.run(["git", "ls-files", "*.g.dart"], cwd=repo,
                               capture_output=True, text=True).stdout.strip()
    for pubspec in ([] if committed else
                    sorted(repo.rglob("pubspec.yaml"), key=lambda p: -len(p.parts))):
        if ".pub-cache" in pubspec.parts or "build" in pubspec.parts:
            continue
        if "build_runner" in pubspec.read_text():
            pkg = pubspec.parent
            # --enforce-lockfile, as the recipes do: a resolve that rewrites
            # pubspec.lock leaves the tree dirty, and Tier 2 refuses that.
            sh(run("flutter", "pub", "get", "--enforce-lockfile"), pkg, log)
            if sh(run("dart", "run", "build_runner", "build", "--delete-conflicting-outputs"), pkg, log):
                return "CODEGEN-FAIL", version or "default"

    stub_signing(app, log)
    if not prefetch_gradle(app, log):
        return "GRADLE-FETCH-FAIL", version or "default"
    cmd = run("flutter", "build", "apk", "--debug")
    fl = flavor(app)
    if fl:
        cmd += ["--flavor", fl]
    if args not in ("", "-"):
        cmd += args.split()
    if sh(cmd, app, log, timeout=2400):
        return "BUILD-FAIL", version or "default"
    # Tier 2 refuses a dirty tree (`git status --porcelain`, untracked files
    # included), so a build that leaves one behind is not usable as-is. Build
    # output inside submodules is ignored locally rather than counted.
    for path in subprocess.run(["git", "config", "-f", ".gitmodules", "--get-regexp", r"\.path$"],
                               cwd=repo, capture_output=True, text=True).stdout.split()[1::2]:
        subprocess.run(["git", "config", f"submodule.{path}.ignore", "dirty"], cwd=repo)
    # Untracked build output the app's .gitignore misses (trale leaves
    # app/android/build/) goes in the clone's own .git/info/exclude, which is
    # not tracked, so the tree reads clean without editing the app.
    untracked = subprocess.run(["git", "status", "--porcelain"], cwd=repo,
                               capture_output=True, text=True).stdout.splitlines()
    junk = [l[3:] for l in untracked
            if l.startswith("?? ") and re.search(r"(^|/)(build|\.dart_tool|\.gradle)/$", l[3:])]
    if junk:
        with (repo / ".git" / "info" / "exclude").open("a") as ex:
            ex.write("".join(f"/{j}\n" for j in junk))
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=repo,
                           capture_output=True, text=True).stdout.strip()
    # Intermediates are ~2 GB per app and regenerated by any rebuild; ten of
    # them filled a 136 GB disk mid-run. The APK under flutter-apk/ is kept.
    for inter in app.glob("build/app/intermediates"):
        subprocess.run(["rm", "-rf", str(inter)])
    if dirty:
        log.write("tree left dirty by the build:\n" + dirty + "\n")
        return "BUILD-OK-DIRTY", version or "default"
    return "BUILD-OK", version or "default"


def stop_daemons(log) -> None:
    """Stop the Gradle daemons our builds left behind.

    Each app pins its own Gradle, so each build leaves a separate daemon idling
    with its heap: ten apps held 10 GB on a 15 GB laptop and starved the next
    build. Matched by the project directory in the daemon's own log, so a
    daemon serving anything outside the bench (another project's build) is
    never touched.
    """
    home = Path(os.environ.get("GRADLE_USER_HOME", Path.home() / ".gradle"))
    for pid in subprocess.run(["pgrep", "-f", "GradleDaemon"], capture_output=True,
                              text=True).stdout.split():
        logs = list((home / "daemon").glob(f"*/daemon-{pid}.out.log"))
        dirs = re.findall(r"currentDir=([^}]*)\}", logs[0].read_text(errors="replace")) if logs else []
        if dirs and all(d.startswith(str(ROOT)) for d in dirs):
            subprocess.run(["kill", pid])
            log.write(f"stopped Gradle daemon {pid}\n")


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    want = set(sys.argv[1:])
    rows = [l.split("\t") for l in APPS.read_text().splitlines()
            if l.strip() and not l.startswith("#")]
    for row in rows:
        app_id, url, commit, subdir = row[:4]
        flutter, args, prep = (row[4:] + ["", "", ""])[:3]
        if want and app_id not in want:
            continue
        t0 = time.time()
        log_path = ROOT / f"{app_id}.build.log"
        with log_path.open("w") as log:
            status, used = build(app_id, url, commit, subdir, flutter, args, prep, log)
            stop_daemons(log)
        line = f"{app_id}\t{status}\tflutter {used}\t{time.time() - t0:.0f}s"
        print(line, flush=True)
        with RESULTS.open("a") as out:
            out.write(time.strftime("%Y-%m-%d %H:%M") + "\t" + line + "\n")


if __name__ == "__main__":
    main()
