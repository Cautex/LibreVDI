"""Self-test of the LibreVDI extensions (see ADR-0008).

Two kinds of checks:

* **upstream contract** – the OpenUDS classes, methods (with the parameters LibreVDI calls them
  with), model fields and settings that LibreVDI relies on still exist. Fails after an OpenUDS
  update that changed them, before anything silently stops working.
* **LibreVDI active** – every hook is installed, the service type is offered, signals are
  connected, the power policy job is registered, the build-time branding is in place.

Run by ``librevdi-entrypoint init`` (``python -m librevdi_ext.selfcheck``) on every start and by
the CI smoke test. Every new hook or upstream dependency must get a check here.
"""

from __future__ import annotations

import base64
import dataclasses
import inspect
import os
import re
import typing

Result = tuple[bool, str]


def _params(func: typing.Any) -> list[str]:
    return list(inspect.signature(func).parameters)


def _check(results: list[Result], ok: bool, what: str) -> None:
    results.append((bool(ok), what))


def _check_params(results: list[Result], func: typing.Any, expected: list[str], what: str) -> None:
    try:
        got = _params(func)
    except (TypeError, ValueError) as e:
        _check(results, False, f"{what}: signature not readable ({e})")
        return
    _check(results, got == expected, f"{what}{tuple(expected)}" + ("" if got == expected else f" – found {got}"))


def upstream_contract() -> list[Result]:
    # pylint: disable=import-outside-toplevel
    from django.db.models.signals import pre_save
    from uds.core import jobs, types
    from uds.core.exceptions.services import MaxServicesReachedError
    from uds.core.managers import downloads_manager
    from uds.core.services.generics.fixed.service import FixedService
    from uds.core.types import errors
    from uds.core.types.rest import TableField
    from uds.core.util.config import GlobalConfig
    from uds.models import Provider, Service, ServicePool, ServicePoolGroup, Tag, UserService
    from uds.REST.methods.user_services import UserServiceItem
    from uds.services.Proxmox.proxmox.client import ProxmoxClient
    from uds.services.Proxmox.service_fixed import ProxmoxServiceFixed
    from uds.web.util import udsclients_info

    from . import assigned_view, pool_maintenance, proxmox_persistent

    r: list[Result] = []
    # methods wrapped by LibreVDI (checked on the originals)
    _check_params(
        r,
        proxmox_persistent._original_release_from_logout,
        ["self", "userservice"],
        "UserServiceManager.release_from_logout",
    )
    _check_params(
        r,
        proxmox_persistent._original_create_assigned_for,
        ["self", "service_pool", "user"],
        "UserServiceManager.create_assigned_for",
    )
    _check_params(
        r, assigned_view._original_item, ["item", "props", "is_cache"], "AssignedUserService.userservice_item"
    )
    _check_params(r, assigned_view._original_table, ["self", "parent"], "AssignedUserService.get_table")
    _check_params(r, assigned_view._original_odata_filter, ["self", "qs"], "AssignedUserService.odata_filter")
    _check_params(r, pool_maintenance._original_is_in_maintenance, ["self"], "ServicePool.is_in_maintenance")
    _check_params(r, assigned_view._original_process_login, ["userservice", "username"], "actor Login.process_login")
    _check_params(r, assigned_view._original_login_action, ["self"], "actor Login.action")
    # the idle logoff policy stands in for the OS manager: only these two methods may be used on it
    try:
        used = set(re.findall(r"osmanager\.(\w+)\(", inspect.getsource(assigned_view._original_login_action)))
    except (OSError, TypeError):
        used = set()
    _check(
        r,
        used == {"max_idle", "ignore_deadline"},
        "actor Login.action uses osmanager.max_idle/ignore_deadline only" + ("" if used else " – source not readable"),
    )

    # base class of the persistent service type
    for name in (
        "initialize",
        "is_removable_on_logout",
        "should_maintain_on_error",
        "_assigned_access",
        "get_name",
        "get_and_assign",
    ):
        _check(r, hasattr(ProxmoxServiceFixed, name), f"ProxmoxServiceFixed.{name}")
    _check(r, "maintain_on_error" in FixedService._gui_fields_template, "FixedService field maintain_on_error")
    for name in ("token", "pool", "machines", "use_snapshots"):
        _check(r, hasattr(ProxmoxServiceFixed, name), f"ProxmoxServiceFixed field {name}")
    for name in ("get_vm_info", "start_vm", "shutdown_vm"):
        _check(r, hasattr(ProxmoxClient, name), f"Proxmox API {name}")

    # models, fields and data structures
    def has_field(model: typing.Any, field: str) -> bool:
        return any(f.name == field for f in model._meta.get_fields())

    for model, field in (
        (ServicePool, "ignores_unused"),
        (ServicePool, "servicesPoolGroup"),
        (ServicePool, "tags"),
        (ServicePool, "service"),
        (UserService, "in_use"),
        (UserService, "in_use_date"),
        (UserService, "deployed_service"),
        (Provider, "maintenance_mode"),
        (Service, "deployedServices"),
        (Tag, "tag"),
        (ServicePoolGroup, "priority"),
    ):
        _check(r, has_field(model, field), f"model field {model.__name__}.{field}")
    item_fields = {f.name for f in dataclasses.fields(UserServiceItem)}
    for field in ("owner", "in_use", "source_host", "source_ip", "state"):
        _check(r, field in item_fields, f"UserServiceItem.{field}")
    _check(r, {"name", "title"} <= {f.name for f in dataclasses.fields(TableField)}, "TableField(name, title)")
    _check(r, len(errors.ERROR_STRINGS) > errors.Error.MAX_SERVICES_REACHED.value, "errors.ERROR_STRINGS entry")
    _check(r, issubclass(MaxServicesReachedError, Exception), "MaxServicesReachedError")
    _check(r, isinstance(getattr(downloads_manager(), "_downloadables", None), dict), "DownloadsManager._downloadables")
    _check(r, isinstance(udsclients_info.PLUGINS, list), "udsclients_info.PLUGINS")
    _check(
        r,
        [f.name for f in dataclasses.fields(types.plugins.UDSClientPlugin)] == ["url", "description", "name", "legacy"],
        "types.plugins.UDSClientPlugin(url, description, name, legacy)",
    )
    _check_params(
        r,
        type(downloads_manager()).register,
        ["self", "name", "description", "path", "mimetype", "legacy"],
        "DownloadsManager.register",
    )
    _check(r, hasattr(jobs, "Job") and hasattr(jobs, "factory"), "uds.core.jobs.Job / factory")
    _check(r, hasattr(pre_save, "receivers"), "django pre_save signal")
    for name in (
        "SUPER_USER_LOGIN",
        "SUPER_USER_PASS",
        "BEHIND_PROXY",
        "ALLOWED_IP_FORWARDERS",
        "SITE_NAME",
        "SITE_LOGO_NAME",
        "SITE_COPYRIGHT",
        "SITE_COPYRIGHT_LINK",
        "LOGIN_BLOCK_IP",
        "KEEP_INFO_TIME",
    ):
        _check(r, hasattr(GlobalConfig, name), f"GlobalConfig.{name}")
    return r


