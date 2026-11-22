"""Publishes LibreVDI Windows installers through the upstream download mechanisms.

Files are taken from ``LIBREVDI_DOWNLOADS_DIR`` (default ``/opt/librevdi/downloads``, mounted from
``./downloads`` on the Docker host) and, for every installer not found there, from the installers
bundled into release images (``/opt/librevdi/bundled-downloads``). They are copied to the paths the
OpenUDS broker serves:

* client  -> static ``clients/UDSLauncherInstaller-<version>.exe``
             (portal button "Launcher" / ``/uds/page/launcher-download``, all users)
* agent   -> ``uds/osmanagers/WindowsOsManager/files/UDSActor[Unmanaged]Setup-<version>.exe``
             (listed in the admin UI download section)

Missing files are skipped. Runs once when the web container starts.
"""

import glob
import os
import re
import shutil
import sys

APP = "/app"
VERSION_FILE = os.path.join(APP, "uds/core/consts/system.py")

# (source glob in downloads dir, target path template relative to /app)
TARGETS: tuple[tuple[str, str], ...] = (
    ("LibreVDI-Client-Setup-*.exe", "static/clients/UDSLauncherInstaller-{version}.exe"),
    ("LibreVDI-Agent-managed-Setup-*.exe", "uds/osmanagers/WindowsOsManager/files/UDSActorSetup-{version}.exe"),
    (
        "LibreVDI-Agent-unmanaged-Setup-*.exe",
        "uds/osmanagers/WindowsOsManager/files/UDSActorUnmanagedSetup-{version}.exe",
    ),
)


def upstream_version(version_file: str = VERSION_FILE) -> str:
    with open(version_file, encoding="utf-8") as f:
        match = re.search(r'^VERSION:\s*typing\.Final\[str\]\s*=\s*"([^"]+)"', f.read(), re.MULTILINE)
    if not match:
        raise RuntimeError(f"cannot determine upstream version from {version_file}")
    return match.group(1)


def newest(pattern: str) -> str | None:
    files = glob.glob(pattern)
    return max(files, key=os.path.getmtime) if files else None


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
        dst = os.path.join(app_dir, target_tpl.format(version=version))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        published.append((os.path.basename(src), dst))
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
