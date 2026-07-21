"""Discover which app to test — the developer picks, the agent doesn't.

Gremlin drives ONE app per run and needs four things about it: the `package`
(to launch and to scope logcat), the launcher `activity`, the `source_root` (so
the Tier-2 fixer can resolve `file:line`), and the `platform` (so the oracle
knows which failure vocabulary to match). This module scans a projects
directory, identifies the app projects in it, and reads those facts out of the
Android config.

The first three come from `android/`, which every toolkit that ships an Android
app must have — so this module is toolkit-agnostic and asks `platforms` for the
fourth rather than assuming Flutter.

    from gremlin.targets import find_projects
    for t in find_projects(Path.home() / "Projects"):
        print(t.name, t.package, t.platform, t.installed)
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from . import platforms

_ANDROID_NS = "http://schemas.android.com/apk/res/android"


@dataclass
class Target:
    name: str                  # friendly project name, or the package for device apps
    package: str               # applicationId, e.g. "com.scribe.scribe"
    activity: str              # adb component; "" for device apps (resolved on launch)
    source_root: Path | None   # the app project dir, or None for a device-only app
    installed: bool = False    # is this package currently on the device?
    source: str = "project"    # "project" (has source) | "device" (installed only)
    platform: str = "flutter"  # platforms.Platform.name of the toolkit that built it

    @property
    def toolkit(self) -> platforms.Platform:
        """The Platform record this target's toolkit is described by."""
        return platforms.by_name(self.platform)

    def to_config(self, **overrides) -> Config:
        kw = dict(package=self.package, activity=self.activity or f"{self.package}/.MainActivity")
        if self.source_root is not None:
            kw["scribe_root"] = self.source_root
        cfg = Config(**kw)
        cfg.platform = self.platform
        for k, v in overrides.items():
            setattr(cfg, k, v)
        return cfg

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "package": self.package,
            "activity": self.activity,
            "source_root": str(self.source_root) if self.source_root else None,
            "installed": self.installed,
            "source": self.source,
            "platform": self.platform,
            "platform_label": self.toolkit.label,
        }


def is_app_project(project: Path) -> bool:
    """Whether any toolkit Gremlin knows about builds this directory."""
    return platforms.detect_platform(project) is not None


# The old Flutter-only names, kept so existing callers and scripts keep working.
def is_flutter_project(project: Path) -> bool:
    return platforms.FLUTTER.detect(Path(project).expanduser())


def find_projects(root: Path, dev=None) -> list[Target]:
    """Every app directly under `root` (plus `root` itself), as Targets.

    If a Device is given, each target is flagged with whether it's installed.
    Results are sorted: installed first, then by name.
    """
    root = Path(root).expanduser()
    candidates: list[Path] = []
    if is_app_project(root):
        candidates.append(root)
    if root.is_dir():
        candidates += [p for p in sorted(root.iterdir()) if p.is_dir() and is_app_project(p)]

    installed = _installed_packages(dev) if dev is not None else None
    targets: list[Target] = []
    for proj in candidates:
        t = _target_from_project(proj)
        if t is None:
            continue
        if installed is not None:
            t.installed = t.package in installed
        targets.append(t)

    targets.sort(key=lambda t: (not t.installed, t.name.lower()))
    return targets


find_flutter_projects = find_projects  # legacy alias


def installed_targets(dev) -> list[Target]:
    """Every user-installed app on the device as a (source-less) Target.

    Activity is left blank and resolved lazily at launch — resolving all of them
    up front would be one adb call per app. The Tier-2 fixer needs a source root,
    so these are explore-only; they still get full exploration + bug detection.

    The toolkit is *not* probed here for the same reason: identifying an app from
    its APK costs a pull, and doing that for every installed package would make
    the target list take minutes. It is resolved on selection instead, by
    `identify_target`.
    """
    targets = []
    for pkg in dev.list_third_party_packages():
        targets.append(Target(name=pkg, package=pkg, activity="", source_root=None,
                              installed=True, source="device", platform=""))
    return targets


def identify_target(target: Target, dev) -> Target:
    """Fill in a device-only target's toolkit by inspecting the installed app.

    Cheap and cached for project targets (which already know), a one-off APK
    inspection for a device-only one. Call this when a target is *selected*, not
    when the list is built.
    """
    if target.platform:
        return target
    found = platforms.detect_platform_on_device(dev, target.package)
    target.platform = found.name if found else ""
    return target


def all_targets(root: Path, dev) -> list[Target]:
    """Source projects (full capability) first, then device-only installed apps.

    A package detected as a project is not duplicated as a device entry.
    """
    projects = find_projects(root, dev=dev)
    seen = {t.package for t in projects}
    devices = [t for t in installed_targets(dev) if t.package not in seen]
    return projects + devices


def target_for_project(project: Path, dev=None) -> Target | None:
    """Build a single Target from an explicit project path."""
    project = Path(project).expanduser()
    if not is_app_project(project):
        return None
    t = _target_from_project(project)
    if t and dev is not None:
        t.installed = t.package in _installed_packages(dev)
    return t


# ---- derivation ------------------------------------------------------------
def _target_from_project(project: Path) -> Target | None:
    plat = platforms.detect_platform(project)
    if plat is None:
        return None
    package = _read_application_id(project)
    if not package:
        return None
    activity = _read_launcher_activity(project, package)
    name = _pretty(plat.project_name(project)) or project.name
    return Target(name=name, package=package, activity=activity,
                  source_root=project, platform=plat.name)


def _read_application_id(project: Path) -> str | None:
    """`applicationId` from build.gradle(.kts); fall back to `namespace`."""
    for fname in ("android/app/build.gradle.kts", "android/app/build.gradle"):
        f = project / fname
        if not f.exists():
            continue
        text = f.read_text()
        for key in ("applicationId", "namespace"):
            # matches both `applicationId = "x"` (kts) and `applicationId "x"` (groovy)
            m = re.search(rf'{key}\s*=?\s*"([^"]+)"', text)
            if m:
                return m.group(1)
    return None


def _read_launcher_activity(project: Path, package: str) -> str:
    """Launcher activity as an adb component `package/activity-class`.

    Parses AndroidManifest for the <activity> whose intent-filter has action
    MAIN + category LAUNCHER. Defaults to `.MainActivity` (Flutter's default).
    """
    manifest = project / "android/app/src/main/AndroidManifest.xml"
    cls = ".MainActivity"
    if manifest.exists():
        try:
            root = ET.fromstring(manifest.read_text())
            for act in root.iter("activity"):
                name = act.get(f"{{{_ANDROID_NS}}}name")
                if not name:
                    continue
                actions = {a.get(f"{{{_ANDROID_NS}}}name") for a in act.iter("action")}
                cats = {c.get(f"{{{_ANDROID_NS}}}name") for c in act.iter("category")}
                if "android.intent.action.MAIN" in actions and "android.intent.category.LAUNCHER" in cats:
                    cls = name
                    break
        except ET.ParseError:
            pass
    return f"{package}/{cls}"


def _pretty(name: str | None) -> str | None:
    """Prettify a package identifier: "my_cool_app" -> "My Cool App"."""
    if not name:
        return None
    return " ".join(w.capitalize() for w in name.replace("-", "_").split("_"))


def _installed_packages(dev) -> set[str]:
    """Set of package names installed on the device (empty if adb unavailable)."""
    try:
        out = dev._shell("pm", "list", "packages")
    except Exception:
        return set()
    return {line[len("package:"):].strip() for line in out.splitlines() if line.startswith("package:")}
