"""Power state of the machine behind an assigned service ("Machine power" column).

Only for persistent desktops (Proxmox). One cluster-wide query per provider (upstream
``ProxmoxClient.list_vms``, cached by upstream for a short time) instead of one API call per row.
Any error shows "Unknown" - the list must never fail because Proxmox is slow or unreachable.
"""

from __future__ import annotations

import logging
import typing

logger = logging.getLogger(__name__)

POWER_ON: typing.Final[str] = "On"
POWER_OFF: typing.Final[str] = "Off"
POWER_SUSPENDED: typing.Final[str] = "Suspended"
POWER_PAUSED: typing.Final[str] = "Paused"
POWER_UNKNOWN: typing.Final[str] = "Unknown"


def power_label(status: str | None, lock: str | None = None, qmpstatus: str | None = None) -> str:
    """Proxmox VM state -> label (English msgid; German via the branding catalog)."""
    if lock == "suspended":  # hibernated to disk: status "stopped", lock "suspended"
        return POWER_SUSPENDED
    if status == "running":
        return POWER_PAUSED if qmpstatus in ("paused", "suspended") else POWER_ON
    if status == "stopped":
        return POWER_OFF
    return POWER_UNKNOWN


def power_state(userservice: typing.Any) -> str:
    """Label for an assigned service, "" if not a persistent desktop."""
    try:
        from .proxmox_persistent import is_persistent_pool  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

        pool = userservice.deployed_service
        if not is_persistent_pool(pool):
            return ""
        vmid = str(getattr(userservice.get_instance(), "_vmid", "") or "")
        if not vmid:
            return POWER_UNKNOWN
        api = pool.service.get_instance().provider().api
        for vm in api.list_vms():  # cached by upstream, one query for all rows
            if str(vm.id) == vmid:
                return power_label(str(vm.status), vm.lock, vm.qmpstatus)
        return POWER_UNKNOWN
    except Exception:  # never break the list
        logger.debug("librevdi: power state of %s not available", userservice, exc_info=True)
        return POWER_UNKNOWN
