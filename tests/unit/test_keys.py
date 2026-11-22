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


def test_rdp_signing_cert(tmp_path):
    from cryptography import x509
    from cryptography.x509.oid import ExtendedKeyUsageOID

    target = tmp_path / "rdp-signing"
    created = keys.ensure_rdp_signing_cert(str(target), "LibreVDI RDP signing (test)")
    assert len(created) == 2
    cert = x509.load_pem_x509_certificate((target / "cert.pem").read_bytes())
    eku = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    assert ExtendedKeyUsageOID.CODE_SIGNING in eku and ExtendedKeyUsageOID.SERVER_AUTH in eku
    assert cert.public_key().key_size == 3072
    assert stat.S_IMODE((target / "key.pem").stat().st_mode) == 0o600
    assert len(keys.sha1_thumbprint(str(target / "cert.pem"))) == 40
    # idempotent
    assert keys.ensure_rdp_signing_cert(str(target), "other") == []
