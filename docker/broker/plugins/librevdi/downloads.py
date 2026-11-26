"""Download lists in the LibreVDI style.

* Agent downloads (admin "Downloads" page): renamed to LibreVDI file names and descriptions;
  entries whose file does not exist are hidden (upstream lists Linux/macOS packages that a
  LibreVDI installation does not ship).
* Linux agent packages (``librevdi-agent[-unmanaged]_*.deb``) are registered as admin downloads.
* Client downloads (portal "Launcher" page): the Windows entry and the Linux entries point to the
  LibreVDI client files; only clients that are actually present are listed.

Installers are published to the upstream locations by ``librevdi_ext.downloads`` before the web
server starts, so the file checks here see the final state.
"""

import dataclasses
import glob
import json
import os
import re
import typing

from django.conf import settings
from uds.core import types
from uds.core.managers import downloads_manager
from uds.web.util import udsclients_info

_NAME_MAP = (
    (re.compile(r"^UDSActorUnmanagedSetup-"), "LibreVDI-Agent-unmanaged-Setup-"),
    (re.compile(r"^UDSActorSetup-"), "LibreVDI-Agent-managed-Setup-"),
)
_TEXT_MAP = (
    (re.compile(r"\bUDS [Aa]ctor\b"), "LibreVDI Agent"),
    (re.compile(r"\bUDS\b"), "LibreVDI"),
)


def _rebrand(text: str, rules: tuple[tuple[re.Pattern[str], str], ...]) -> str:
    for pattern, repl in rules:
        text = pattern.sub(repl, text)
    return text


def _static_file(url: str) -> str:
    prefix = settings.STATIC_URL
    rel = url[len(prefix) :] if url.startswith(prefix) else url.lstrip("/")
    return os.path.join(settings.STATIC_ROOT, rel)


def _published_names() -> dict[str, str]:
    """Real installer file names (with LibreVDI version), written by librevdi_ext.downloads."""
    app = os.path.dirname(os.path.abspath(settings.STATIC_ROOT))  # /app
    try:
        with open(os.path.join(settings.STATIC_ROOT, "librevdi", "installers.json"), encoding="utf-8") as f:
            return {os.path.normpath(os.path.join(app, k)): v for k, v in json.load(f).items()}
    except (OSError, ValueError):
        return {}


_DISTRO_NAMES = {
    "ubuntu2404": "Ubuntu 24.04",
    "ubuntu2604": "Ubuntu 26.04",
    "rocky9": "Rocky Linux 9",
    "rocky10": "Rocky Linux 10",
}
# librevdi-client_0.1.0~dev.5_amd64-ubuntu2404.deb, librevdi-client-0.1.0~dev.5.x86_64-rocky9.rpm
_PACKAGE_RE = re.compile(r"^(librevdi-[a-z-]+?)(?:_[^_]+_amd64-|-\d[^/]*\.x86_64-)([0-9a-z]+)\.(deb|rpm)$")
_MIMETYPES = {"deb": "application/x-debian-package", "rpm": "application/x-rpm"}
_AGENT_DESCRIPTIONS = {
    "librevdi-agent-unmanaged": "LibreVDI Agent (unmanaged) for persistent Linux desktops - {distro}",
    "librevdi-agent": "LibreVDI Agent (managed) for cloned Linux desktops - {distro}",
}


def _linux_packages(directory: str, package: str) -> list[tuple[str, str, str]]:
    """(file name, distribution name, format) of the packages of ``package`` in ``directory``,
    in the order of ``_DISTRO_NAMES``."""
    found = []
    for path in glob.glob(os.path.join(directory, "librevdi-*")):
        match = _PACKAGE_RE.match(os.path.basename(path))
        if match and match.group(1) == package:
            found.append((os.path.basename(path), match.group(2), match.group(3)))
    order = list(_DISTRO_NAMES)
    found.sort(key=lambda f: (order.index(f[1]) if f[1] in order else len(order), f[0]))
    return [(name, _DISTRO_NAMES.get(distro, distro), fmt) for name, distro, fmt in found]


def _register_linux_agents(manager: typing.Any, app: str) -> None:
    directory = os.path.join(app, "uds", "osmanagers", "LinuxOsManager", "files")
    for package, description in _AGENT_DESCRIPTIONS.items():
        for name, distro, fmt in _linux_packages(directory, package):
            manager.register(
                name,
                description.format(distro=distro),
                os.path.join(directory, name),
                mimetype=_MIMETYPES[fmt],
            )


def _linux_clients(base_url: str) -> list[typing.Any]:
    clients_dir = os.path.join(settings.STATIC_ROOT, "clients")
    return [
        types.plugins.UDSClientPlugin(
            url=f"{base_url}/{name}", description=f"LibreVDI Client ({distro})", name="Linux", legacy=False
        )
        for name, distro, _fmt in _linux_packages(clients_dir, "librevdi-client")
    ]


def apply() -> None:
    manager = downloads_manager()
    app = os.path.dirname(os.path.abspath(settings.STATIC_ROOT))  # /app
    _register_linux_agents(manager, app)
    table = getattr(manager, "_downloadables", None)
    names = _published_names()
    if isinstance(table, dict):
        for key in list(table):
            item = table[key]
            if not os.path.isfile(item.path):
                del table[key]
                continue
            real_name = names.get(os.path.normpath(item.path))
            item.name = real_name or _rebrand(item.name, _NAME_MAP)
            item.description = _rebrand(item.description, _TEXT_MAP)

    clients = sorted(glob.glob(os.path.join(settings.STATIC_ROOT, "clients", "LibreVDI-Client-Setup-*.exe")))
    for i, plugin in enumerate(udsclients_info.PLUGINS):
        if clients and plugin.name == "Windows" and "UDSLauncherInstaller-" in plugin.url:
            udsclients_info.PLUGINS[i] = dataclasses.replace(
                plugin,
                url=plugin.url.rsplit("/", 1)[0] + "/" + os.path.basename(clients[-1]),
                description="LibreVDI Client (Windows)",
            )
    if udsclients_info.PLUGINS:
        base_url = udsclients_info.PLUGINS[0].url.rsplit("/", 1)[0]
        linux = _linux_clients(base_url)
        if linux:  # LibreVDI packages replace the upstream Linux entries
            udsclients_info.PLUGINS[:] = [p for p in udsclients_info.PLUGINS if p.name != "Linux"] + linux
    udsclients_info.PLUGINS[:] = [p for p in udsclients_info.PLUGINS if os.path.isfile(_static_file(p.url))]


apply()
