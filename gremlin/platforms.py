"""What differs between one UI toolkit and the next — and nothing else.

Gremlin's central bet is that a framework confesses its own failures to the log,
so detection can be an exact string match instead of a model's judgment. That
bet is not specific to Flutter: React Native prints its errors to `logcat` too,
just with different words. Everything between the two — adb, the accessibility
tree, the vision policy, the trace, the replayer, the three gates — is already
toolkit-agnostic.

So the toolkit-specific knowledge is gathered here, in one `Platform` record per
framework, and the rest of the codebase asks a Platform rather than hardcoding
Flutter. Adding a third toolkit should mean adding a record to this file and
nothing else.

A Platform answers five questions:

    1. Is this directory one of my projects?      (`detect`)
    2. What does my failure look like in logcat?  (`signals`)
    3. How do I name a source location?           (`location_re`, `normalize_source_path`)
    4. Where does my source live?                 (`source_globs`, `fence`)
    5. How do I rebuild an installed debug app?   (`build`)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


# Severity ranks, shared across platforms so the dashboard can order findings
# from any toolkit in one list.
CRASH = "crash"
LAYOUT = "layout"
HANG = "hang"


@dataclass(frozen=True)
class Signal:
    """One thing that, if it appears in the log, means the app is broken."""
    severity: str
    kind: str
    pattern: re.Pattern


@dataclass(frozen=True)
class Platform:
    name: str                      # stable id: "flutter" | "react-native"
    label: str                     # for humans: "Flutter" | "React Native"
    signals: tuple[Signal, ...]
    location_re: re.Pattern        # extracts (file, line) from a log line
    source_globs: tuple[str, ...]  # where to hunt for a file by basename
    fence: str                     # markdown code-fence language for excerpts
    detect: Callable[[Path], bool]
    project_name: Callable[[Path], str | None]
    build: Callable[[Path], Path]  # rebuild a debug apk, return its path
    fix_guidance: str              # toolkit-specific "don't just silence it" rules

    def classify(self, line: str) -> Signal | None:
        """First signal matching this log line, or None. First match wins."""
        for sig in self.signals:
            if sig.pattern.search(line):
                return sig
        return None

    def normalize_source_path(self, raw: str) -> str:
        """Map a path as it appears in a log to one relative to the project root."""
        return raw


# ---------------------------------------------------------------------------
# Flutter
# ---------------------------------------------------------------------------

_FLUTTER_SIGNALS = (
    Signal(CRASH, "native-crash", re.compile(r"FATAL EXCEPTION")),
    Signal(CRASH, "dart-exception", re.compile(r"Unhandled Exception", re.IGNORECASE)),
    Signal(LAYOUT, "renderflex-overflow", re.compile(r"A RenderFlex overflowed by", re.IGNORECASE)),
    # Flutter prints this as an uppercase banner: "EXCEPTION CAUGHT BY RENDERING LIBRARY".
    Signal(LAYOUT, "render-error", re.compile(r"Exception caught by rendering library", re.IGNORECASE)),
    Signal(HANG, "jank", re.compile(r"Skipped \d+ frames")),
    # Gremlin probe marker (see gremlin_probe.dart). Modern Flutter (Impeller)
    # doesn't reliably print framework/Dart errors to logcat, so an app under
    # test can opt in and forward them here. A marker line that also contains a
    # specific phrase above (e.g. an overflow) is already classified by that
    # phrase — this catch-all only fires for errors none of those matched.
    Signal(CRASH, "dart-exception", re.compile(r"GREMLIN_BUG")),
)

# e.g. "library_screen.dart:42:15" or "package:scribe/screens/x.dart:10".
_DART_LOCATION_RE = re.compile(r"([\w./]+\.dart):(\d+)(?::(\d+))?")


def _is_flutter(project: Path) -> bool:
    """A Flutter app/package declares `sdk: flutter` in its pubspec."""
    pub = project / "pubspec.yaml"
    if not pub.exists():
        return False
    try:
        return bool(re.search(r"^\s*sdk:\s*flutter\b", pub.read_text(), re.M))
    except OSError:
        return False


def _flutter_name(project: Path) -> str | None:
    try:
        m = re.search(r"^name:\s*(\S+)", (project / "pubspec.yaml").read_text(), re.M)
    except OSError:
        return None
    return m.group(1) if m else None


def _flutter_build(project: Path) -> Path:
    subprocess.run(["flutter", "build", "apk", "--debug"], cwd=str(project), check=True)
    return project / "build/app/outputs/flutter-apk/app-debug.apk"


class _Flutter(Platform):
    def normalize_source_path(self, raw: str) -> str:
        # Log paths look like "lib/screens/x.dart", "package:myapp/screens/x.dart",
        # or "myapp/screens/x.dart" — normalize any package prefix to the lib/ root.
        return re.sub(r"^(package:)?[^/]+/", "lib/", raw) if "/" in raw else raw


FLUTTER = _Flutter(
    name="flutter",
    label="Flutter",
    signals=_FLUTTER_SIGNALS,
    location_re=_DART_LOCATION_RE,
    source_globs=("lib/**/{name}",),
    fence="dart",
    detect=_is_flutter,
    project_name=_flutter_name,
    build=_flutter_build,
    fix_guidance=(
        "e.g. do not wrap the widget in a scroll view just to hide an overflow, "
        "do not wrap build() in try/catch, and do not delete the widget."
    ),
)


# ---------------------------------------------------------------------------
# React Native
# ---------------------------------------------------------------------------

# React Native routes every JS-side console call and every uncaught error to
# logcat under the `ReactNativeJS` tag, and lets a fatal JS error surface as a
# native `JavascriptException`. These are the words it uses.
_RN_SIGNALS = (
    Signal(CRASH, "native-crash", re.compile(r"FATAL EXCEPTION")),
    # A JS error that made it all the way to the native layer.
    Signal(CRASH, "js-exception", re.compile(r"com\.facebook\.react\.common\.JavascriptException")),
    # LogBox / ExceptionsManager report of an uncaught JS error.
    Signal(CRASH, "js-exception", re.compile(r"ReactNativeJS.*\bError:", re.IGNORECASE)),
    Signal(CRASH, "unhandled-rejection", re.compile(r"Possible Unhandled Promise Rejection", re.IGNORECASE)),
    # The bundle could not be built or served — the app is dead on arrival.
    Signal(CRASH, "bundle-error", re.compile(r"Unable to (load script|resolve module)", re.IGNORECASE)),
    # React's own correctness warnings. These are real defects, not style nits:
    # a missing key silently corrupts list state on reorder.
    Signal(LAYOUT, "react-warning", re.compile(r"Each child in a list should have a unique")),
    Signal(LAYOUT, "react-warning", re.compile(r"VirtualizedList: ", re.IGNORECASE)),
    # Updating state on an unmounted component / bad hook usage.
    Signal(LAYOUT, "react-warning", re.compile(r"Warning: (Cannot update|Invalid hook call)", re.IGNORECASE)),
    Signal(HANG, "jank", re.compile(r"Skipped \d+ frames")),
    # Probe marker (see gremlinProbe.js), same opt-in contract as Flutter's.
    Signal(CRASH, "js-exception", re.compile(r"GREMLIN_BUG")),
)

# e.g. "App.tsx:42:15", "src/screens/Home.jsx:10". Deliberately excludes the
# Metro bundle URL form (index.android.bundle:1:12345), which carries a line
# number in generated code and would point the reporter at nothing real.
_JS_LOCATION_RE = re.compile(r"([\w./-]+\.(?:tsx|ts|jsx|js)):(\d+)(?::(\d+))?")

_RN_IGNORED_PATHS = re.compile(r"(^|/)(node_modules|index\.android\.bundle)")


def _is_react_native(project: Path) -> bool:
    """An RN app depends on `react-native` and has an android/ folder to drive."""
    pkg = project / "package.json"
    if not pkg.exists() or not (project / "android").is_dir():
        return False
    try:
        data = json.loads(pkg.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    return "react-native" in deps


def _rn_name(project: Path) -> str | None:
    try:
        return json.loads((project / "package.json").read_text()).get("name")
    except (OSError, json.JSONDecodeError):
        return None


def _rn_build(project: Path) -> Path:
    """Assemble a *release* APK carrying a *development* JS bundle.

    Two constraints pull in opposite directions here.

    Replay must not depend on Metro: a stock debug build fetches its bundle from
    the dev server at launch, so a cold-start replay would depend on a process
    outside the run. That argues for a release build, which embeds the bundle.

    But a production bundle is exactly the one that cannot report the defects we
    care about. React ships a separate production build with its development
    warnings compiled out — no "missing key", no "invalid hook call", no
    "setState on an unmounted component" — so a plain release build would make
    three of this platform's signals permanently unmatchable, and Gremlin would
    look like it was finding nothing because nothing was wrong.

    The resolution is to bundle with `--dev true` (keeping `__DEV__`, and with it
    React's development build and its warnings) and then assemble release, which
    embeds that bundle and disables the dev-server fetch. The app under test is
    a *fixture*; it is supposed to be instrumented.

    The stock template signs release with the debug keystore, so this needs no
    signing setup; a project that overrides that needs its own keystore.
    """
    android = project / "android"
    assets = android / "app/src/main/assets"
    assets.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        ["npx", "react-native", "bundle",
         "--platform", "android",
         "--dev", "true",              # keep React's development warnings
         "--entry-file", "index.js",
         "--bundle-output", str(assets / "index.android.bundle"),
         "--assets-dest", str(android / "app/src/main/res")],
        cwd=str(project), check=True,
    )
    # Gradle refuses to configure without an SDK location, and the SDK is
    # frequently installed without ANDROID_HOME being exported — the same reason
    # `emulator` is often missing from PATH. Fall back to the known install
    # locations rather than failing with a setup error the developer has to
    # decode.
    env = dict(os.environ)
    if not env.get("ANDROID_HOME") and not (android / "local.properties").exists():
        from .emulator import sdk_root
        found = sdk_root()
        if found is not None:
            env["ANDROID_HOME"] = str(found)

    subprocess.run([str(android / "gradlew"), "assembleRelease"],
                   cwd=str(android), check=True, env=env)
    return android / "app/build/outputs/apk/release/app-release.apk"


class _ReactNative(Platform):
    def normalize_source_path(self, raw: str) -> str:
        # Strip a leading "./" and any absolute prefix up to the project root;
        # stacks may carry either a relative path or a full on-disk path.
        return re.sub(r"^\./", "", raw)


REACT_NATIVE = _ReactNative(
    name="react-native",
    label="React Native",
    signals=_RN_SIGNALS,
    location_re=_JS_LOCATION_RE,
    # RN projects vary: sources sit at the root, under src/, or under app/.
    source_globs=("{name}", "src/**/{name}", "app/**/{name}"),
    fence="jsx",
    detect=_is_react_native,
    project_name=_rn_name,
    build=_rn_build,
    fix_guidance=(
        "e.g. do not wrap the component in a try/catch or error boundary just to "
        "swallow the error, do not silence the warning with a console filter, and "
        "do not delete the component."
    ),
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

PLATFORMS: tuple[Platform, ...] = (FLUTTER, REACT_NATIVE)
DEFAULT = FLUTTER


def detect_platform(project: Path) -> Platform | None:
    """Which toolkit builds this directory, if any."""
    project = Path(project).expanduser()
    for plat in PLATFORMS:
        if plat.detect(project):
            return plat
    return None


def by_name(name: str | None) -> Platform:
    """Look a platform up by its stable id, falling back to the default."""
    for plat in PLATFORMS:
        if plat.name == name:
            return plat
    return DEFAULT


def is_ignored_source(path: str) -> bool:
    """True for paths no report should point at (vendored or generated code)."""
    return bool(_RN_IGNORED_PATHS.search(path))


# ---------------------------------------------------------------------------
# Detection from the device, for apps we have no source for
# ---------------------------------------------------------------------------
#
# `detect_platform` above reads a project directory, which only works when the
# developer owns the source. An app that is merely *installed* — the case for
# every device-only target — has to be identified from the APK itself.
#
# Both toolkits ship unmistakable payloads: Flutter bundles `libflutter.so` and
# an `assets/flutter_assets/` tree, React Native bundles its JS as
# `assets/index.android.bundle` alongside `libreactnativejni.so` (or, since the
# new architecture merged the libraries, `libreactnative.so`). Neither can be
# absent from a working app, so presence is conclusive and absence means "not
# this toolkit" rather than "unknown build flavour".

_APK_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    # Checked in order; first toolkit with any marker present wins. React Native
    # is checked first because a Flutter app never carries an RN bundle, whereas
    # an RN app may legitimately contain some unrelated `.so` we'd rather not
    # have to reason about.
    ("react-native", ("assets/index.android.bundle", "libreactnativejni.so",
                      "libreactnative.so")),
    ("flutter", ("assets/flutter_assets/", "libflutter.so")),
)

# Cache per (serial, package): pulling an APK is seconds of USB, and the target
# list re-detects on every dashboard refresh.
_device_platform_cache: dict[tuple[str | None, str], Platform | None] = {}


def detect_platform_on_device(dev, package: str) -> Platform | None:
    """Which toolkit built the installed `package`, or None if neither.

    Tries the cheap check first — the native libraries the installer extracted
    onto disk, which is one `ls` — and only falls back to pulling the APK when
    the app was installed with `extractNativeLibs=false` and there is nothing on
    disk to list.
    """
    key = (getattr(dev, "serial", None), package)
    if key in _device_platform_cache:
        return _device_platform_cache[key]

    found = _platform_from_native_libs(dev, package) or _platform_from_apk(dev, package)
    _device_platform_cache[key] = found
    return found


def _match_markers(names: str) -> Platform | None:
    """First toolkit whose markers appear in a blob of file names."""
    for plat_name, markers in _APK_MARKERS:
        if any(m in names for m in markers):
            return by_name(plat_name)
    return None


def _platform_from_native_libs(dev, package: str) -> Platform | None:
    """Look for the toolkit's `.so` in the app's extracted native library dir."""
    try:
        dump = dev._shell("dumpsys", "package", package, timeout=30)
    except Exception:
        return None
    m = re.search(r"(?:legacyN|n)ativeLibrary(?:Dir|Path)=(\S+)", dump)
    if not m:
        return None
    try:
        listing = dev._shell("ls", "-R", m.group(1), timeout=20)
    except Exception:
        return None
    return _match_markers(listing)


def _platform_from_apk(dev, package: str) -> Platform | None:
    """Pull the base APK and read its table of contents.

    Only the central directory matters, but adb has no partial-read primitive,
    so the whole base APK comes across. It is pulled to a temp file that is
    always removed, and the result is cached by the caller.
    """
    try:
        paths = dev._shell("pm", "path", package, timeout=30)
    except Exception:
        return None
    apks = [l[len("package:"):].strip() for l in paths.splitlines()
            if l.startswith("package:")]
    if not apks:
        return None
    # Splits carry assets but the base always carries the toolkit runtime.
    remote = next((p for p in apks if p.endswith("base.apk")), apks[0])

    with tempfile.TemporaryDirectory() as tmp:
        local = Path(tmp) / "base.apk"
        try:
            subprocess.run(dev._base() + ["pull", remote, str(local)],
                           capture_output=True, timeout=180, check=True)
            with zipfile.ZipFile(local) as z:
                return _match_markers("\n".join(z.namelist()))
        except (OSError, subprocess.SubprocessError, zipfile.BadZipFile):
            return None


# Once an app is *running*, the toolkit announces itself in logcat under its own
# tag — a free confirmation for a target we could not identify statically.
_LOG_TAG_HINTS: tuple[tuple[str, re.Pattern], ...] = (
    ("react-native", re.compile(r"\bReactNativeJS\b|\bReactNative\b")),
    ("flutter", re.compile(r"\bflutter\b")),
)


def platform_from_log(lines: "list[str] | str") -> Platform | None:
    """Infer the toolkit from logcat output the app has already produced."""
    blob = lines if isinstance(lines, str) else "\n".join(lines)
    for plat_name, pattern in _LOG_TAG_HINTS:
        if pattern.search(blob):
            return by_name(plat_name)
    return None
