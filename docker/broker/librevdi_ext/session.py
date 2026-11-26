"""Sessions on persistent desktops from the command line (inside the broker container).

  docker compose exec broker-web python -m librevdi_ext.session list [--pool NAME]
  docker compose exec broker-web python -m librevdi_ext.session logoff  --pool NAME --user NAME
  docker compose exec broker-web python -m librevdi_ext.session message --pool NAME --user NAME "Text"

``--user`` is the user name as shown in the pool (e.g. ``max``; ``max@Lokal`` if names are
ambiguous). Results: ``sent`` (the agent accepted the request), ``no-connection`` (the agent has not
registered its callback address yet - restart the agent service in the machine or log in once),
``failed`` (agent not reachable: machine off, firewall port 43910 closed).
See ``uds.plugins.librevdi.session_control``.
"""

from __future__ import annotations

import argparse
import sys
import typing

import django


def _assigned(pool_name: str | None, user: str | None) -> list[typing.Any]:
    from uds.core.types.states import State  # pylint: disable=import-outside-toplevel
    from uds.models import UserService  # pylint: disable=import-outside-toplevel

    qs = UserService.objects.filter(cache_level=0, state__in=[State.USABLE, State.PREPARING]).select_related(
        "deployed_service", "user", "user__manager"
    )
    if pool_name:
        qs = qs.filter(deployed_service__name=pool_name) | qs.filter(deployed_service__short_name=pool_name)
    result = []
    for us in qs:
        owner = us.user.name if us.user else ""
        full = f"{owner}@{us.user.manager.name}" if us.user else ""
        if user and user not in (owner, full):
            continue
        result.append(us)
    return result


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m librevdi_ext.session", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)  # fmt: skip
    sub = ap.add_subparsers(dest="command", required=True)
    p_list = sub.add_parser("list", help="assigned persistent desktops and whether the agent is reachable")
    p_list.add_argument("--pool")
    for name in ("logoff", "message"):
        p = sub.add_parser(name)
        p.add_argument("--pool", required=True)
        p.add_argument("--user", required=True)
        if name == "message":
            p.add_argument("text")
    args = ap.parse_args(argv)

    django.setup()
    from uds.plugins.librevdi import session_control  # pylint: disable=import-outside-toplevel

    targets = _assigned(args.pool, getattr(args, "user", None))
    if args.command == "list":
        print(f"{'pool':<24} {'user':<20} {'machine':<20} {'in use':<7} agent connection")
        for us in targets:
            connected = session_control.apply_comms(us) or bool(us.get_comms_endpoint())
            owner = f"{us.user.name}@{us.user.manager.name}" if us.user else "-"
            print(
                f"{us.deployed_service.name:<24} {owner:<20} {us.friendly_name:<20} "
                f"{'yes' if us.in_use else 'no':<7} {'registered' if connected else 'not registered'}"
            )
        return 0
    if not targets:
        print("no assigned machine for this pool/user", file=sys.stderr)
        return 1
    if len(targets) > 1:
        print("more than one machine matches - use user@authenticator", file=sys.stderr)
        return 1
    us = targets[0]
    if args.command == "logoff":
        result = session_control.logoff(us)
    else:
        result = session_control.message(us, args.text[:1000])
    print(f"{args.command} {us.friendly_name}: {result}")
    return 0 if result == "sent" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
