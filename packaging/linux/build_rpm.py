#!/usr/bin/env python3
"""Packages the binaries built by the upstream ``rustbuilder.py`` as LibreVDI RPMs (Rocky Linux).

Upstream builds RPMs only for Fedora/openSUSE (``udslauncher.spec``, ``udsactor*.spec``; ``%files``
owns all of ``/usr`` and ``/etc``). For Enterprise Linux LibreVDI writes its own spec:

1. ``make install-…`` of the upstream Makefile into a staging root (same files as the .deb)
2. systemd unit for the agent (the upstream Makefile installs it only for Fedora/openSUSE)
3. rebranding via ``rebrand_deb.rebrand_files`` (texts, icon, extra files, license notices)
4. spec with an explicit file list, ``Provides``/``Obsoletes`` of the upstream name, the bundled
   FreeRDP libraries excluded from automatic provides/requires
5. ``rpmbuild`` inside the distribution's builder image

Usage: build_rpm.py client|agent Rocky9|Rocky10 <version, e.g. 0.1.0~dev.5> <outdir>
           [--notices FILE] [--icon FILE]
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rebrand_deb  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
CONFIGURE_TOOL = REPO / "packaging" / "linux" / "librevdi-agent-configure"

# name, upstream package, make target, summary
PACKAGES = {
    "client": [
        (
            "librevdi-client",
            "udslauncher",
            "install-udslauncher",
            "LibreVDI Client - connects to LibreVDI virtual desktops",
        ),
    ],
    "agent": [
        ("librevdi-agent", "udsactor", "install-udsactor", "LibreVDI Agent (managed) for cloned desktops"),
        (
            "librevdi-agent-unmanaged",
            "udsactor-unmanaged",
            "install-udsactor-unmanaged",
            "LibreVDI Agent (unmanaged) for persistent desktops",
        ),
    ],
}
PRIVATE_DIRS = ("/usr/share/udslauncher", "/usr/share/udsactor")

AGENT_SCRIPTS = """
%post
mkdir -p /etc/udsactor && chmod 0700 /etc/udsactor
if [ -x /usr/bin/systemctl ]; then
    systemctl daemon-reload >/dev/null 2>&1 || :
    systemctl enable udsactor.service >/dev/null 2>&1 || :
fi

%preun
if [ $1 -eq 0 ] && [ -x /usr/bin/systemctl ]; then
    systemctl disable --now udsactor.service >/dev/null 2>&1 || :
fi

%postun
if [ -x /usr/bin/systemctl ]; then
    systemctl daemon-reload >/dev/null 2>&1 || :
fi
if [ $1 -eq 0 ]; then
    rm -rf /etc/udsactor
fi
"""
CLIENT_SCRIPTS = """
%post
update-desktop-database -q /usr/share/applications >/dev/null 2>&1 || :
update-mime-database /usr/share/mime >/dev/null 2>&1 || :

