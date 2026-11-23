"""Download lists in the LibreVDI style.

* Agent downloads (admin "Downloads" page): renamed to LibreVDI file names and descriptions;
  entries whose file does not exist are hidden (upstream lists Linux/macOS packages that a
  LibreVDI installation does not ship).
* Client downloads (portal "Launcher" page): only clients that are actually present are listed.

Installers are published to the upstream locations by ``librevdi_ext.downloads`` before the web
server starts, so the file checks here see the final state.
"""

import dataclasses
import glob
import os
import re

from django.conf import settings
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


def apply() -> None:
    manager = downloads_manager()
    table = getattr(manager, "_downloadables", None)
    if isinstance(table, dict):
        for key in list(table):
            item = table[key]
            if not os.path.isfile(item.path):
                del table[key]
                continue
            item.name = _rebrand(item.name, _NAME_MAP)
            item.description = _rebrand(item.description, _TEXT_MAP)

    clients = sorted(glob.glob(os.path.join(settings.STATIC_ROOT, "clients", "LibreVDI-Client-Setup-*.exe")))
    for i, plugin in enumerate(udsclients_info.PLUGINS):
        if clients and plugin.name == "Windows" and "UDSLauncherInstaller-" in plugin.url:
            udsclients_info.PLUGINS[i] = dataclasses.replace(
                plugin,
                url=plugin.url.rsplit("/", 1)[0] + "/" + os.path.basename(clients[-1]),
                description="LibreVDI Client (Windows)",
            )
    udsclients_info.PLUGINS[:] = [p for p in udsclients_info.PLUGINS if os.path.isfile(_static_file(p.url))]


apply()
