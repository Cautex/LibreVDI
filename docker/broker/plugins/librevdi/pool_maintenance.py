"""Maintenance per desktop pool.

Upstream knows maintenance only for a whole provider (every pool on that hypervisor). LibreVDI adds
maintenance for a single pool without changing the admin UI: a pool with the tag ``maintenance``
(or ``wartung``) in its "Tags" field is in maintenance. Upstream then handles it like provider
maintenance: the pool is shown "in maintenance" in the portal and the admin list, no new
connections are made, running sessions are not disconnected. The LibreVDI power policy pauses for
services that have a pool in maintenance.
"""

from __future__ import annotations

import typing

from django.db.models import Q
from uds.models import ServicePool

MAINTENANCE_TAGS: typing.Final[tuple[str, ...]] = ("maintenance", "wartung")

_original_is_in_maintenance = ServicePool.is_in_maintenance


def tagged_for_maintenance(pool: typing.Any) -> bool:
    if getattr(pool, "pk", None) is None:  # unsaved pool: no tags yet
        return False
    query = Q()
    for tag in MAINTENANCE_TAGS:
        query |= Q(tag__iexact=tag)
    return pool.tags.filter(query).exists()


def _is_in_maintenance(self: ServicePool) -> bool:
    return _original_is_in_maintenance(self) or tagged_for_maintenance(self)


def register() -> None:
    if ServicePool.is_in_maintenance is not _is_in_maintenance:
        ServicePool.is_in_maintenance = _is_in_maintenance  # type: ignore[method-assign]


register()
