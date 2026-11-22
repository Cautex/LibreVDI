"""Key generation helpers (used by the entrypoint and during image build)."""

import datetime
import os
import secrets
import sys

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


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


def ensure_rdp_signing_cert(target_dir: str, common_name: str, years: int = 5) -> list[str]:
    """Creates a self-signed certificate for signing .rdp files (if none exists).

    RSA 3072, key usage digitalSignature, EKU serverAuth + codeSigning. Existing files are kept;
    administrators can also point LIBREVDI_RDP_SIGN_CERT/KEY to a certificate of their own CA.
    """
    cert_path = os.path.join(target_dir, "cert.pem")
    key_path = os.path.join(target_dir, "key.pem")
    if os.path.exists(cert_path) and os.path.exists(key_path):
        return []
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=365 * years))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CODE_SIGNING]),
            critical=False,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256())
    )
    _write_private(
        key_path,
        key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()
        ).decode(),
    )
    os.makedirs(target_dir, exist_ok=True)
    with open(cert_path, "w", encoding="utf-8") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM).decode())
    return [cert_path, key_path]


def sha1_thumbprint(cert_path: str) -> str:
    with open(cert_path, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read())
    return cert.fingerprint(hashes.SHA1()).hex().upper()  # noqa: S303  # Windows thumbprints are SHA-1


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ.get("UDS_DATA_DIR", "/var/lib/uds"), "keys")
    for p in ensure_keys(target):
        print(f"librevdi: generated {p} - BACK UP THIS FILE, encrypted data depends on it")
