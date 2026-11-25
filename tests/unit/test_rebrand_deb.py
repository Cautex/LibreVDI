import os
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packaging", "linux"))
import rebrand_deb as rd

CONTROL = """Package: udslauncher
Version: 5.0.0
Architecture: amd64
Maintainer: Upstream Maintainer <upstream@example.com>
Depends: libc6 (>= 2.36)
Section: net
Priority: optional
Homepage: http://www.udsenterprise.com
Description: Launcher for Universal Desktop Services (UDS) Broker
 This package provides the required components.
"""

DESKTOP = """[Desktop Entry]
Name=UDS Launcher
Comment=UDS Launcher for VDI connections
Exec=/usr/share/udslauncher/launcher %u
Icon=help-browser
Type=Application
MimeType=x-scheme-handler/udssv2;
"""


def test_rebrand_control_keeps_dependencies_and_replaces_upstream():
    out = dict(rd.parse_control(rd.rebrand_control(CONTROL, "librevdi-client", "0.1.0~dev.1", "LibreVDI Client")))
    assert out["Package"] == "librevdi-client"
    assert out["Version"] == "0.1.0~dev.1"
    assert out["Depends"] == "libc6 (>= 2.36)"
    assert out["Provides"] == out["Conflicts"] == out["Replaces"] == "udslauncher"
    assert out["Homepage"] == rd.PROJECT_URL
    assert out["Description"].startswith("LibreVDI Client\n Based on OpenUDS")


def test_rebrand_text_and_icon():
    text = rd.set_desktop_icon(rd.rebrand_text(DESKTOP), "librevdi-client")
    assert "Name=LibreVDI Client" in text
    assert "Icon=librevdi-client" in text
    assert "Exec=/usr/share/udslauncher/launcher %u" in text  # technical path unchanged
    assert rd.rebrand_text("Description=UDS Actor Service") == "Description=LibreVDI Agent Service"


@pytest.mark.skipif(shutil.which("dpkg-deb") is None, reason="dpkg-deb not available")
def test_full_package_roundtrip(tmp_path):
    root = tmp_path / "src"
    (root / "DEBIAN").mkdir(parents=True)
    (root / "DEBIAN" / "control").write_text(CONTROL)
    (root / "DEBIAN" / "postinst").write_text("#!/bin/sh\nexit 0\n")
    os.chmod(root / "DEBIAN" / "postinst", 0o755)  # noqa: S103
    (root / "usr/share/applications").mkdir(parents=True)
    (root / "usr/share/applications/udslauncher.desktop").write_text(DESKTOP)
    (root / "usr/share/udslauncher").mkdir(parents=True)
    (root / "usr/share/udslauncher/launcher").write_bytes(b"\x7fELF")
    upstream = tmp_path / "udslauncher_5.0.0_amd64.deb"
    subprocess.run(["dpkg-deb", "--root-owner-group", "-b", str(root), str(upstream)], check=True, capture_output=True)
    icon = tmp_path / "logo.png"
    icon.write_bytes(b"png")

    rd.main(
        [
            str(upstream),
            str(tmp_path / "out"),
            "--name",
            "librevdi-client",
            "--version",
            "0.1.0~dev.1",
            "--description",
            "LibreVDI Client",
            "--suffix",
            "debian13",
            "--icon",
            str(icon),
        ]
    )

    out = tmp_path / "out" / "librevdi-client_0.1.0~dev.1_amd64-debian13.deb"
    assert out.exists()
    info = subprocess.run(
        ["dpkg-deb", "-f", str(out), "Package", "Replaces"], check=True, capture_output=True, text=True
    ).stdout
    assert "Package: librevdi-client" in info and "Replaces: udslauncher" in info
    files = subprocess.run(["dpkg-deb", "-c", str(out)], check=True, capture_output=True, text=True).stdout
    assert "usr/share/icons/hicolor/256x256/apps/librevdi-client.png" in files
    extracted = tmp_path / "x"
    subprocess.run(["dpkg-deb", "-R", str(out), str(extracted)], check=True)
    assert "Name=LibreVDI Client" in (extracted / "usr/share/applications/udslauncher.desktop").read_text()
    md5 = (extracted / "DEBIAN" / "md5sums").read_text()
    assert "usr/share/applications/udslauncher.desktop" in md5 and "usr/share/udslauncher/launcher" in md5
