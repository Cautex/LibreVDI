#!/usr/bin/env python3
"""Collects third-party license notices for a Windows build (agent or client).

Writes one plain-text file ``THIRD-PARTY-NOTICES.txt`` that ships inside the installer and as a
release asset, and a Markdown summary table (``--summary``).

Sources:

* Rust crates linked into the binaries: ``cargo metadata`` of the upstream workspace, walking only
  normal (runtime) dependencies of the workspace members (dev and build dependencies are not
  shipped). License texts are taken from the files each crate ships (LICENSE*, COPYING*, NOTICE*).
* native libraries from vcpkg (``--vcpkg-installed DIR --vcpkg-port NAME``): vcpkg stores each
  port's license text in ``<installed>/<triplet>/share/<port>/copyright``.
* further components (``--extra "Name|SPDX|path-to-license-file"``), e.g. FreeRDP.

Usage:
  collect_licenses.py --cargo-dir upstream/uds-actor --out out/THIRD-PARTY-NOTICES.txt \
      --summary out/third-party.md --title "LibreVDI Agent"
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field

LICENSE_PREFIXES = ("license", "licence", "copying", "notice", "copyright", "unlicense")
TARGET = "x86_64-pc-windows-msvc"


@dataclass
class Component:
    name: str
    version: str
    license: str
    source: str
    texts: list[tuple[str, str]] = field(default_factory=list)  # (file name, content)
    authors: list[str] = field(default_factory=list)


def read_text(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read().strip()


def license_files(directory: str) -> list[str]:
    if not os.path.isdir(directory):
        return []
    return sorted(
        os.path.join(directory, name)
        for name in os.listdir(directory)
        if name.lower().startswith(LICENSE_PREFIXES) and os.path.isfile(os.path.join(directory, name))
    )


def runtime_packages(metadata: dict, roots: list[str] | None = None) -> list[dict]:
    """Packages reachable from the workspace members via normal dependencies only."""
    nodes = {node["id"]: node for node in metadata["resolve"]["nodes"]}
    packages = {pkg["id"]: pkg for pkg in metadata["packages"]}
    members = set(metadata["workspace_members"])
    start = [pid for pid in members if not roots or packages[pid]["name"] in roots]
    seen: set[str] = set()
    stack = list(start)
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        for dep in nodes.get(pid, {}).get("deps", []):
            kinds = {k.get("kind") for k in dep.get("dep_kinds", [])}
            if None in kinds:  # normal dependency (None) -> linked into the binary
                stack.append(dep["pkg"])
    return sorted(
        (packages[pid] for pid in seen if pid not in members),
        key=lambda p: (p["name"], p["version"]),
    )


def cargo_components(cargo_dir: str, roots: list[str] | None) -> list[Component]:
    raw = subprocess.run(  # noqa: S603 - fixed argument list
        ["cargo", "metadata", "--format-version", "1", "--locked", "--filter-platform", TARGET],  # noqa: S607
        cwd=cargo_dir,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",  # Windows default would be the ANSI code page
    ).stdout
    result = []
    for pkg in runtime_packages(json.loads(raw), roots):
        crate_dir = os.path.dirname(pkg["manifest_path"])
        src = pkg.get("source") or ""
        top = None  # directory up to which license files of the enclosing repository are inherited
        if not src:  # path dependency inside the upstream source tree
            top = os.path.abspath(cargo_dir)
            source = "OpenUDS source tree: " + os.path.relpath(crate_dir, os.path.dirname(top))
        elif src.startswith("git+"):  # git dependency: ~/.cargo/git/checkouts/<repo>/<rev>/...
            url, _, rev = src[4:].partition("#")
            source = f"{url.split('?')[0]} (revision {rev})"
            parts = crate_dir.split(os.sep)
            if "checkouts" in parts:
                top = os.sep.join(parts[: parts.index("checkouts") + 3])
        else:
            source = pkg.get("repository") or f"https://crates.io/crates/{pkg['name']}"
        comp = Component(
            name=pkg["name"],
            version=pkg["version"],
            license=pkg.get("license") or "see license file",
            source=source,
            authors=pkg.get("authors") or [],
        )
        files = license_files(crate_dir)
        parent = crate_dir
        while not files and top and parent != top and parent.startswith(top):
            parent = os.path.dirname(parent)
            files = license_files(parent)
        if pkg.get("license_file"):
            files.append(os.path.join(crate_dir, pkg["license_file"]))
        for path in dict.fromkeys(files):  # keep order, drop duplicates
            if os.path.isfile(path):
                comp.texts.append((os.path.basename(path), read_text(path)))
        result.append(comp)
    return result


def vcpkg_components(installed: str, ports: list[str]) -> list[Component]:
    result = []
    triplets = sorted(d for d in os.listdir(installed) if os.path.isdir(os.path.join(installed, d, "share")))
    if "*" in ports:  # every installed library port (vcpkg-* ports are build helpers, not shipped)
        ports = sorted(
            {
                port
                for t in triplets
                for port in os.listdir(os.path.join(installed, t, "share"))
                if not port.startswith("vcpkg-")
                and os.path.isfile(os.path.join(installed, t, "share", port, "copyright"))
            }
        )
    for port in ports:
        for triplet in triplets:
            share = os.path.join(installed, triplet, "share", port)
            copyright_file = os.path.join(share, "copyright")
            if not os.path.isfile(copyright_file):
                continue
            version = "?"
            spdx = os.path.join(share, "vcpkg.spdx.json")
            license_id = "see license text"
            if os.path.isfile(spdx):
                with open(spdx, encoding="utf-8") as f:
                    doc = json.load(f)
                for p in doc.get("packages", []):
                    if p.get("name") == port:
                        version = p.get("versionInfo", version)
                        concluded = p.get("licenseConcluded") or p.get("licenseDeclared")
                        if concluded and concluded != "NOASSERTION":
                            license_id = concluded
                        break
            result.append(
                Component(
                    name=port,
                    version=version,
                    license=license_id,
                    source=f"vcpkg port '{port}' ({triplet})",
                    texts=[("copyright", read_text(copyright_file))],
                )
            )
            break
        else:
            raise SystemExit(f"vcpkg port {port!r} not found below {installed}")
    return result


def extra_component(spec: str) -> Component:
    try:
        name, license_id, path = spec.split("|", 2)
    except ValueError:
        raise SystemExit(f"--extra must be 'Name|SPDX|path', got {spec!r}") from None
    if not os.path.isfile(path):
        raise SystemExit(f"license file for {name} not found: {path}")
    return Component(
        name=name, version="", license=license_id, source="", texts=[(os.path.basename(path), read_text(path))]
    )


# Standard texts for crates that publish no license file: taken from the first crate that ships them
STANDARD_TEXTS = (
    ("Apache-2.0", ("license-apache", "license-apache-2.0", "license-apache2")),
    ("MIT", ("license-mit",)),
)


def standard_texts(components: list[Component], fallbacks: dict[str, str] | None = None) -> dict[str, str]:
    found: dict[str, str] = dict(fallbacks or {})
    for spdx, names in STANDARD_TEXTS:
        if spdx in found:
            continue
        for c in components:
            text = next((t for f, t in c.texts if f.lower().split(".")[0] in names), None)
            if text:
                found[spdx] = text
                break
    return found


def render_notices(title: str, components: list[Component], fallbacks: dict[str, str] | None = None) -> str:
    out = [
        f"{title} - third-party software notices",
        "=" * 72,
        "",
        "This program contains the following third-party components. Each is distributed under",
        "its own license, reproduced below. Libraries under the LGPL are shipped as separate,",
        "replaceable DLLs.",
        "",
    ]
    for c in components:
        out.append(f"  {c.name} {c.version}".rstrip() + f"  [{c.license}]")
    for c in components:
        out += ["", "-" * 72, f"{c.name} {c.version}".rstrip(), f"License: {c.license}"]
        if c.source:
            out.append(f"Source: {c.source}")
        if c.authors:
            out.append("Authors: " + ", ".join(c.authors))
        if not c.texts:
            out.append("(this component publishes no license file; the standard text of the license above")
            out.append(" is reproduced in the appendix, copyright held by the authors listed)")
        for fname, text in c.texts:
            out += ["", f"--- {fname} ---", text]
    if any(not c.texts for c in components):
        for spdx, text in standard_texts(components, fallbacks).items():
            out += ["", "=" * 72, f"Appendix: standard {spdx} license text", "=" * 72, "", text]
    return "\n".join(out) + "\n"


def render_summary(title: str, components: list[Component]) -> str:
    out = [f"## {title}", "", "| Component | Version | License |", "|---|---|---|"]
    out += [f"| {c.name} | {c.version} | {c.license} |" for c in components]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--title", required=True)
    ap.add_argument("--cargo-dir", required=True)
    ap.add_argument("--root", action="append", help="only these workspace packages (default: all members)")
    ap.add_argument("--vcpkg-installed")
    ap.add_argument("--vcpkg-port", action="append", default=[])
    ap.add_argument("--extra", action="append", default=[])
    ap.add_argument(
        "--fallback-text",
        action="append",
        default=[],
        metavar="SPDX=PATH",
        help="license text for the appendix, e.g. BSD-3-Clause=upstream/uds-client/LICENSE",
    )
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary")
    args = ap.parse_args(argv)

    fallbacks = {}
    for spec in args.fallback_text:
        spdx, _, path = spec.partition("=")
        if not path or not os.path.isfile(path):
            ap.error(f"--fallback-text: file not found in {spec!r}")
        fallbacks[spdx] = read_text(path)
    components = [extra_component(spec) for spec in args.extra]
    if args.vcpkg_port:
        if not args.vcpkg_installed:
            ap.error("--vcpkg-port needs --vcpkg-installed")
        components += vcpkg_components(args.vcpkg_installed, args.vcpkg_port)
    components += cargo_components(args.cargo_dir, args.root)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(render_notices(args.title, components, fallbacks))
    if args.summary:
        with open(args.summary, "w", encoding="utf-8") as f:
            f.write(render_summary(args.title, components))
    missing = [c.name for c in components if not c.texts]
    print(f"{args.title}: {len(components)} components, {len(missing)} without license file")
    if missing:
        print("  without license file: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
