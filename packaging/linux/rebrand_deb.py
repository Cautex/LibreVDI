#!/usr/bin/env python3
"""Repackages an upstream OpenUDS .deb (udslauncher, udsactor, udsactor-unmanaged) as LibreVDI.

The upstream build stays untouched (ADR-0008, level 4); only the finished package is changed:

* control: package name, version, maintainer, homepage, description; ``Provides``/``Conflicts``/
  ``Replaces`` the upstream name, so an installed upstream package is replaced cleanly
* visible texts in desktop entries, autostart entries, systemd units, polkit policies and MIME
  definitions ("UDS Launcher" -> "LibreVDI Client", "UDS Actor" -> "LibreVDI Agent", ...)
* desktop entries without an icon of their own get the LibreVDI icon
* extra LibreVDI files (``--add-file src:/path/in/package[:mode]``, default 0755), e.g. the
  command line configuration tool of the agent or the third-party license notices
* ``DEBIAN/md5sums`` regenerated

Technical names stay (binaries, paths such as /usr/share/udslauncher, systemd unit file names), so
the maintainer scripts of the upstream package keep working.

Usage: rebrand_deb.py <in.deb> <out-dir> --name librevdi-client --version 0.1.0~dev.21 \
           --description "LibreVDI Client ..." [--suffix debian13] [--icon path.png]
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_URL = "https://github.com/Cautex/LibreVDI"
MAINTAINER = "LibreVDI <librevdi@users.noreply.github.com>"

TEXT_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bUDS[ -]Launcher\b"), "LibreVDI Client"),
    (re.compile(r"\bUDS VDI Launcher\b"), "LibreVDI Client"),
    (re.compile(r"\bUDS[ -]Actor\b"), "LibreVDI Agent"),
    (re.compile(r"\bUniversal Desktop Services \(UDS\)"), "LibreVDI"),
    (re.compile(r"\bUDS\b"), "LibreVDI"),
]
# files whose visible texts are rebranded (paths inside the package)
TEXT_FILE = re.compile(r"\.(desktop|service|policy|xml)$")


def rebrand_text(text: str) -> str:
    for pattern, repl in TEXT_RULES:
        text = pattern.sub(repl, text)
    return text


def parse_control(text: str) -> list[tuple[str, str]]:
    """Ordered (field, value) pairs; continuation lines stay part of the value."""
    fields: list[tuple[str, str]] = []
    for line in text.splitlines():
        if line.startswith((" ", "\t")) and fields:
            name, value = fields[-1]
            fields[-1] = (name, value + "\n" + line)
        elif ":" in line:
            name, value = line.split(":", 1)
            fields.append((name.strip(), value.strip()))
    return fields


def render_control(fields: list[tuple[str, str]]) -> str:
    return "".join(f"{name}: {value}\n" for name, value in fields)


def rebrand_control(text: str, name: str, version: str, description: str) -> str:
    fields = dict(parse_control(text))
    original = fields.get("Package", "")
    out: list[tuple[str, str]] = []
    for field, value in parse_control(text):
        if field == "Package":
            value = name
        elif field == "Version":
            value = version
        elif field == "Maintainer":
            value = MAINTAINER
        elif field == "Homepage":
            value = PROJECT_URL
        elif field == "Description":
            summary, _, _rest = description.partition("\n")
            value = summary + "\n Based on OpenUDS (BSD-3-Clause, (c) Virtual Cable S.L.)."
        elif field in ("Provides", "Conflicts", "Replaces"):
            continue  # set below
        out.append((field, value))
    if original and original != name:
        out.append(("Provides", original))
        out.append(("Conflicts", original))
        out.append(("Replaces", original))
    return render_control(out)


def set_desktop_icon(text: str, icon: str) -> str:
    if re.search(r"^Icon=(help-browser|)$", text, re.M) or "Icon=" not in text:
        if "Icon=" in text:
            return re.sub(r"^Icon=.*$", f"Icon={icon}", text, flags=re.M)
        return text.replace("[Desktop Entry]\n", f"[Desktop Entry]\nIcon={icon}\n", 1)
    return text


def regenerate_md5sums(root: Path) -> None:
    lines = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if rel.parts[0] == "DEBIAN" or not path.is_file() or path.is_symlink():
            continue
        lines.append(f"{hashlib.md5(path.read_bytes()).hexdigest()}  {rel.as_posix()}\n")  # noqa: S324 - dpkg format
    (root / "DEBIAN" / "md5sums").write_text("".join(lines), encoding="utf-8")


def add_files(root: Path, specs: list[str]) -> None:
    """``src:/dest`` (executable, 0755) or ``src:/dest:0644``."""
    for spec in specs:
        src, sep, rest = spec.partition(":")
        dest, _, mode = rest.partition(":")
        if not sep or not dest.startswith("/"):
            raise SystemExit(f"--add-file expects src:/absolute/path[:mode], got {spec!r}")
        target = root / dest.lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
        os.chmod(target, int(mode or "0755", 8))


def rebrand_tree(
    root: Path, name: str, version: str, description: str, icon_src: Path | None, extra: list[str] | None = None
) -> None:
    add_files(root, extra or [])
    control = root / "DEBIAN" / "control"
    control.write_text(rebrand_control(control.read_text(encoding="utf-8"), name, version, description), "utf-8")

    icon_target = None
    if icon_src is not None:
        icon_dir = root / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps"
        icon_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(icon_src, icon_dir / f"{name}.png")
        icon_target = name

    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if rel.parts[0] == "DEBIAN" or not path.is_file() or path.is_symlink() or not TEXT_FILE.search(path.name):
            continue
        text = path.read_text(encoding="utf-8")
        new = rebrand_text(text)
        if path.suffix == ".desktop" and icon_target:
            new = set_desktop_icon(new, icon_target)
        if new != text:
            path.write_text(new, encoding="utf-8")
    regenerate_md5sums(root)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deb", type=Path)
    ap.add_argument("outdir", type=Path)
    ap.add_argument("--name", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--description", required=True)
    ap.add_argument("--suffix", default="", help="file name suffix, e.g. debian13")
    ap.add_argument("--icon", type=Path)
    ap.add_argument(
        "--add-file", action="append", default=[], metavar="SRC:/DEST", help="add a file (default mode 0755)"
    )
    args = ap.parse_args(argv)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "pkg"
        subprocess.run(["dpkg-deb", "-R", str(args.deb), str(root)], check=True)  # noqa: S603, S607
        rebrand_tree(root, args.name, args.version, args.description, args.icon, args.add_file)
        arch = dict(parse_control((root / "DEBIAN" / "control").read_text(encoding="utf-8"))).get("Architecture", "all")
        suffix = f"-{args.suffix}" if args.suffix else ""
        args.outdir.mkdir(parents=True, exist_ok=True)
        out = args.outdir / f"{args.name}_{args.version}_{arch}{suffix}.deb"
        os.chmod(root / "DEBIAN", 0o755)  # noqa: S103 - dpkg-deb requires 0755 for DEBIAN
        subprocess.run(["dpkg-deb", "--root-owner-group", "-Zxz", "-b", str(root), str(out)], check=True)  # noqa: S603, S607
    print(f"rebrand_deb: {args.deb.name} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
