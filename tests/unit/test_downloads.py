import os
import time

from librevdi_ext import downloads


def test_upstream_version(tmp_path):
    f = tmp_path / "system.py"
    f.write_text('import typing\nVERSION: typing.Final[str] = "5.0.0"\nOTHER = 1\n')
    assert downloads.upstream_version(str(f)) == "5.0.0"


def test_publish_maps_and_picks_newest(tmp_path):
    src = tmp_path / "downloads"
    app = tmp_path / "app"
    src.mkdir()
    old = src / "LibreVDI-Client-Setup-0.1.0-dev.3.exe"
    new = src / "LibreVDI-Client-Setup-0.1.0-dev.4.exe"
    old.write_bytes(b"old")
    new.write_bytes(b"new")
    os.utime(old, (time.time() - 100, time.time() - 100))
    (src / "LibreVDI-Agent-unmanaged-Setup-0.1.0-dev.4.exe").write_bytes(b"unmanaged")
    (src / "unrelated.exe").write_bytes(b"x")

    published = downloads.publish(str(src), str(app), "5.0.0")

    client = app / "static/clients/UDSLauncherInstaller-5.0.0.exe"
    agent = app / "uds/osmanagers/WindowsOsManager/files/UDSActorUnmanagedSetup-5.0.0.exe"
    assert client.read_bytes() == b"new"
    assert agent.read_bytes() == b"unmanaged"
    assert not (app / "uds/osmanagers/WindowsOsManager/files/UDSActorSetup-5.0.0.exe").exists()
    assert len(published) == 2


def test_publish_empty_dir(tmp_path):
    assert downloads.publish(str(tmp_path), str(tmp_path / "app"), "5.0.0") == []


def test_publish_host_dir_wins_bundled_fills_gaps(tmp_path):
    host = tmp_path / "host"
    bundled = tmp_path / "bundled"
    app = tmp_path / "app"
    host.mkdir()
    bundled.mkdir()
    (host / "LibreVDI-Client-Setup-0.3.0.exe").write_bytes(b"host client")
    (bundled / "LibreVDI-Client-Setup-0.2.0.exe").write_bytes(b"bundled client")
    (bundled / "LibreVDI-Agent-managed-Setup-0.2.0.exe").write_bytes(b"bundled agent")

    published = downloads.publish([str(host), str(bundled)], str(app), "5.0.0")

    assert (app / "static/clients/UDSLauncherInstaller-5.0.0.exe").read_bytes() == b"host client"
    assert (app / "uds/osmanagers/WindowsOsManager/files/UDSActorSetup-5.0.0.exe").read_bytes() == b"bundled agent"
    assert len(published) == 2
