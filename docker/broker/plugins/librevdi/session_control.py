"""Session control for persistent desktops: log off a session or show a message in it.

Upstream can already talk to the agent in a desktop (``UserServiceManager.request_logoff``,
``send_message`` -> HTTPS to the agent on port 43910), but only if the assigned service has the
agent's *callback address* (``comms_url``) and certificate. Managed agents register it on "ready";
**unmanaged** agents (persistent desktops) never do, so upstream silently skips these requests.

The unmanaged agent does send everything needed when it starts (``actor/v3/unmanaged``: its IP
addresses and MACs, listener port, secret; the broker answers with a new TLS certificate). The hook
on ``Unmanaged.action`` remembers that per MAC in the storage of the persistent service and sets
the callback address on the assigned service of that machine - at agent start and, for machines
assigned later, at the next login (``apply_comms``, called from the login hook).

Admin access (the compiled admin UI has a fixed set of buttons; own buttons follow with the own UI):

* REST: ``POST …/servicespools/<pool>/services/<assigned service>/logoff`` and ``…/message``
  (JSON ``{"message": "…"}``), admin permission
* command line in the broker container: ``python -m librevdi_ext.session`` (list / logoff / message)
"""

from __future__ import annotations

import logging
import typing

from uds.core.exceptions.actor import NoActorComms
from uds.core.managers.userservice_helpers import comms
from uds.models import Service, ServiceTokenAlias, UserService
from uds.REST.methods.actor_v3 import Unmanaged, get_list_of_ids

from .proxmox_persistent import TYPE_TYPE

logger = logging.getLogger(__name__)

COMMS_KEY: typing.Final[str] = "librevdi-comms-"

_original_unmanaged_action = Unmanaged.action


def _service_for_token(token: str) -> typing.Any:
    alias = ServiceTokenAlias.objects.filter(alias=token).first()
    if alias:
        return alias.service
    return Service.objects.filter(token=token).first()


def comms_url(info: dict[str, typing.Any]) -> str:
    return f"https://{info['ip']}:{int(info['port'])}/actor/{info['secret']}"


def interfaces_info(params: dict[str, typing.Any], certificate: str) -> dict[str, dict[str, typing.Any]]:
    """MAC (lower case) -> callback data, from the parameters of an ``unmanaged`` request."""
    result = {}
    for iface in params.get("id") or []:
        mac, ip = str(iface.get("mac") or "").lower(), str(iface.get("ip") or "")
        if mac and ip:
            result[mac] = {"ip": ip, "port": int(params["port"]), "secret": str(params["secret"]), "cert": certificate}
    return result


def apply_comms(userservice: typing.Any) -> bool:
    """Sets the remembered callback address on an assigned persistent desktop. True if known."""
    try:
        service_model = userservice.deployed_service.service
        if service_model.data_type != TYPE_TYPE:
            return False
        info = service_model.get_instance().storage.read_pickled(COMMS_KEY + str(userservice.unique_id or "").lower())
        if not info:
            return False
        url = comms_url(info)
        if userservice.get_comms_endpoint() != url or userservice.properties.get("cert") != info["cert"]:
            userservice.set_comms_info(url, info["secret"])
            userservice.properties["cert"] = info["cert"]
            logger.info("librevdi: agent callback address set for %s", userservice.friendly_name)
        return True
    except Exception:  # never break agent start or login
        logger.exception("librevdi: setting agent callback address of %s", userservice)
        return False


def _unmanaged_action(self: Unmanaged) -> typing.Any:
    response = _original_unmanaged_action(self)
    try:
        result = response.get("result") if isinstance(response, dict) else None
        certificate = result.get("certificate") if isinstance(result, dict) else None
        if certificate:
            service_model = _service_for_token(str(self._params.get("token") or ""))
            if service_model is not None and service_model.data_type == TYPE_TYPE:
                storage = service_model.get_instance().storage
                for mac, info in interfaces_info(self._params, certificate).items():
                    storage.save_pickled(COMMS_KEY + mac, info)
                ids = get_list_of_ids(self)
                for userservice in UserService.objects.filter(
                    deployed_service__service=service_model, unique_id__in=ids
                ):
                    apply_comms(userservice)
    except Exception:  # the agent must start even if this fails
        logger.exception("librevdi: remembering the agent callback address")
    return response


def _send(userservice: typing.Any, method: str, data: dict[str, typing.Any]) -> str:
    """'sent', 'no-connection' (agent never registered / old agent) or 'failed' (agent unreachable)."""
    apply_comms(userservice)
    try:
        answer = comms._execute_actor_request(userservice, method, data=data)  # noqa: SLF001
    except NoActorComms:
        return "no-connection"
    return "failed" if answer is None else "sent"


def logoff(userservice: typing.Any) -> str:
    return _send(userservice, "logout", {})


def message(userservice: typing.Any, text: str) -> str:
    return _send(userservice, "message", {"message": text})


def _rest_logoff(self: typing.Any, parent: typing.Any, item: str) -> dict[str, str]:
    from uds.core.util.model import process_uuid  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    userservice = parent.userServices.get(uuid=process_uuid(item))
    return {"result": logoff(userservice)}


def _rest_message(self: typing.Any, parent: typing.Any, item: str) -> dict[str, str]:
    from uds.core.util.model import process_uuid  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    text = str(self._params.get("message") or "").strip()
    if not text:
        return {"result": "empty-message"}
    userservice = parent.userServices.get(uuid=process_uuid(item))
    return {"result": message(userservice, text[:1000])}


def register() -> None:
    # pylint: disable=import-outside-toplevel
    from uds.core import types
    from uds.REST.methods.user_services import AssignedUserService

    if Unmanaged.action is not _unmanaged_action:
        Unmanaged.action = _unmanaged_action  # type: ignore[method-assign]
    names = {m.name for m in AssignedUserService.CUSTOM_METHODS}
    for name, description in (
        ("logoff", "LibreVDI: log off the session in the machine (persistent desktops)"),
        ("message", "LibreVDI: show a message in the session (persistent desktops), body {'message': '...'}"),
    ):
        if name not in names:
            AssignedUserService.CUSTOM_METHODS.append(
                types.rest.ModelCustomMethod(name, method=types.rest.CustomMethodMethod.POST, description=description)
            )
    AssignedUserService.logoff = _rest_logoff  # type: ignore[attr-defined]
    AssignedUserService.message = _rest_message  # type: ignore[attr-defined]


register()
