import datetime
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "docker", "broker", "plugins", "librevdi"))
import power_policy as pp

NOW = datetime.datetime(2026, 11, 23, 12, 0, tzinfo=datetime.UTC)


def _a(vmid, in_use, minutes_ago):
    since = None if minutes_ago is None else NOW - datetime.timedelta(minutes=minutes_ago)
    return pp.Assignment(vmid=vmid, in_use=in_use, in_use_since=since)


def test_shutdown_only_logged_off_long_enough_and_running():
    assignments = [
        _a("101", False, 45),  # logged off 45 min ago, running -> shut down
        _a("102", False, 10),  # logged off too recently
        _a("103", True, 120),  # user still logged in (or disconnected session)
        _a("104", False, 60),  # already stopped
        _a("105", False, None),  # never had a login/logoff timestamp
        _a("", False, 60),  # no machine id
    ]
    running = {"101": True, "102": True, "103": True, "104": False, "105": True}
    assert pp.machines_to_shut_down(assignments, lambda v: running[v], NOW, 30) == ["101"]


def test_shutdown_delay_zero_means_immediately():
    assert pp.machines_to_shut_down([_a("101", False, 0)], lambda v: True, NOW, 0) == ["101"]


def test_always_on_starts_only_stopped():
    stopped = {"101": True, "102": False}
    assert pp.machines_to_start(["101", "102", ""], lambda v: stopped[v]) == ["101"]
