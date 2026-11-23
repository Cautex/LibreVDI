"""Applies LibreVDI configuration to the broker database (run by ``librevdi-entrypoint init``).

Two kinds of values:

* **managed** – derived from the deployment (environment variables) and applied on every start:
  super user credentials, reverse proxy settings.
* **defaults** – sensible first-run values (branding, login hardening). They are applied only
  once (marker file on the data volume), so later changes in the admin UI are kept.
"""

import os
import sys

import django

DEFAULTS_VERSION = "1"


def _log(msg: str) -> None:
    print(f"librevdi: {msg}", flush=True)


def main() -> int:
    django.setup()
    # pylint: disable=import-outside-toplevel
    from uds.core.util.config import GlobalConfig

    GlobalConfig.initialize()

    # --- managed values -----------------------------------------------------------------
    root_user = os.environ.get("LIBREVDI_ROOT_USER", "root")
    root_pass = os.environ.get("LIBREVDI_ROOT_PASSWORD", "")
    pass_file = os.environ.get("LIBREVDI_ROOT_PASSWORD_FILE", "")
    if not root_pass and pass_file and os.path.isfile(pass_file):
        with open(pass_file, encoding="utf-8") as f:
            root_pass = f.read().strip()

    if root_pass:
        from uds.core import consts  # pylint: disable=import-outside-toplevel

        if root_pass == consts.security.DEFAULT_SUPERUSER_PASSWORD:
            _log("ERROR: LIBREVDI_ROOT_PASSWORD must not be the upstream default password")
            return 1
        GlobalConfig.SUPER_USER_LOGIN.set(root_user)
        GlobalConfig.SUPER_USER_PASS.set(root_pass)
        _log(f"super user '{root_user}' password applied from environment")
    else:
        _log("WARNING: LIBREVDI_ROOT_PASSWORD not set - super user keeps its current password")

    behind_proxy = os.environ.get("LIBREVDI_BEHIND_PROXY", "1").lower() in ("1", "true", "yes", "on")
    GlobalConfig.BEHIND_PROXY.set(behind_proxy)
    if behind_proxy:
        forwarders = os.environ.get("LIBREVDI_PROXY_NETWORKS", "")
        if forwarders:
            GlobalConfig.ALLOWED_IP_FORWARDERS.set(forwarders)
            _log(f"reverse proxy mode on, trusted forwarders: {forwarders}")
        else:
            _log("WARNING: reverse proxy mode on but LIBREVDI_PROXY_NETWORKS is empty (forwarders: '*')")

    # Persistent desktops (LibreVDI plugin): pools must never release unused assignments
    from uds.models import ServicePool  # pylint: disable=import-outside-toplevel

    fixed = ServicePool.objects.filter(
        service__data_type="LibreVDIProxmoxPersistentService", ignores_unused=False
    ).update(ignores_unused=True)
    if fixed:
        _log(f"persistent desktops: 'ignore unused' set on {fixed} service pool(s)")

    # --- first-run defaults -------------------------------------------------------------
    marker = os.path.join(os.environ.get("UDS_DATA_DIR", "/var/lib/uds"), f".librevdi-defaults-v{DEFAULTS_VERSION}")
    if os.path.exists(marker):
        _log("first-run defaults already applied, keeping admin changes")
        return 0

    GlobalConfig.SITE_NAME.set(os.environ.get("LIBREVDI_SITE_NAME", "LibreVDI"))
    GlobalConfig.SITE_LOGO_NAME.set(os.environ.get("LIBREVDI_SITE_NAME", "LibreVDI"))
    GlobalConfig.SITE_COPYRIGHT.set("LibreVDI · based on OpenUDS (BSD-3-Clause)")
    GlobalConfig.SITE_COPYRIGHT_LINK.set("https://github.com/Cautex/LibreVDI")
    GlobalConfig.LOGIN_BLOCK_IP.set(True)
    # NOT enabled by default: IMMUTABLE_LOG_ENABLED stamps entries via an external RFC 3161
    # time-stamping service; if that is unreachable, logins fail (see docs/upstream-notes.md).

    with open(marker, "w", encoding="utf-8") as f:
        f.write("applied\n")
    _log("first-run defaults applied (branding, login IP blocking)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
