"""LibreVDI branding for the OpenUDS broker, applied once at image build time.

Upstream files under ``uds/`` stay untouched except for the compiled translations; everything
else is written to the collected static files (``STATIC_ROOT``) and to template overrides
(``/app/templates``, searched by Django before the app templates).

1. Images: logo, favicons, login image and the inline loading logo are replaced.
2. Bundles (portal ``modern/`` and admin ``admin/`` main.js): user-visible string literals that
   name UDS are rebranded. Functional identifiers (config section names "UDS", "UDS ID") and the
   upstream copyright notice are kept (BSD-3-Clause); LibreVDI is added next to it.
3. Templates: page title, anti-framing redirect, inline logo; Subresource-Integrity hashes are
   recomputed for every changed file.
4. Translations: all upstream ``.po`` catalogs are rebranded and compiled to ``.mo`` (upstream
   ships none, so the UI was English only). Entries are added for rebranded message ids, so
   translated texts keep working after the bundle change.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import re
import shutil
import sys
from pathlib import Path

PROJECT_URL = "https://github.com/Cautex/LibreVDI"

# Ordered: specific phrases first. Applied to UI strings and translations.
_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bUDS Enterprise\b"), "LibreVDI"),
    (re.compile(r"\bUDS Open Source\b"), "OpenUDS Open Source"),
    (re.compile(r"\bUDS has been developed\b"), "OpenUDS has been developed"),
    (re.compile(r"\bUDS Service launcher\b"), "LibreVDI Client"),
    (re.compile(r"\bUDS([ -])[Ll]auncher\b"), r"LibreVDI\1Client"),
    (re.compile(r"\bUDS([ -])[Aa]ctor\b"), r"LibreVDI\1Agent"),
    (re.compile(r"\bUDS([ -])Akteur\w*"), r"LibreVDI\1Agent"),  # German upstream translation
    (re.compile(r"\bUDS\b"), "LibreVDI"),
    (re.compile(r"\bUds\b"), "LibreVDI"),
]

# String literals that are identifiers, not UI text (admin config sections, WebAuthn RP name)
PROTECTED_LITERALS = {"UDS", "UDS ID"}

# Exact replacements inside the compiled bundles (context needed, or not brand words)
BUNDLE_EXACT: list[tuple[str, str]] = [
    ('this.title="UDS"', 'this.title="LibreVDI"'),
    ('["alt","UDS",', '["alt","LibreVDI",'),
    ('"http://www.udsenterprise.com"', f'"{PROJECT_URL}"'),
    ('"https://www.udsenterprise.com"', f'"{PROJECT_URL}"'),
    ('"\\xA0udsenterprise.com "', '"\\xA0LibreVDI "'),
    ('" Virtual Cable S.L.U."', '" Virtual Cable S.L.U. (OpenUDS) \\xB7 LibreVDI"'),
    ('"Virtual Cable S.L."', '"Virtual Cable S.L. (OpenUDS) \\xB7 LibreVDI"'),
    ('"Universal Desktop Services "', '"LibreVDI \\xB7 OpenUDS "'),
    ('"Universal Desktop Services"', '"LibreVDI"'),
]

_BRAND_WORD = re.compile(r"\bUDS\b|\bUds\b")
_QUOTED = re.compile(r'"((?:[^"\\\n]|\\.)*)"')


def rebrand_text(text: str) -> str:
    for pattern, repl in _RULES:
        text = pattern.sub(repl, text)
    return text


# Hard-coded (not translated) UI texts in the bundles, in addition to the catalog message ids
EXTRA_LITERALS = [
    "UDS Launcher",
    " UDS Launcher ",
    "UDS Service launcher",
    "UDS Enterprise",
    "UDS Admin",
    "In order to increase your access privileges, please contact your local UDS administrator. ",
]


def rebrand_bundle(js: str, candidates: set[str]) -> tuple[str, int, list[str]]:
    """Replaces exactly known string literals (no JS parsing).

    Returns the new source, the number of replaced literals and brand words still found inside
    quotes (for the build log; they may be identifiers, which must not change).
    """
    for old, new in BUNDLE_EXACT:
        js = js.replace(old, new)
    count = 0
    for text in sorted(candidates | set(EXTRA_LITERALS), key=len, reverse=True):
        if text in PROTECTED_LITERALS or not _BRAND_WORD.search(text):
            continue
        quoted = '"' + text + '"'
        n = js.count(quoted)
        if n:
            js = js.replace(quoted, '"' + rebrand_text(text) + '"')
            count += n
    leftovers = sorted(
        {m.group(1) for m in _QUOTED.finditer(js) if _BRAND_WORD.search(m.group(1)) and len(m.group(1)) < 120}
    )
    return js, count, leftovers


def catalog_msgids(locale_dir: Path) -> set[str]:
    """All message ids of the JS catalogs that contain a brand word."""
    import polib  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    ids: set[str] = set()
    for po_path in locale_dir.glob("*/LC_MESSAGES/djangojs.po"):
        ids.update(e.msgid for e in polib.pofile(str(po_path)) if _BRAND_WORD.search(e.msgid))
    return ids


def sri(data: bytes) -> str:
    return "sha384-" + base64.b64encode(hashlib.sha384(data).digest()).decode()


def png_data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


_DATA_URI_LOGO = re.compile(r"(\.app-loading \.logo\s*\{[^}]*?url\()data:image/[a-z+]+;base64,[A-Za-z0-9+/=]+(\))")


def replace_loading_logo(text: str, data_uri: str) -> str:
    return _DATA_URI_LOGO.sub(lambda m: m.group(1) + data_uri + m.group(2), text)


def padded_png(src: Path, size: tuple[int, int]) -> bytes:
    from PIL import Image  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    logo = Image.open(src).convert("RGBA")
    side = min(size)
    logo = logo.resize((side, side), Image.LANCZOS)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.paste(logo, ((size[0] - side) // 2, (size[1] - side) // 2), logo)
    buf = io.BytesIO()
    canvas.save(buf, "PNG")
    return buf.getvalue()


def brand_static(static: Path, assets: Path, candidates: set[str]) -> dict[str, tuple[str, str]]:
    """Images, bundles and stylesheets. Returns {url_path: (old_sri, new_sri)} for changed files."""
    changed: dict[str, tuple[str, str]] = {}
    for app in ("modern", "admin"):
        img = static / app / "img"
        shutil.copyfile(assets / "logo-128.png", img / "udsicon.png")
        shutil.copyfile(assets / "logo-64.png", img / "favicon.png")
        shutil.copyfile(assets / "logo.ico", img / "favicon.ico")
        if (img / "login-img.png").exists():
            from PIL import Image  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

            size = Image.open(img / "login-img.png").size
            (img / "login-img.png").write_bytes(padded_png(assets / "logo-256.png", size))

        main = static / app / "main.js"
        old = main.read_bytes()
        new_js, count, leftovers = rebrand_bundle(old.decode("utf-8"), candidates)
        main.write_text(new_js, encoding="utf-8")
        changed[f"{app}/main.js"] = (sri(old), sri(main.read_bytes()))
        print(f"branding: {app}/main.js – {count} string literals rebranded")
        for item in leftovers:
            print(f"branding: {app}/main.js keeps {item!r}")

        css = static / app / "styles.css"
        old_css = css.read_bytes()
        css.write_text(
            replace_loading_logo(old_css.decode("utf-8"), png_data_uri(assets / "logo-128.png")), encoding="utf-8"
        )
        changed[f"{app}/styles.css"] = (sri(old_css), sri(css.read_bytes()))
    return changed


def brand_templates(src: Path, out: Path, changed: dict[str, tuple[str, str]], assets: Path) -> None:
    logo_uri = png_data_uri(assets / "logo-128.png")
    for app in ("modern", "admin"):
        text = (src / "uds" / app / "index.html").read_text(encoding="utf-8")
        text = text.replace("<title>Uds</title>", "<title>LibreVDI</title>")
        text = text.replace(
            "window.location.href = 'https://www.udsenterprise.com';", "window.location.href = 'about:blank';"
        )
        text = replace_loading_logo(text, logo_uri)
        for old_sri, new_sri in changed.values():
            text = text.replace(f'integrity="{old_sri}"', f'integrity="{new_sri}"')
        target = out / "uds" / app / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        missing = [p for p, (_, new) in changed.items() if p.startswith(app + "/") and new not in text]
        if missing:
            raise SystemExit(f"branding: SRI for {missing} not updated in {app}/index.html (template changed?)")
        print(f"branding: template uds/{app}/index.html written")


def brand_catalogs(locale_dir: Path) -> None:
    import polib  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    for po_path in sorted(locale_dir.glob("*/LC_MESSAGES/*.po")):
        po = polib.pofile(str(po_path))
        additions = []
        for entry in po:
            if entry.obsolete:
                continue
            for key in list(entry.msgstr_plural):
                entry.msgstr_plural[key] = rebrand_text(entry.msgstr_plural[key])
            entry.msgstr = rebrand_text(entry.msgstr)
            branded_id = rebrand_text(entry.msgid)
            if branded_id != entry.msgid and entry.msgid not in PROTECTED_LITERALS:
                if not entry.msgstr:
                    entry.msgstr = branded_id  # untranslated: show branded English text
                additions.append(
                    polib.POEntry(
                        msgid=branded_id,
                        msgid_plural=rebrand_text(entry.msgid_plural) if entry.msgid_plural else "",
                        msgstr=entry.msgstr,
                        msgstr_plural=dict(entry.msgstr_plural),
                        msgctxt=entry.msgctxt,
                    )
                )
        existing = {(e.msgctxt, e.msgid) for e in po}
        for add in additions:
            if (add.msgctxt, add.msgid) not in existing:
                po.append(add)
                existing.add((add.msgctxt, add.msgid))
        po.save(str(po_path))
        po.save_as_mofile(str(po_path.with_suffix(".mo")))
    print(f"branding: translations compiled in {locale_dir}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--static", type=Path, default=Path("/app/static"))
    ap.add_argument("--templates-src", type=Path, default=Path("/app/uds/templates"))
    ap.add_argument("--templates-out", type=Path, default=Path("/app/templates"))
    ap.add_argument("--locale", type=Path, default=Path("/app/uds/locale"))
    ap.add_argument("--assets", type=Path, default=Path("/opt/librevdi/branding"))
    args = ap.parse_args(argv)

    # message ids are read before the catalogs are rebranded
    changed = brand_static(args.static, args.assets, catalog_msgids(args.locale))
    brand_templates(args.templates_src, args.templates_out, changed, args.assets)
    brand_catalogs(args.locale)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
