"""Visible, editable default pool group.

Upstream shows pools without a pool group under a built-in heading ("General") that does not
exist in the admin UI, so it cannot get an image, comment or priority. LibreVDI creates a real
pool group "Default" once (``librevdi_ext.bootstrap``) and puts every pool without a group into it
when the pool is saved. Admins can rename, edit or delete it; if it is deleted, upstream behaviour
applies again.
"""

import logging
import typing

from django.db.models.signals import pre_save
from uds.models import ServicePool, ServicePoolGroup

DEFAULT_GROUP_NAME: typing.Final[str] = "Default"
DEFAULT_GROUP_COMMENT: typing.Final[str] = "Desktop pools without their own group (LibreVDI)"

logger = logging.getLogger(__name__)


def _put_into_default_group(sender: typing.Any, instance: ServicePool, **kwargs: typing.Any) -> None:
    if instance.servicesPoolGroup_id is None:
        group = ServicePoolGroup.objects.filter(name=DEFAULT_GROUP_NAME).first()
        if group is not None:
            instance.servicesPoolGroup = group


def register() -> None:
    pre_save.connect(_put_into_default_group, sender=ServicePool, dispatch_uid="librevdi-default-pool-group")


register()
