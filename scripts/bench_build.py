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


def build(app_id: str, url: str, commit: str, subdir: str, prep: str, log) -> tuple[str, str]:
    repo = ROOT / app_id
    if not (repo / ".git").exists():
        # One retry: on a flaky connection the first attempt can fail on DNS alone.
        clone = ["git", "clone", "-q", "--filter=blob:none", url, str(repo)]
        if sh(clone, ROOT, log) and (time.sleep(10) or sh(clone, ROOT, log)):
            return "CLONE-FAIL", ""
    if sh(["git", "checkout", "-q", "-f", commit], repo, log):
        return "CHECKOUT-FAIL", ""
    # Only submodules an anonymous clone can reach; ssh:// ones are packaging.
    subs = subprocess.run(["git", "config", "-f", ".gitmodules", "--get-regexp", r"submodule\..*\.url"],
                          cwd=repo, capture_output=True, text=True).stdout.splitlines()
    for line in subs:
        key, sub_url = line.split(None, 1)
        if not sub_url.startswith(("ssh://", "git@")):
            path = subprocess.run(["git", "config", "-f", ".gitmodules", key.replace(".url", ".path")],
                                  cwd=repo, capture_output=True, text=True).stdout.strip()
            sh(["git", "submodule", "update", "--init", "--recursive", path], repo, log)

    app = repo / (subdir if subdir not in ("", ".") else "")
    version = pinned_flutter(app)
    tool = f"flutter@{version}" if version else "flutter"
    # An hour: each Flutter SDK is ~1.5 GB, and a slow link took 30 min for half.
    if version and sh(["mise", "install", tool], app, log, timeout=3600):
        return "FLUTTER-INSTALL-FAIL", version
    run = lambda *a: ["mise", "exec", tool, "--", *a]

    if prep and sh(prep, app, log):
        return "PREP-FAIL", version or "default"
    # Code generation in every package that uses build_runner, deepest first so
    # a path dependency's output exists before the app that imports it.
    for pubspec in sorted(repo.rglob("pubspec.yaml"), key=lambda p: -len(p.parts)):
        if ".pub-cache" in pubspec.parts or "build" in pubspec.parts:
            continue
        if "build_runner" in pubspec.read_text():
            pkg = pubspec.parent
            sh(run("flutter", "pub", "get"), pkg, log)
            if sh(run("dart", "run", "build_runner", "build", "--delete-conflicting-outputs"), pkg, log):
                return "CODEGEN-FAIL", version or "default"

    cmd = run("flutter", "build", "apk", "--debug")
    fl = flavor(app)
    if fl:
        cmd += ["--flavor", fl]
    if sh(cmd, app, log, timeout=2400):
        return "BUILD-FAIL", version or "default"
    return "BUILD-OK", version or "default"


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    want = set(sys.argv[1:])
    rows = [l.split("\t") for l in APPS.read_text().splitlines()
            if l.strip() and not l.startswith("#")]
    for row in rows:
        app_id, url, commit, subdir = row[:4]
        prep = row[4] if len(row) > 4 else ""
        if want and app_id not in want:
            continue
        t0 = time.time()
        log_path = ROOT / f"{app_id}.build.log"
        with log_path.open("w") as log:
            status, flutter = build(app_id, url, commit, subdir, prep, log)
        line = f"{app_id}\t{status}\tflutter {flutter}\t{time.time() - t0:.0f}s"
        print(line, flush=True)
        with RESULTS.open("a") as out:
            out.write(time.strftime("%Y-%m-%d %H:%M") + "\t" + line + "\n")


if __name__ == "__main__":
    main()
