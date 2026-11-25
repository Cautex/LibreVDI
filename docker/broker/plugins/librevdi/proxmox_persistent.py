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
from django.utils.translation import gettext_lazy
from django.utils.translation import gettext_noop as _
from uds.core import exceptions, types
from uds.core.exceptions.services import MaxServicesReachedError
from uds.core.managers.userservice import UserServiceManager
from uds.core.types import errors
from uds.core.ui import gui
from uds.models import ServicePool
from uds.services.Proxmox.provider import ProxmoxProvider
from uds.services.Proxmox.service_fixed import ProxmoxServiceFixed

from .power_policy import POLICY_ALWAYS_ON, POLICY_NONE, POLICY_SHUTDOWN

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
    # Like a dedicated pool: the service may be created first and machines added later
    machines = gui.MultiChoiceField(
        label=_("Machines"),
        order=30,
        tooltip=_("Machines of this service. Can be left empty and added later."),
        required=False,
        tab=types.ui.Tab.MACHINE,
        rows=10,
    )
    use_snapshots = ProxmoxServiceFixed.use_snapshots
    # "Keep on error" is not offered: upstream would free the machine (and lose the user's
    # assignment) on any access error, e.g. while Proxmox is briefly unreachable.

    # Like "automatic assignment" of dedicated pools in commercial VDI: off = only machines an
    # administrator assigned (Service pool -> Assigned services -> Assign service) are handed out.
    auto_assign = gui.CheckBoxField(
        label=_("Automatic assignment"),
        order=99,
        default=True,
        tooltip=_(
            "On: a user without a machine gets the next free one on first login and keeps it. "
            "Off: users only get the machine an administrator assigned to them."
        ),
        tab=types.ui.Tab.ADVANCED,
    )

    # Power policy (applied by power_policy.PersistentPowerPolicy every two minutes)
    power_policy = gui.ChoiceField(
        label=_("After logoff"),
        order=100,
        default=POLICY_NONE,
        choices=[
            gui.choice_item(POLICY_NONE, _("Do nothing")),
            gui.choice_item(POLICY_SHUTDOWN, _("Shut down machine after delay")),
            gui.choice_item(POLICY_ALWAYS_ON, _("Keep all machines powered on")),
        ],
        tooltip=_(
            "Power policy for the machines of this service. Stopped machines are always started "
            "when their user connects."
        ),
        tab=types.ui.Tab.ADVANCED,
    )
    power_delay = gui.NumericField(
        label=_("Shutdown delay (minutes)"),
        order=101,
        length=4,
        default=30,
        min_value=0,
        max_value=10080,
        tooltip=_("Minutes after the user logged off before the machine is shut down"),
        tab=types.ui.Tab.ADVANCED,
        required=True,
    )

    # Session policy: enforced by the agent (upstream "max idle"), see session_idle_seconds()
    idle_logoff = gui.NumericField(
        label=_("Log off inactive sessions after (minutes)"),
        order=102,
        length=4,
        default=0,
        min_value=0,
        max_value=10080,
        tooltip=_(
            "0 = off. The agent logs off a session without keyboard or mouse input for this time; "
            "this includes disconnected sessions. The user is warned two minutes before. "
            "Takes effect from the next login."
        ),
        tab=types.ui.Tab.ADVANCED,
        required=True,
    )

    @typing.override
    def should_maintain_on_error(self) -> bool:
        return True  # never free a persistent machine because of an error

    @typing.override
    def initialize(self, values: "types.core.ValuesType") -> None:
        if values and not self.machines.value:
            # allowed for persistent desktops, except removing the last machines while assigned
            with self._assigned_access() as assigned_vms:
                if assigned_vms:
                    raise exceptions.ui.ValidationError(
                        "Cannot remove machines with assigned services: "
                        + ", ".join(self.get_name(m) or m for m in sorted(assigned_vms))
                    )
            self.token.value = self.token.value.strip()
            return
        super().initialize(values)

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


def session_idle_seconds(userservice: typing.Any) -> int | None:
    """Idle logoff time (seconds) for a session on a persistent desktop, None if off or not ours."""
    try:
        pool = userservice.deployed_service
        if not is_persistent_pool(pool):
            return None
        minutes = pool.service.get_instance().idle_logoff.as_int()
    except Exception:  # never break a login because of the policy
        logger.exception("librevdi: reading idle logoff policy of %s", userservice)
        return None
    return minutes * 60 if minutes > 0 else None


class IdleLogoffPolicy:
    """Stands in for the (absent) OS manager of persistent pools in the actor login: upstream
    ``Login.action`` only calls ``max_idle()`` and ``ignore_deadline()`` on it and sends max_idle to
    the agent, which warns the user and logs the session off when idle (checked by the selfcheck)."""

    def __init__(self, seconds: int) -> None:
        self.seconds = seconds

    def max_idle(self) -> int:
        return self.seconds

    def ignore_deadline(self) -> bool:
        return False  # same as without OS manager: the pool deadline (calendar) applies


_original_release_from_logout = UserServiceManager.release_from_logout


def _release_from_logout(self: UserServiceManager, userservice: typing.Any) -> None:
    if is_persistent_pool(userservice.deployed_service):
        logger.debug("librevdi: keeping persistent assignment of %s", userservice)
        return
    _original_release_from_logout(self, userservice)


_original_create_assigned_for = UserServiceManager.create_assigned_for


def _create_assigned_for(self: UserServiceManager, service_pool: typing.Any, user: typing.Any) -> typing.Any:
    """New automatic assignments only if the persistent service allows it."""
    if is_persistent_pool(service_pool) and not service_pool.service.get_instance().auto_assign.as_bool():
        logger.info(
            "librevdi: no machine assigned to %s in pool %s and automatic assignment is off",
            user.pretty_name,
            service_pool.name,
        )
        raise MaxServicesReachedError()  # portal: "no more services available" - nothing is created
    return _original_create_assigned_for(self, service_pool, user)


# Portal message when a user gets no machine (replaces "Maximum services limit reached", which
# reads like a server problem). Must match NO_DESKTOP_MSG in branding/apply_branding.py.
NO_DESKTOP_MSG = (
    "No desktop is available for you: none is assigned to you or all are in use. Please contact your administrator."
)


def register() -> None:
    """Offer the service type in the Proxmox provider and install the hooks (idempotent)."""
    if not any(t.type_type == TYPE_TYPE for t in ProxmoxProvider.offers):
        ProxmoxProvider.offers.append(ProxmoxServicePersistent)
    pre_save.connect(_keep_unused_assignments, sender=ServicePool, dispatch_uid="librevdi-persistent-unused")
    if UserServiceManager.release_from_logout is not _release_from_logout:
        UserServiceManager.release_from_logout = _release_from_logout  # type: ignore[method-assign]
    errors.ERROR_STRINGS[errors.Error.MAX_SERVICES_REACHED.value] = gettext_lazy(NO_DESKTOP_MSG)
    if UserServiceManager.create_assigned_for is not _create_assigned_for:
        UserServiceManager.create_assigned_for = _create_assigned_for  # type: ignore[method-assign]


register()
