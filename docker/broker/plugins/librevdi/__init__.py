"""LibreVDI extensions for the OpenUDS broker.

This package is copied to ``uds/plugins/librevdi`` in the broker image. OpenUDS imports every
package below ``uds.plugins`` when the app starts (see ``uds/plugins/__init__.py``), so no upstream
file has to be changed.
"""

from . import assigned_view as assigned_view  # noqa: F401
from . import downloads as downloads  # noqa: F401
from . import pool_groups as pool_groups  # noqa: F401
from . import pool_maintenance as pool_maintenance  # noqa: F401
from . import power_policy as power_policy  # noqa: F401, E402
from . import proxmox_persistent as proxmox_persistent  # noqa: F401
from . import session_control as session_control  # noqa: F401

power_policy.register()
