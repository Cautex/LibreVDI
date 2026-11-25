"""Assigned services overview like in commercial VDI: assigned user vs. logged-in user.

Upstream shows only the owner ("Owner") and "In Use". When someone else is logged in on the machine
(a local administrator, an old session) the machine is "in use" although its owner is not working
on it. LibreVDI adds the column "Logged-in user" (the Windows/Linux user name reported by the agent
at the latest login – upstream kept the first one while the machine stayed in use – shown while the
machine is in use), renames "Owner" to "Assigned user" and
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
from uds.models import UserService
from uds.REST.methods.actor_v3 import Login
from uds.REST.methods.user_services import AssignedUserService, UserServiceItem


@dataclasses.dataclass
class LibreVDIUserServiceItem(UserServiceItem):
    logged_user: str = ""


def logged_user(in_use: bool, props: dict[str, typing.Any]) -> str:
    return str(props.get("last_username") or "") if in_use else ""


_original_process_login = Login.process_login
_original_odata_filter = AssignedUserService.odata_filter
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


def _process_login(userservice: typing.Any, username: str) -> typing.Any:
    """Upstream stores the user name only when the machine goes from unused to in use, so a second
    session (e.g. a local admin left logged in) hides the actual user. Keep the latest login."""
    result = _original_process_login(userservice, username)
    if username:
        userservice.properties["last_username"] = username
    return result


def _odata_filter(self: AssignedUserService, qs: typing.Any) -> typing.Any:
    """Removed machines disappear from the assigned list at once (upstream keeps them for keepInfoTime).
    Filtered in the query, so the total count (X-Total-Count) matches the rows."""
    if not getattr(self, "FOR_CACHED", False) and getattr(qs, "model", None) is UserService:
        qs = qs.exclude(state=State.REMOVED)
    return _original_odata_filter(self, qs)


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
    if Login.process_login is not _process_login:
        Login.process_login = staticmethod(_process_login)  # type: ignore[assignment]
    if AssignedUserService.odata_filter is not _odata_filter:
        AssignedUserService.odata_filter = _odata_filter  # type: ignore[method-assign]
    if AssignedUserService.get_table is not _get_table:
        AssignedUserService.get_table = _get_table  # type: ignore[method-assign]


register()
