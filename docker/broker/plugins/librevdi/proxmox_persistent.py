"""Proxmox persistent (dedicated) desktops.

Upstream "Proxmox Fixed Machines" releases the machine when the user logs off in Windows/Linux
(user service state "Removed"); on the next login the user gets *any* free machine of the list.
For classic persistent VDI each user must keep *his* machine until an administrator removes the
assignment. This service type is identical to "Proxmox Fixed Machines" except that assignments
are never released on logoff.

Assignments end only when an administrator deletes the assigned service (Pools -> Service pool ->
Assigned services -> Delete) or the machine is removed from the service.

Upstream releases assignments on two paths; both are covered:

1. Logoff reported by the agent: honours ``Service.is_removable_on_logout()`` (overridden below).
2. Job "Unused services checker" (pools without OS manager): releases machines that are assigned
   but not in use for ``checkUnusedTime`` (default 631 s) and ignores the service type. Pools with
   this service type therefore always get "ignores unused" set (on save, and once by
   ``librevdi_ext.bootstrap`` for existing pools), and ``release_from_logout`` refuses to release
   them as a safety net.
"""

import logging
import typing

from django.db.models.signals import pre_save
from django.utils.translation import gettext_noop as _
from uds.core.managers.userservice import UserServiceManager
from uds.models import ServicePool
from uds.services.Proxmox.provider import ProxmoxProvider
from uds.services.Proxmox.service_fixed import ProxmoxServiceFixed

logger = logging.getLogger(__name__)

TYPE_TYPE: typing.Final[str] = "LibreVDIProxmoxPersistentService"


class ProxmoxServicePersistent(ProxmoxServiceFixed):
    """Like ``ProxmoxServiceFixed``, but the user <-> machine assignment survives logoffs."""

    type_name = _("Proxmox Persistent Desktops (LibreVDI)")
    type_type = TYPE_TYPE
    type_description = _(
        "Dedicated persistent desktops: every user keeps his machine across logoffs. "
        "Assignments are only released by an administrator. Needs qemu agent installed on machines."
    )
    icon_file = "service.png"

    # Same GUI as fixed machines (declared explicitly, as upstream does for inherited fields)
    token = ProxmoxServiceFixed.token
    pool = ProxmoxServiceFixed.pool
    machines = ProxmoxServiceFixed.machines
    use_snapshots = ProxmoxServiceFixed.use_snapshots
    maintain_on_error = ProxmoxServiceFixed.maintain_on_error

    @typing.override
    def is_removable_on_logout(self) -> bool:
        return False


def is_persistent_pool(pool: typing.Any) -> bool:
    service = getattr(pool, "service", None)
    return service is not None and getattr(service, "data_type", None) == TYPE_TYPE


def _keep_unused_assignments(sender: typing.Any, instance: ServicePool, **kwargs: typing.Any) -> None:
    """Pools of persistent desktops must never release unused assignments."""
    try:
        if is_persistent_pool(instance):
            instance.ignores_unused = True
    except Exception:  # service not set yet (new pool being created) - nothing to do
        logger.debug("librevdi: pool %s has no service yet", instance)


_original_release_from_logout = UserServiceManager.release_from_logout


def _release_from_logout(self: UserServiceManager, userservice: typing.Any) -> None:
    if is_persistent_pool(userservice.deployed_service):
        logger.debug("librevdi: keeping persistent assignment of %s", userservice)
        return
    _original_release_from_logout(self, userservice)


def register() -> None:
    """Offer the service type in the Proxmox provider and install the hooks (idempotent)."""
    if not any(t.type_type == TYPE_TYPE for t in ProxmoxProvider.offers):
        ProxmoxProvider.offers.append(ProxmoxServicePersistent)
    pre_save.connect(_keep_unused_assignments, sender=ServicePool, dispatch_uid="librevdi-persistent-unused")
    if UserServiceManager.release_from_logout is not _release_from_logout:
        UserServiceManager.release_from_logout = _release_from_logout  # type: ignore[method-assign]


register()
