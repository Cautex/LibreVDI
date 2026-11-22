"""Key generation helpers (used by the entrypoint and during image build)."""

import os
import secrets
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def random_secret(length: int = 64) -> str:
    return secrets.token_urlsafe(length)


def _rsa_pem(bits: int) -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


def ephemeral_rsa_pem() -> str:
    """Throw-away key for build/test runs only."""
    return _rsa_pem(2048)


def _write_private(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)


def ensure_keys(key_dir: str) -> list[str]:
    """Create missing key files in ``key_dir``. Existing files are never overwritten."""
    created = []
    secret_path = os.path.join(key_dir, "secret_key")
    rsa_path = os.path.join(key_dir, "rsa.pem")
    if not os.environ.get("LIBREVDI_SECRET_KEY") and not os.path.exists(secret_path):
        _write_private(secret_path, random_secret())
        created.append(secret_path)
    if not os.environ.get("LIBREVDI_RSA_KEY") and not os.path.exists(rsa_path):
        _write_private(rsa_path, _rsa_pem(4096))
        created.append(rsa_path)
    return created


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ.get("UDS_DATA_DIR", "/var/lib/uds"), "keys")
    for p in ensure_keys(target):
        print(f"librevdi: generated {p} - BACK UP THIS FILE, encrypted data depends on it")
