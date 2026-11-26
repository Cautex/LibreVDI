"""Publishes LibreVDI installers and packages through the upstream download mechanisms.

Files are taken from ``LIBREVDI_DOWNLOADS_DIR`` (default ``/opt/librevdi/downloads``, mounted from
``./downloads`` on the Docker host) and, for every installer not found there, from the installers
bundled into release images (``/opt/librevdi/bundled-downloads``). They are copied to the paths the
OpenUDS broker serves:

* client  -> static ``clients/LibreVDI-Client-Setup-<version>.exe`` (file name kept; the LibreVDI
             plugin points the portal's Windows entry to it, ``/uds/page/launcher-download``)
* agent   -> ``uds/osmanagers/WindowsOsManager/files/UDSActor[Unmanaged]Setup-<version>.exe``
             (listed in the admin UI download section)
* Linux client packages (``librevdi-client_<version>_amd64-<distro>.deb``, Ubuntu;
  ``librevdi-client-<version>.x86_64-<distro>.rpm``, Rocky Linux) -> static ``clients/``
  (file name kept; listed in the portal's Linux section by the LibreVDI plugin)
* Linux agent packages (``librevdi-agent[-unmanaged]`` .deb / .rpm, names as above) ->
  ``uds/osmanagers/LinuxOsManager/files/`` (file name kept; registered by the LibreVDI plugin)

Missing files are skipped. Runs once when the web container starts.
"""

import glob
import json
import os
import re
import shutil
import sys

APP = "/app"
VERSION_FILE = os.path.join(APP, "uds/core/consts/system.py")

# (source glob in downloads dir, target path template relative to /app)
TARGETS: tuple[tuple[str, str], ...] = (
    ("LibreVDI-Client-Setup-*.exe", "static/clients/{source}"),
    ("LibreVDI-Agent-managed-Setup-*.exe", "uds/osmanagers/WindowsOsManager/files/UDSActorSetup-{version}.exe"),
    (
        "LibreVDI-Agent-unmanaged-Setup-*.exe",
        "uds/osmanagers/WindowsOsManager/files/UDSActorUnmanagedSetup-{version}.exe",
    ),
)
DEB_DISTROS: tuple[str, ...] = ("ubuntu2404", "ubuntu2604")
RPM_DISTROS: tuple[str, ...] = ("rocky9", "rocky10")
LINUX_AGENT_DIR = "uds/osmanagers/LinuxOsManager/files"
_LINUX_PACKAGES = (
    ("librevdi-client", "static/clients"),
    ("librevdi-agent", LINUX_AGENT_DIR),
    ("librevdi-agent-unmanaged", LINUX_AGENT_DIR),
)
TARGETS += tuple(
    (f"{package}_*_amd64-{distro}.deb", f"{target_dir}/{{source}}")
    for package, target_dir in _LINUX_PACKAGES
    for distro in DEB_DISTROS
)
# "[0-9]" after the name: librevdi-agent-* would also match librevdi-agent-unmanaged-*
TARGETS += tuple(
    (f"{package}-[0-9]*.x86_64-{distro}.rpm", f"{target_dir}/{{source}}")
    for package, target_dir in _LINUX_PACKAGES
    for distro in RPM_DISTROS
)


def upstream_version(version_file: str = VERSION_FILE) -> str:
    with open(version_file, encoding="utf-8") as f:
        match = re.search(r'^VERSION:\s*typing\.Final\[str\]\s*=\s*"([^"]+)"', f.read(), re.MULTILINE)
    if not match:
        raise RuntimeError(f"cannot determine upstream version from {version_file}")
    return match.group(1)


_VERSION_RES = (
    re.compile(r"-Setup-(\d+(?:\.\d+)*)(?:-([0-9A-Za-z.-]+))?\.exe$"),
    re.compile(r"_(\d+(?:\.\d+)*)(?:~([0-9A-Za-z.]+))?_[0-9a-z]+(?:-[0-9a-z]+)?\.deb$"),  # Debian: ~ = pre-release
    re.compile(r"-(\d+(?:\.\d+)*)(?:~([0-9A-Za-z.]+))?\.x86_64(?:-[0-9a-z]+)?\.rpm$"),  # RPM: same convention
)


def version_key(path: str) -> tuple:
    """Sort key: highest version wins (0.2.0 > 0.2.0-rc.1 > 0.1.0-dev.12 > 0.1.0-dev.8), then mtime."""
    name = os.path.basename(path)
    match = next((m for r in _VERSION_RES if (m := r.search(name))), None)
    if not match:
        return ((), 0, (), os.path.getmtime(path))
    release = tuple(int(x) for x in match.group(1).split("."))
    pre = match.group(2)
    pre_nums = tuple(int(x) for x in re.findall(r"\d+", pre)) if pre else ()
    return (release, 0 if pre else 1, pre_nums, os.path.getmtime(path))


def newest(pattern: str) -> str | None:
    files = glob.glob(pattern)
    return max(files, key=version_key) if files else None


MANIFEST = "static/librevdi/installers.json"  # target path (relative to /app) -> published file name


BUNDLED_DIR = "/opt/librevdi/bundled-downloads"


def publish(source_dirs: str | list[str], app_dir: str, version: str) -> list[tuple[str, str]]:
    """Copies each installer from the first directory that has one (earlier directories win)."""
    if isinstance(source_dirs, str):
        source_dirs = [source_dirs]
    published = []
    for source_glob, target_tpl in TARGETS:
        src = next((f for d in source_dirs if (f := newest(os.path.join(d, source_glob)))), None)
        if not src:
            continue
        dst = os.path.join(app_dir, target_tpl.format(version=version, source=os.path.basename(src)))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if "{source}" in target_tpl:  # drop copies of other versions from earlier starts
            for stale in glob.glob(os.path.join(os.path.dirname(dst), source_glob)):
                if stale != dst:
                    os.remove(stale)
        shutil.copyfile(src, dst)
        published.append((os.path.basename(src), dst))
    manifest = os.path.join(app_dir, MANIFEST)
    os.makedirs(os.path.dirname(manifest), exist_ok=True)
    with open(manifest, "w", encoding="utf-8") as f:
        json.dump({os.path.relpath(dst, app_dir): name for name, dst in published}, f, indent=1)
    return published


def main() -> int:
    source_dirs = [
        d
        for d in (os.environ.get("LIBREVDI_DOWNLOADS_DIR", "/opt/librevdi/downloads"), BUNDLED_DIR)
        if os.path.isdir(d)
    ]
    if not source_dirs:
        return 0
    try:
        published = publish(source_dirs, APP, upstream_version())
    except OSError as e:  # never block the web server because of downloads
        print(f"librevdi: WARNING: could not publish installers: {e}", file=sys.stderr)
        return 0
    for name, dst in published:
        print(f"librevdi: published {name} -> {dst}")
    if not published:
        print(f"librevdi: no installers found in {', '.join(source_dirs)} (see downloads/README.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