def librevdi_active() -> list[Result]:
    # pylint: disable=import-outside-toplevel
    from django.db.models.signals import pre_save
    from uds.core import jobs
    from uds.core.consts import images
    from uds.core.managers.userservice import UserServiceManager
    from uds.core.types import errors
    from uds.core.ui import gui
    from uds.models import ServicePool
    from uds.REST.methods.actor_v3 import Login
    from uds.REST.methods.user_services import AssignedUserService
    from uds.services.Proxmox.provider import ProxmoxProvider

    from . import assigned_view, pool_maintenance, proxmox_persistent

    r: list[Result] = []
    _check(
        r,
        any(t is proxmox_persistent.ProxmoxServicePersistent for t in ProxmoxProvider.offers),
        "service type 'Proxmox Persistent Desktops (LibreVDI)' offered",
    )
    _check(
        r,
        UserServiceManager.release_from_logout is proxmox_persistent._release_from_logout,
        "hook: keep persistent assignments on logoff/unused",
    )
    _check(
        r,
        UserServiceManager.create_assigned_for is proxmox_persistent._create_assigned_for,
        "hook: 'Automatic assignment' switch",
    )
    _check(r, AssignedUserService.userservice_item is assigned_view._userservice_item, "hook: 'Logged-in user' column")
    _check(r, AssignedUserService.get_table is assigned_view._get_table, "hook: assigned services column titles")
    _check(r, AssignedUserService.odata_filter is assigned_view._odata_filter, "hook: hide removed machines")
    _check(r, Login.process_login is assigned_view._process_login, "hook: latest login updates 'Logged-in user'")
    _check(r, Login.action is assigned_view._login_action, "hook: no idle logoff for Wayland sessions")
    _check(r, ServicePool.is_in_maintenance is pool_maintenance._is_in_maintenance, "hook: maintenance per pool")
    _check(
        r,
        isinstance(getattr(proxmox_persistent.ProxmoxServicePersistent, "idle_logoff", None), gui.NumericField),
        "persistent service setting 'Log off inactive sessions'",
    )
    uids = {key[0] for key, *_ in pre_save.receivers}
    for uid in ("librevdi-persistent-unused", "librevdi-default-pool-group"):
        _check(r, uid in uids, f"signal: {uid}")
    _check(r, "librevdi power policy (persistent desktops)" in jobs.factory().objects(), "job: power policy")
    _check(
        r,
        str(errors.ERROR_STRINGS[errors.Error.MAX_SERVICES_REACHED.value]) != "Maximum services limit reached. "
        "Please, contact administrator",
        "portal message 'no desktop available'",
    )
    logo = "/opt/librevdi/branding/logo-64.png"
    if os.path.isfile(logo):
        with open(logo, "rb") as f:
            _check(
                r, images.DEFAULT_THUMB_BASE64 == base64.b64encode(f.read()).decode(), "branding: default pool image"
            )
    return r


def run() -> list[Result]:
    return upstream_contract() + librevdi_active()
