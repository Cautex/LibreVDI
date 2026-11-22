"""Certificate for signed .rdp files.

``init``     (broker-init): creates a self-signed signing certificate on the data volume unless
             one exists or ``LIBREVDI_RDP_SIGN_CERT`` points to an administrator-provided one.
``publish``  (web start): copies the public certificate to the static files
             (``/uds/res/librevdi/rdp-signing.crt``) so clients can import it, and logs the SHA-1
             thumbprint needed for the Windows policy "trusted .rdp publishers".
"""

import os
import shutil
import sys

from librevdi_ext import keys

DATA_DIR = os.environ.get("UDS_DATA_DIR", "/var/lib/uds")
DEFAULT_DIR = os.path.join(DATA_DIR, "rdp-signing")
STATIC_TARGET = "/app/static/librevdi/rdp-signing.crt"


def _log(msg: str) -> None:
    print(f"librevdi: rdp-signing: {msg}", flush=True)


def init() -> int:
    if os.environ.get("LIBREVDI_RDP_SIGN_CERT"):
        _log(f"using administrator-provided certificate {os.environ['LIBREVDI_RDP_SIGN_CERT']}")
        return 0
    domain = os.environ.get("LIBREVDI_PUBLIC_URL", "").split("://")[-1].split("/")[0] or "LibreVDI"
    created = keys.ensure_rdp_signing_cert(DEFAULT_DIR, f"LibreVDI RDP signing ({domain})")
    if created:
        _log(f"self-signed signing certificate created in {DEFAULT_DIR} - BACK UP with the other keys")
    return 0


def publish() -> int:
    cert = os.environ.get("LIBREVDI_RDP_SIGN_CERT") or os.path.join(DEFAULT_DIR, "cert.pem")
    if not os.path.isfile(cert) or not cert.endswith((".pem", ".crt")):
        return 0
    try:
        os.makedirs(os.path.dirname(STATIC_TARGET), exist_ok=True)
        shutil.copyfile(cert, STATIC_TARGET)
        _log(f"public certificate at /uds/res/librevdi/rdp-signing.crt, SHA-1 {keys.sha1_thumbprint(cert)}")
    except (OSError, ValueError) as e:  # never block the web server
        _log(f"WARNING: could not publish certificate: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(init() if sys.argv[1:] == ["init"] else publish())
