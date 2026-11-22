"""Proxmox persistent (dedicated) desktops.

Upstream "Proxmox Fixed Machines" releases the machine when the user logs off in Windows/Linux
(user service state "Removed"); on the next login the user gets *any* free machine of the list.
For classic persistent VDI each user must keep *his* machine until an administrator removes the
assignment. This service type is identical to "Proxmox Fixed Machines" except that assignments
are never released on logoff.

Assignments end only when an administrator deletes the assigned service (Pools -> Service pool ->
Assigned services -> Delete) or the machine is removed from the service.
"""

import typing

from django.utils.translation import gettext_noop as _
from uds.services.Proxmox.provider import ProxmoxProvider
from uds.services.Proxmox.service_fixed import ProxmoxServiceFixed

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


def register() -> None:
    """Offer the service type in the Proxmox provider (idempotent)."""
    if not any(t.type_type == TYPE_TYPE for t in ProxmoxProvider.offers):
        ProxmoxProvider.offers.append(ProxmoxServicePersistent)


register()
