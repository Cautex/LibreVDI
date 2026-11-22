import os
import stat

from cryptography.hazmat.primitives import serialization
from librevdi_ext import keys


def test_ensure_keys_creates_once(tmp_path, monkeypatch):
    monkeypatch.delenv("LIBREVDI_SECRET_KEY", raising=False)
    monkeypatch.delenv("LIBREVDI_RSA_KEY", raising=False)
    key_dir = tmp_path / "keys"

    created = keys.ensure_keys(str(key_dir))
    assert sorted(os.path.basename(p) for p in created) == ["rsa.pem", "secret_key"]

    rsa_pem = (key_dir / "rsa.pem").read_bytes()
    key = serialization.load_pem_private_key(rsa_pem, password=None)
    assert key.key_size == 4096
    for name in ("rsa.pem", "secret_key"):
        assert stat.S_IMODE((key_dir / name).stat().st_mode) == 0o600

    # second run must not overwrite anything
    secret_before = (key_dir / "secret_key").read_text()
    assert keys.ensure_keys(str(key_dir)) == []
    assert (key_dir / "secret_key").read_text() == secret_before
    assert (key_dir / "rsa.pem").read_bytes() == rsa_pem


def test_ensure_keys_skips_when_env_given(tmp_path, monkeypatch):
    monkeypatch.setenv("LIBREVDI_SECRET_KEY", "x")
    monkeypatch.setenv("LIBREVDI_RSA_KEY", "y")
    assert keys.ensure_keys(str(tmp_path / "keys")) == []


def test_random_secret_unique():
    assert keys.random_secret() != keys.random_secret()
    assert len(keys.random_secret()) >= 64
