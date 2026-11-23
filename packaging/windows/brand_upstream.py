"""Applies LibreVDI branding to the upstream Rust sources before a Windows build (CI only).

Works on a checkout of ``upstream/uds-client`` or ``upstream/uds-actor`` in place:

* user-visible string literals (window titles, about box, service display name, dialogs)
* Windows file metadata (product name, company, copyright) set by the shared ``builder`` crate
* icons and images in ``assets/img`` (same file names and sizes, LibreVDI logo)
* client translations (``locales/*/LC_MESSAGES/*.po``) rebranded and recompiled to ``.mo``

The Windows service is renamed to ``LibreVDIAgent``; the old name ``UDSActorService`` is added to
the agent's legacy list, so installing over an older agent removes the old service.
Technical identifiers stay untouched: environment variables, the agent's ``"UDS Actor v"`` user
agent that the broker parses, registry paths.
The upstream copyright remains (BSD-3-Clause); LibreVDI is added.

Every expected replacement must match at least once – otherwise the script fails, so upstream
changes are noticed instead of silently shipping a half-branded binary.

Usage: python brand_upstream.py client|agent <path-to-upstream-repo> <path-to-branding-dir>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_URL = "https://github.com/Cautex/LibreVDI"
COPYRIGHT = "LibreVDI contributors; OpenUDS (c) Virtual Cable S.L. (BSD-3-Clause)"

# (old, new): exact text, replaced in *.rs files of the repository
CLIENT_TEXT: list[tuple[str, str]] = [
    ('"About UDS Launcher"', '"About LibreVDI Client"'),
    ('"UDS Launcher Application"', '"LibreVDI Client"'),
    ('"UDS Connection Launcher"', '"LibreVDI Client (based on OpenUDS)"'),
    ('"Developed by Virtual Cable S.L."', '"Based on OpenUDS by Virtual Cable S.L. (BSD-3-Clause)"'),
    ('"https://www.udsenterprise.com"', f'"{PROJECT_URL}"'),
    ('"UDS Alert"', '"LibreVDI"'),
    ('"UDS Connection (always on)"', '"LibreVDI (always on)"'),
    ('"UDS Connection"', '"LibreVDI"'),
    ('"UDS Launcher"', '"LibreVDI Client"'),
    ("Only approve UDS servers you trust.", "Only approve LibreVDI servers you trust."),
]

AGENT_TEXT: list[tuple[str, str]] = [
    # service key name (shown in Task Manager / sc.exe); must stay identical in both places
    ('"UDSActorService"', '"LibreVDIAgent"'),
    ('&["UDSActorNG", "UDSActor"]', '&["UDSActorNG", "UDSActor", "UDSActorService"]'),
    ('"UDS Actor Unmanaged Configuration"', '"LibreVDI Agent Configuration (unmanaged)"'),
    ('"UDS Actor Configuration"', '"LibreVDI Agent Configuration"'),
    ('"UDS Actor (Unmanaged)"', '"LibreVDI Agent (unmanaged)"'),
    ('"UDS Actor Config Unmanaged"', '"LibreVDI Agent Configuration (unmanaged)"'),
    ('"UDS Actor Config"', '"LibreVDI Agent Configuration"'),
    ('"UDS Actor Client"', '"LibreVDI Agent Client"'),
    ('"UDS Actor Management Service"', '"LibreVDI Agent (based on OpenUDS)"'),
    ('"UDS Actor Service"', '"LibreVDI Agent"'),  # service display name + event log source
    ('"UDS Actor"', '"LibreVDI Agent"'),
    ('"UDS Broker Host:"', '"LibreVDI Broker:"'),
    (
        '"Please register with UDS before testing the connection"',
        '"Please register with LibreVDI before testing the connection"',
    ),
]

# Windows resources written by the shared builder crate (both repositories, slightly different text)
BUILDER_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r'res\.set\("CompanyName", "Virtual Cable S\.L\.(?:U\.)?"\);'), 'res.set("CompanyName", "LibreVDI");'),
    (
        re.compile(r'format!\("Copyright © 2012-\{current_year\} Virtual Cable S\.L\.(?:U\.)?"\)'),
        'format!("Copyright © {current_year} ' + COPYRIGHT + '")',
    ),
]

_PO_RULES = [
    (re.compile(r"\bUDS([ -])[Ll]auncher\b"), r"LibreVDI\1Client"),
    (re.compile(r"\bUDS\b"), "LibreVDI"),
]


def replace_in_sources(repo: Path, mapping: list[tuple[str, str]], label: str) -> None:
    files = [p for p in repo.glob("crates/**/*.rs") if "target" not in p.parts]
    contents = {p: p.read_text(encoding="utf-8") for p in files}
    for old, new in mapping:
        hits = 0
        for path, text in contents.items():
            if old in text:
                contents[path] = text.replace(old, new)
                hits += text.count(old)
        if not hits:
            raise SystemExit(f"brand_upstream: {label}: expected text not found: {old}")
        print(f"brand_upstream: {label}: {hits}x {old[:60]}")
    for path, text in contents.items():
        if text != path.read_text(encoding="utf-8"):
            path.write_text(text, encoding="utf-8")


def replace_builder(repo: Path) -> None:
    for path in repo.glob("crates/builder/src/*.rs"):
        text = path.read_text(encoding="utf-8")
        for pattern, repl in BUILDER_RULES:
            text, n = pattern.subn(repl, text)
            if not n:
                raise SystemExit(f"brand_upstream: builder: pattern not found in {path}: {pattern.pattern}")
        path.write_text(text, encoding="utf-8")
        print(f"brand_upstream: builder metadata {path.relative_to(repo)}")


def replace_images(repo: Path, branding: Path) -> None:
    from PIL import Image  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    logo = Image.open(branding / "logo-512.png").convert("RGBA")
    # assets/img (exe icons, installers) and crate-embedded logos, e.g. the agent configuration
    # window (crates/gui-kit/assets/uds-128.png, include_bytes!). Only the logo files ("uds*").
    files = sorted(p for p in (repo / "assets" / "img").iterdir())
    files += sorted(p for p in repo.glob("crates/*/assets/uds*") if p.is_file())
    for path in files:
        if path.suffix.lower() == ".ico":
            logo.save(path, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
        elif path.suffix.lower() in (".png", ".bmp"):
            with Image.open(path) as current:
                size, mode = current.size, current.mode
            side = min(size)
            canvas = Image.new("RGBA", size, (255, 255, 255, 0 if path.suffix.lower() == ".png" else 255))
            scaled = logo.resize((side, side), Image.LANCZOS)
            canvas.paste(scaled, ((size[0] - side) // 2, (size[1] - side) // 2), scaled)
            out = canvas if path.suffix.lower() == ".png" else canvas.convert("RGB")
            if path.suffix.lower() == ".png" and mode not in ("RGBA", "LA"):
                out = canvas.convert(mode if mode in ("RGB", "L", "P") else "RGBA")
            out.save(path)
        else:
            continue
        print(f"brand_upstream: image {path.relative_to(repo)}")


def rebrand_po(text: str) -> str:
    for pattern, repl in _PO_RULES:
        text = pattern.sub(repl, text)
    return text


def replace_translations(repo: Path) -> None:
    import polib  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    for po_path in sorted(repo.glob("crates/**/locales/*/LC_MESSAGES/*.po")):
        po = polib.pofile(str(po_path))
        for entry in po:
            entry.msgid = rebrand_po(entry.msgid)
            entry.msgstr = rebrand_po(entry.msgstr)
        po.save(str(po_path))
        po.save_as_mofile(str(po_path.with_suffix(".mo")))
        print(f"brand_upstream: translations {po_path.relative_to(repo)}")


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[0] not in ("client", "agent"):
        print(__doc__)
        return 2
    kind, repo, branding = argv[0], Path(argv[1]), Path(argv[2])
    replace_in_sources(repo, CLIENT_TEXT if kind == "client" else AGENT_TEXT, kind)
    replace_builder(repo)
    replace_images(repo, branding)
    if kind == "client":
        replace_translations(repo)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
