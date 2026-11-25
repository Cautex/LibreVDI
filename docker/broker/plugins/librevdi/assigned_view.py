"""Assigned services overview like in commercial VDI: assigned user vs. logged-in user.

Upstream shows only the owner ("Owner") and "In Use". When someone else is logged in on the machine
(a local administrator, an old session) the machine is "in use" although its owner is not working
on it. LibreVDI adds the column "Logged-in user" (the Windows/Linux user name reported by the agent
at the last login, shown while the machine is in use), renames "Owner" to "Assigned user" and
"Src Host/Ip" to "Last client (host/IP)" (the values stay after logoff on purpose).
Removed machines are hidden from the list immediately (upstream shows them greyed out until the
cleanup job deletes them after ``keepInfoTime``, default 4 h).
"""

from __future__ import annotations

import dataclasses
import typing

from django.utils.translation import gettext_lazy as _
from uds.core.types.rest import TableField
from uds.core.types.states import State
from uds.REST.methods.user_services import AssignedUserService, UserServiceItem


@dataclasses.dataclass
class LibreVDIUserServiceItem(UserServiceItem):
    logged_user: str = ""


def logged_user(in_use: bool, props: dict[str, typing.Any]) -> str:
    return str(props.get("last_username") or "") if in_use else ""


_original_do_get_items = AssignedUserService.do_get_items
_original_item = AssignedUserService.userservice_item
_original_table = AssignedUserService.get_table


def _userservice_item(
    item: typing.Any, props: dict[str, typing.Any] | None = None, is_cache: bool = False
) -> typing.Any:
    val = _original_item(item, props, is_cache)
    if is_cache:
        return val
    values = {f.name: getattr(val, f.name) for f in dataclasses.fields(val)}
    return LibreVDIUserServiceItem(
        **values, logged_user=logged_user(item.in_use, props if props is not None else dict(item.properties))
    )


def _do_get_items(self: AssignedUserService, parent: typing.Any, for_cached: bool) -> typing.Any:
    """Removed machines disappear from the list at once (upstream keeps them for keepInfoTime)."""
    items = _original_do_get_items(self, parent, for_cached)
    if isinstance(items, list):
        return [i for i in items if getattr(i, "state", None) != State.REMOVED]
    return items


def _get_table(self: AssignedUserService, parent: typing.Any) -> typing.Any:
    table = _original_table(self, parent)
    titles = {
        # where the last connection came from (kept after logoff, updated on every connection)
        "source_host": _("Last client (host)"),
        "source_ip": _("Last client (IP)"),
        "owner": _("Assigned user"),
    }
    for field in table.fields:
        if field.name in titles:
            field.title = str(titles[field.name])
    for index, field in enumerate(table.fields):
        if field.name == "owner":
            table.fields.insert(index + 1, TableField(name="logged_user", title=str(_("Logged-in user"))))
            break
    return table


def register() -> None:
    if AssignedUserService.userservice_item is not _userservice_item:  # type: ignore[comparison-overlap]
        AssignedUserService.userservice_item = staticmethod(_userservice_item)  # type: ignore[assignment]
    if AssignedUserService.do_get_items is not _do_get_items:
        AssignedUserService.do_get_items = _do_get_items  # type: ignore[method-assign]
    if AssignedUserService.get_table is not _get_table:
        AssignedUserService.get_table = _get_table  # type: ignore[method-assign]


register()
