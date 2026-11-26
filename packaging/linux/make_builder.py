#!/usr/bin/env python3
"""Derives the Docker builders for distributions without an upstream builder from the upstream
Debian 13 builder (``upstream/uds-*/building/linux/builders/Debian13/Dockerfile``), so the FreeRDP
build options and the Rust setup stay those of upstream. Upstream files are not changed.

* Ubuntu 24.04 / 26.04: other base image, ``libusb-1.0-0-dev`` instead of ``libusb-1.0.0-dev``,
  no ``libgio-2.0-dev`` (only a virtual package on 24.04; ``libglib2.0-dev`` provides it)
* Rocky Linux 9 / 10: the apt block becomes a dnf block (EPEL + CRB; FFmpeg from EPEL's
  ``*-free`` packages); FreeRDP is installed into ``/usr/local/lib`` (not ``lib64``, the
  ``FREERDP_ROOT`` link path of the launcher). H.264 is off: OpenH264 is not packaged for
  Enterprise Linux and EPEL's FFmpeg has no H.264 decoder - RDP falls back to the other codecs.
  Rocky 9 (libvpx 1.9) gets a static libvpx (LIBVPX_VERSION) for the launcher.

Usage: make_builder.py client|agent <distro> <Debian13 Dockerfile> <output Dockerfile>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

UBUNTU = {"Ubuntu2404": "ubuntu:24.04", "Ubuntu2604": "ubuntu:26.04"}
ROCKY = {"Rocky9": "9", "Rocky10": "10"}

_COMMON_EL = (
    "curl gcc gcc-c++ make cmake pkgconf-pkg-config openssl-devel mesa-libGL-devel mesa-libGLU-devel "
    "libXft-devel libXext-devel libXinerama-devel libXcursor-devel libXfixes-devel "
    "pango-devel cairo-devel glib2-devel rpm-build"
)
EL_PACKAGES = {
    "client": _COMMON_EL + " ninja-build nasm git alsa-lib-devel pulseaudio-libs-devel clang-devel turbojpeg-devel"
    " libavcodec-free-devel libavutil-free-devel libswscale-free-devel libavformat-free-devel"
    " libswresample-free-devel krb5-devel cups-devel fuse3-devel pcsc-lite-devel libvpx-devel opus-devel",
    "agent": _COMMON_EL + " libstdc++-static",
}
LIBVPX_VERSION = "1.14.1"
LIBVPX_REPO = "https://chromium.googlesource.com/webm/libvpx"
LIBVPX_STEP = (
    f"RUN git clone --branch v{LIBVPX_VERSION} --depth 1 {LIBVPX_REPO} /libvpx-build \\\n"
    "  && cd /libvpx-build \\\n"
    "  && ./configure --prefix=/usr/local --enable-pic --disable-examples --disable-tools --disable-docs"
    " --disable-unit-tests \\\n"
    '  && make -j"$(nproc)" && make install && cd / && rm -rf /libvpx-build\n'
    "ENV PKG_CONFIG_PATH=/usr/local/lib/pkgconfig\n\n"
)
APT_BLOCK = re.compile(r"^RUN apt-get update && apt-get install -y \\\n.*?rm -rf /var/lib/apt/lists/\*\n", re.M | re.S)


def ubuntu(text: str, image: str) -> str:
    text = re.sub(r"^FROM debian:\S+", f"FROM {image}", text, count=1, flags=re.M)
    text = text.replace("libusb-1.0.0-dev", "libusb-1.0-0-dev")
    return text.replace(" libgio-2.0-dev", "")


def rocky(text: str, version: str, component: str) -> str:
    text = re.sub(r"^FROM debian:\S+", f"FROM rockylinux/rockylinux:{version}", text, count=1, flags=re.M)
    packages = " \\\n    ".join(_wrap(EL_PACKAGES[component]))
    dnf = (
        "RUN dnf install -y epel-release dnf-plugins-core \\\n"
        "  && crb enable \\\n"
        f"  && dnf install -y --allowerasing \\\n    {packages} \\\n"
        "  && (dnf install -y libusbx-devel || dnf install -y libusb1-devel) \\\n"
        "  && dnf clean all\n"
    )
    if component == "agent":
        dnf = dnf.replace("  && (dnf install -y libusbx-devel || dnf install -y libusb1-devel) \\\n", "")
    text, n = APT_BLOCK.subn(lambda _m: dnf, text, count=1)
    if n != 1:
        raise SystemExit("make_builder: apt block not found in the Debian 13 Dockerfile (upstream changed?)")
    if component == "client" and version == "9":
        # vpx-sys (launcher) needs libvpx >= 1.10, Rocky 9 ships 1.9: static build, linked into the
        # launcher (nothing extra to install on the desktop; license in THIRD-PARTY-NOTICES)
        text = text.replace(" libvpx-devel", "")
        marker = "WORKDIR /freerdp-build\n"
        if marker not in text:
            raise SystemExit("make_builder: FreeRDP build step not found (upstream changed?)")
        text = text.replace(marker, LIBVPX_STEP + marker, 1)
    if component == "client":
        for old, new in (
            (
                "-DCMAKE_INSTALL_PREFIX=${FREERDP_ROOT} \\",
                "-DCMAKE_INSTALL_PREFIX=${FREERDP_ROOT} \\\n  -DCMAKE_INSTALL_LIBDIR=lib \\",
            ),
            ("-DWITH_OPENH264=ON", "-DWITH_OPENH264=OFF"),
            ("-DWITH_GFX_H264=ON", "-DWITH_GFX_H264=OFF"),
        ):
            if old not in text:
                raise SystemExit(f"make_builder: {old!r} not found in the Debian 13 Dockerfile (upstream changed?)")
            text = text.replace(old, new, 1)
    return text


def _wrap(words: str, width: int = 90) -> list[str]:
    lines, line = [], ""
    for word in words.split():
        if line and len(line) + len(word) + 1 > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return [*lines, line] if line else lines


def derive(component: str, distro: str, text: str) -> str:
    if distro in UBUNTU:
        return ubuntu(text, UBUNTU[distro])
    if distro in ROCKY:
        return rocky(text, ROCKY[distro], component)
    raise SystemExit(f"make_builder: no rule for {distro}")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 4 or args[0] not in ("client", "agent"):
        print(__doc__, file=sys.stderr)
        return 2
    component, distro, src, out = args
    result = derive(component, distro, Path(src).read_text(encoding="utf-8"))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(result, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
