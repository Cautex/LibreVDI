"""Container healthcheck.

``python -m librevdi_ext.healthcheck``          checks the web process (GET /readyz)
``python -m librevdi_ext.healthcheck --tasks``  checks that the task manager process runs
"""

import os
import sys
import urllib.request


def check_web() -> bool:
    port = os.environ.get("LIBREVDI_PORT", "8000")
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/readyz", timeout=4) as resp:  # nosec: local
            return resp.status == 200
    except Exception:  # pylint: disable=broad-except
        return False


def check_tasks() -> bool:
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                if b"task_manager" in f.read():
                    return True
        except OSError:
            continue
    return False


if __name__ == "__main__":
    ok = check_tasks() if "--tasks" in sys.argv else check_web()
    sys.exit(0 if ok else 1)
