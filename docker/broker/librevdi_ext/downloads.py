"""Publishes LibreVDI Windows installers through the upstream download mechanisms.

Files are taken from ``LIBREVDI_DOWNLOADS_DIR`` (default ``/opt/librevdi/downloads``, mounted from
``./downloads`` on the Docker host) and copied to the paths the OpenUDS broker serves:

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


def publish(source_dir: str, app_dir: str, version: str) -> list[tuple[str, str]]:
    published = []
    for source_glob, target_tpl in TARGETS:
        src = newest(os.path.join(source_dir, source_glob))
        if not src:
            continue
        dst = os.path.join(app_dir, target_tpl.format(version=version))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        published.append((os.path.basename(src), dst))
    return published


def main() -> int:
    source_dir = os.environ.get("LIBREVDI_DOWNLOADS_DIR", "/opt/librevdi/downloads")
    if not os.path.isdir(source_dir):
        return 0
    try:
        published = publish(source_dir, APP, upstream_version())
    except OSError as e:  # never block the web server because of downloads
        print(f"librevdi: WARNING: could not publish installers: {e}", file=sys.stderr)
        return 0
    for name, dst in published:
        print(f"librevdi: published {name} -> {dst}")
    if not published:
        print(f"librevdi: no installers found in {source_dir} (see downloads/README.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
