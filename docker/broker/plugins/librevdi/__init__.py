"""LibreVDI extensions for the OpenUDS broker.

This package is copied to ``uds/plugins/librevdi`` in the broker image. OpenUDS imports every
package below ``uds.plugins`` when the app starts (see ``uds/plugins/__init__.py``), so no upstream
file has to be changed.
"""

from . import proxmox_persistent as proxmox_persistent  # noqa: F401