%postun
update-desktop-database -q /usr/share/applications >/dev/null 2>&1 || :
update-mime-database /usr/share/mime >/dev/null 2>&1 || :
"""


def file_list(root: Path, name: str) -> list[str]:
    own_dirs = (*PRIVATE_DIRS, f"/usr/share/doc/{name}")
    entries = []
    for path in sorted(root.rglob("*")):
        rel = "/" + path.relative_to(root).as_posix()
        if path.is_dir() and not path.is_symlink():
            if any(rel == d or rel.startswith(d + "/") for d in own_dirs):
                entries.append(f"%dir {rel}")
        else:
            entries.append(rel)
    return entries


def spec(
    component: str, name: str, upstream: str, version: str, summary: str, root: str, files: list[str], others: list[str]
) -> str:
    lines = [
        f"Name: {name}",
        f"Version: {version}",
        "Release: 1%{?dist}",
        f"Summary: {summary}",
        "License: BSD-3-Clause",
        f"URL: {rebrand_deb.PROJECT_URL}",
        "Vendor: LibreVDI",
        f"Provides: {upstream} = %{{version}}-%{{release}}",
        f"Obsoletes: {upstream} < 100",  # every upstream 5.x/6.x version
        *(f"Conflicts: {other}" for other in others),
        "",
        "%global debug_package %{nil}",
        "%global __brp_check_rpaths %{nil}",
        # bundled FreeRDP libraries: neither provided to the system nor required from it
        "%global __provides_exclude_from ^/usr/share/(udslauncher|udsactor)/.*$",
        r"%global __requires_exclude ^lib(freerdp|freerdp-client|winpr|winpr-tools|rdtk|uwac)[0-9]*\.so.*$",
    ]
    if component == "agent":
        lines += ["Requires: libXScrnSaver", "Recommends: xset"]
    lines += [
        "",
        "%description",
        f"{summary}.",
        "Based on OpenUDS (BSD-3-Clause, (c) Virtual Cable S.L.).",
        "",
        "%prep",
        "%build",
        "%install",
        "mkdir -p %{buildroot}",
        f"cp -a {root}/. %{{buildroot}}/",
        "",
        "%files",
        "%defattr(-,root,root,-)",
        *files,
    ]
    return "\n".join(lines) + "\n" + (AGENT_SCRIPTS if component == "agent" else CLIENT_SCRIPTS)


def run(cmd: list[str], **kwargs: object) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, **kwargs)  # noqa: S603 - fixed argument lists


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("component", choices=sorted(PACKAGES))
    ap.add_argument("distro")
    ap.add_argument("version")
    ap.add_argument("outdir", type=Path)
    ap.add_argument("--notices", type=Path)
    ap.add_argument("--icon", type=Path, default=REPO / "branding" / "logo-256.png")
    args = ap.parse_args(argv)

    crate = REPO / "upstream" / ("uds-client" if args.component == "client" else "uds-actor")
    build_dir = crate / "building" / "linux"
    image = f"rust-builder-{'udslauncher' if args.component == 'client' else 'udsactor'}:{args.distro}"
    names = [p[0] for p in PACKAGES[args.component]]
    args.outdir.mkdir(parents=True, exist_ok=True)

    for name, upstream, target, summary in PACKAGES[args.component]:
        work = build_dir / f"rpm-{args.distro}-{name}"
        shutil.rmtree(work, ignore_errors=True)
        root = work / "root"
        root.mkdir(parents=True)
        run(["make", "-s", "-C", str(build_dir), target, "IN_DOCKER=1", f"DISTRO={args.distro}", f"DESTDIR={root}"])
        if args.component == "agent":
            unit = root / "usr" / "lib" / "systemd" / "system" / "udsactor.service"
            unit.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(build_dir / "debian" / "udsactor.service", unit)
        extra = []
        if args.notices:
            extra.append(f"{args.notices}:/usr/share/doc/{name}/THIRD-PARTY-NOTICES.txt:0644")
        if name == "librevdi-agent-unmanaged":
            extra.append(f"{CONFIGURE_TOOL}:/usr/sbin/librevdi-agent-configure")
        rebrand_deb.rebrand_files(root, name, args.icon, extra)

        in_container = "/crate/" + work.relative_to(crate).as_posix()
        others = [n for n in names if n != name]
        spec_text = spec(
            args.component, name, upstream, args.version, summary, f"{in_container}/root", file_list(root, name), others
        )
        (work / f"{name}.spec").write_text(spec_text, encoding="utf-8")
        run(
            [
                "docker", "run", "--rm", "-v", f"{crate}:/crate", image, "sh", "-c",
                f"rpmbuild -bb --define '_topdir {in_container}/rpmbuild' {in_container}/{name}.spec"
                f" && chown -R {os.getuid()}:{os.getgid()} {in_container}",
            ]
        )  # fmt: skip
        built = sorted((work / "rpmbuild" / "RPMS").rglob(f"{name}-*.rpm"))
        if not built:
            raise SystemExit(f"build_rpm: no RPM produced for {name}")
        out = args.outdir / f"{name}-{args.version}.x86_64-{args.distro.lower()}.rpm"
        shutil.copyfile(built[-1], out)
        print(f"build_rpm: {built[-1].name} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
