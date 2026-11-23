"""Power policy for persistent desktops (like "remote machine power policy" in commercial VDI).

Per service "Proxmox Persistent Desktops (LibreVDI)", tab "Power":

* ``none``      – do nothing (default, previous behaviour)
* ``shutdown``  – shut an assigned machine down (guest shutdown via ACPI / QEMU agent) when its
                  user has been logged off for at least ``power_delay`` minutes
* ``always_on`` – keep every machine of the service running (start stopped machines)

Starting a stopped machine when its user connects is upstream behaviour (``set_ready`` of fixed
machines) and works with every policy. A job checks all services of this type every two minutes.
Disconnected sessions (RDP window closed without logoff) count as "in use" and are left alone.
Machines whose agent never reported to the broker for this assignment (actor version unknown,
e.g. agent configured with the token of another service) are never shut down: without agent
reports the broker cannot know whether someone is logged in.
Nothing happens while the provider is in maintenance mode (e.g. while an admin works on the VMs).
"""

from __future__ import annotations

import dataclasses
import datetime
import logging
import typing

POLICY_NONE: typing.Final[str] = "none"
POLICY_SHUTDOWN: typing.Final[str] = "shutdown"
POLICY_ALWAYS_ON: typing.Final[str] = "always_on"
JOB_INTERVAL_SECONDS: typing.Final[int] = 120

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class Assignment:
    """What the policy needs to know about one assigned machine."""

    vmid: str
    in_use: bool
    in_use_since: datetime.datetime | None  # last change of "in use" (login/logoff)
    agent_seen: bool = True  # the agent reported to the broker for this assignment (actor version known)


def machines_to_shut_down(
    assignments: typing.Iterable[Assignment],
    running: typing.Callable[[str], bool],
    now: datetime.datetime,
    delay_minutes: int,
) -> list[str]:
    """Machines whose user is logged off for at least ``delay_minutes`` and that are still running."""
    cutoff = now - datetime.timedelta(minutes=max(delay_minutes, 0))
    return [
        a.vmid
        for a in assignments
        if a.vmid
        and a.agent_seen  # without agent reports "not in use" means nothing: never shut down a session
        and not a.in_use
        and a.in_use_since is not None
        and a.in_use_since <= cutoff
        and running(a.vmid)
    ]


def machines_to_start(vmids: typing.Iterable[str], stopped: typing.Callable[[str], bool]) -> list[str]:
    return [vmid for vmid in vmids if vmid and stopped(vmid)]


def _job_class() -> type:
    # Broker imports only inside the function: the decision logic above stays testable without Django
    # pylint: disable=import-outside-toplevel
    from uds.core import jobs
    from uds.core.types.log import LogLevel, LogSource
    from uds.core.types.states import State
    from uds.core.util import log
    from uds.core.util.model import sql_now
    from uds.models import Service, UserService

    from .proxmox_persistent import TYPE_TYPE

    class PersistentPowerPolicy(jobs.Job):
        friendly_name = "LibreVDI power policy (persistent desktops)"

        def next_execution_delay(self) -> int:
            return JOB_INTERVAL_SECONDS

        def run(self) -> None:
            for service_model in Service.objects.filter(data_type=TYPE_TYPE):
                try:
                    self._apply(service_model)
                except Exception:  # one broken service must not stop the others
                    logger.exception("librevdi: power policy failed for service %s", service_model.name)

        def _apply(self, service_model: typing.Any) -> None:
            if service_model.provider.maintenance_mode:  # like upstream: no automatic actions
                return
            service = service_model.get_instance()
            policy = service.power_policy.value
            if policy not in (POLICY_SHUTDOWN, POLICY_ALWAYS_ON):
                return
            api = service.provider().api

            def status(vmid: str) -> typing.Any:
                return api.get_vm_info(int(vmid))

            def stopped(vmid: str) -> bool:
                info = status(vmid)
                return not info.status.is_running() and info.lock != "suspended"

            if policy == POLICY_ALWAYS_ON:
                for vmid in machines_to_start(service.machines.as_list(), stopped):
                    api.start_vm(int(vmid))
                    service.do_log(LogLevel.INFO, f"Power policy 'always on': starting machine {vmid}")
                return

            userservices = {
                getattr(us.get_instance(), "_vmid", ""): us
                for us in UserService.objects.filter(
                    deployed_service__service=service_model, cache_level=0, state=State.USABLE
                )
            }
            assignments = [
                Assignment(
                    vmid=vmid,
                    in_use=us.in_use,
                    in_use_since=us.in_use_date,
                    agent_seen=us.actor_version not in ("", "0.0.0"),
                )
                for vmid, us in userservices.items()
            ]
            delay = service.power_delay.as_int()
            for vmid in machines_to_shut_down(assignments, lambda v: status(v).status.is_running(), sql_now(), delay):
                api.shutdown_vm(int(vmid))
                log.log(
                    userservices[vmid],
                    LogLevel.INFO,
                    message=f"Power policy: user logged off for {delay} min, shutting down machine {vmid}",
                    source=LogSource.SERVICE,
                )

    return PersistentPowerPolicy


def register() -> None:
    _job_class().register()
