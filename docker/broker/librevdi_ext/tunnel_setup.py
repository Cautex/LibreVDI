"""Registers the bundled tunnel server with the broker and creates its tunnel group.

Run by the compose service ``tunnel-init`` (broker image, command ``tunnel-setup``) once the
broker web service is healthy. Idempotent:

1. logs in as super user (REST),
2. registers a tunnel server (``/tunnel/register``) – the broker returns the same token again
   for an already registered hostname – and writes the token for the tunnel container,
3. ensures a tunnel group with the public address clients connect to
   (``LIBREVDI_TUNNEL_HOST`` / ``LIBREVDI_TUNNEL_PORT``) and assigns the server to it.

Afterwards administrators create a transport "RDP (tunneled)" with this tunnel and add it to the
pools that should be reached through LibreVDI.
"""

import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request

BROKER = os.environ.get("LIBREVDI_TUNNEL_BROKER_URL", "http://proxy:8081/uds/rest")
GROUP_NAME = os.environ.get("LIBREVDI_TUNNEL_GROUP", "LibreVDI Tunnel")
HOSTNAME = os.environ.get("LIBREVDI_TUNNEL_SERVER_NAME", "librevdi-tunnel")
TOKEN_FILE = os.environ.get("LIBREVDI_TUNNEL_TOKEN_FILE", "/run/librevdi-tunnel/token")
ZERO_AUTH = "00000000-0000-0000-0000-000000000000"


class Broker:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.token = ""

    def call(self, method: str, path: str, body: object | None = None) -> object:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["X-Auth-Token"] = self.token
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)  # noqa: S310
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310  # nosec: internal URL
            raw = resp.read()
        return json.loads(raw) if raw else None


def _log(msg: str) -> None:
    print(f"librevdi: tunnel-setup: {msg}", flush=True)


def wait_for_broker(broker: Broker, user: str, password: str) -> None:
    deadline = time.time() + 180
    while True:
        try:
            result = broker.call("POST", "/auth/login", {"auth_id": ZERO_AUTH, "username": user, "password": password})
            broker.token = result["token"]  # type: ignore[index]
            return
        except (urllib.error.URLError, KeyError, TypeError, ValueError) as e:
            if time.time() > deadline:
                raise SystemExit(f"broker not reachable or login failed: {e}") from e
            time.sleep(3)


def main() -> int:
    host = os.environ.get("LIBREVDI_TUNNEL_HOST", "")
    port = int(os.environ.get("LIBREVDI_TUNNEL_PORT", "4443"))
    user = os.environ.get("LIBREVDI_ROOT_USER", "root")
    password = os.environ.get("LIBREVDI_ROOT_PASSWORD", "")
    if not host or not password:
        _log("LIBREVDI_TUNNEL_HOST and LIBREVDI_ROOT_PASSWORD are required")
        return 1

    broker = Broker(BROKER)
    wait_for_broker(broker, user, password)

    # Server registration: "ip" identifies the server, clients never use it
    own_ip = socket.gethostbyname(socket.gethostname())
    token = broker.call("POST", "/tunnel/register", {"ip": own_ip, "hostname": HOSTNAME, "port": port})
    if isinstance(token, dict):
        token = token.get("result") or token.get("token")
    if not isinstance(token, str) or not token:
        _log(f"unexpected registration answer: {token!r}")
        return 1
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(token)
    _log(f"tunnel server '{HOSTNAME}' registered")

    groups = broker.call("GET", "/tunnels/tunnels") or []
    group = next((g for g in groups if g.get("name") == GROUP_NAME), None)  # type: ignore[union-attr]
    if group is None:
        group = broker.call(
            "POST",
            "/tunnels/tunnels",
            {"name": GROUP_NAME, "comments": "Created by LibreVDI", "tags": [], "host": host, "port": port},
        )
        _log(f"tunnel group '{GROUP_NAME}' created ({host}:{port})")
    elif group.get("host") != host or int(group.get("port", 0)) != port:
        _log(f"tunnel group '{GROUP_NAME}' exists with {group.get('host')}:{group.get('port')} – left unchanged")
    group_id = group["id"]  # type: ignore[index]
    _log(f"tunnel group '{GROUP_NAME}' ready")

    unassigned = broker.call("GET", f"/tunnels/tunnels/{group_id}/tunnels") or []
    for server in unassigned:  # type: ignore[union-attr]
        if HOSTNAME in (server.get("hostname"), server.get("name")):
            broker.call("POST", f"/tunnels/tunnels/{group_id}/assign/{server['id']}")
    _log(f"tunnel server assigned to '{GROUP_NAME}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
