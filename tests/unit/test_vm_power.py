import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "docker", "broker", "plugins", "librevdi"))
import vm_power as vp


def test_power_labels():
    assert vp.power_label("running") == vp.POWER_ON
    assert vp.power_label("running", None, "paused") == vp.POWER_PAUSED
    assert vp.power_label("stopped") == vp.POWER_OFF
    assert vp.power_label("stopped", "suspended", "stopped") == vp.POWER_SUSPENDED  # hibernated
    assert vp.power_label("unknown") == vp.POWER_UNKNOWN
    assert vp.power_label(None) == vp.POWER_UNKNOWN


def test_power_state_never_raises():
    class Broken:
        @property
        def deployed_service(self):
            raise RuntimeError("database gone")

    assert vp.power_state(Broken()) == vp.POWER_UNKNOWN
