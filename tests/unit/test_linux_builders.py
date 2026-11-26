import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packaging", "linux"))
import build_rpm
import make_builder

UPSTREAM = Path(__file__).resolve().parents[2] / "upstream"
CLIENT = UPSTREAM / "uds-client" / "building" / "linux" / "builders" / "Debian13" / "Dockerfile"
AGENT = UPSTREAM / "uds-actor" / "building" / "linux" / "builders" / "Debian13" / "Dockerfile"

needs_upstream = pytest.mark.skipif(not CLIENT.exists(), reason="upstream submodules not checked out")


@needs_upstream
@pytest.mark.parametrize("distro,image", [("Ubuntu2404", "ubuntu:24.04"), ("Ubuntu2604", "ubuntu:26.04")])
def test_ubuntu_builders(distro, image):
    out = make_builder.derive("client", distro, CLIENT.read_text())
    assert out.splitlines()[0] == f"FROM {image}"
    assert "libusb-1.0-0-dev" in out and "libusb-1.0.0-dev" not in out
    assert "libgio-2.0-dev" not in out
    assert "git clone --branch" in out  # FreeRDP build of upstream kept


@needs_upstream
@pytest.mark.parametrize("component,src", [("client", CLIENT), ("agent", AGENT)])
@pytest.mark.parametrize("distro,version", [("Rocky9", "9"), ("Rocky10", "10")])
def test_rocky_builders(component, src, distro, version):
    out = make_builder.derive(component, distro, src.read_text())
    assert out.splitlines()[0] == f"FROM rockylinux/rockylinux:{version}"
    assert "apt-get" not in out
    assert "crb enable" in out and "rpm-build" in out
    assert "sh.rustup.rs" in out
    if component == "client":
        assert "-DCMAKE_INSTALL_LIBDIR=lib" in out
        assert "-DWITH_OPENH264=OFF" in out and "-DWITH_GFX_H264=OFF" in out
        assert "libavcodec-free-devel" in out
        if version == "9":
            assert "libvpx" in out and "libvpx-devel" not in out and out.index("libvpx") < out.index("FreeRDP.git")
        else:
            assert "libvpx-devel" in out and "chromium.googlesource.com" not in out
    else:
        assert "libstdc++-static" in out and "libusb" not in out


def test_rocky_builder_rejects_changed_upstream():
    with pytest.raises(SystemExit):
        make_builder.derive("agent", "Rocky9", "FROM debian:trixie\nRUN true\n")


def test_rpm_spec_and_file_list(tmp_path):
    root = tmp_path / "root"
    (root / "usr/share/udsactor").mkdir(parents=True)
    (root / "usr/share/udsactor/icon.png").write_bytes(b"x")
    (root / "usr/sbin").mkdir(parents=True)
    (root / "usr/sbin/udsactor-config").write_bytes(b"x")
    (root / "usr/share/doc/librevdi-agent-unmanaged").mkdir(parents=True)
    (root / "usr/share/doc/librevdi-agent-unmanaged/THIRD-PARTY-NOTICES.txt").write_text("n")

    files = build_rpm.file_list(root, "librevdi-agent-unmanaged")
    assert "%dir /usr/share/udsactor" in files
    assert "%dir /usr/share/doc/librevdi-agent-unmanaged" in files
    assert "/usr/sbin/udsactor-config" in files
    assert "%dir /usr/sbin" not in files and "%dir /usr" not in files  # system directories not owned

    text = build_rpm.spec(
        "agent", "librevdi-agent-unmanaged", "udsactor-unmanaged", "0.1.0~dev.5", "LibreVDI Agent", "/r", files,
        ["librevdi-agent"],
    )  # fmt: skip
    assert "Name: librevdi-agent-unmanaged" in text and "Version: 0.1.0~dev.5" in text
    assert "Obsoletes: udsactor-unmanaged" in text and "Conflicts: librevdi-agent" in text
    assert "systemctl enable udsactor.service" in text
    assert "__requires_exclude" in text
