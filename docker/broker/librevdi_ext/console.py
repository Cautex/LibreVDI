"""stdout log handler used by the LibreVDI logging configuration.

Importing this module also imports ``uds.core.util.log`` first. Upstream relies on that import
order: its file handlers live there and are imported by Django's logging setup before the app
registry is populated. Without it, ``uds.core.consts`` and ``uds.core.util.model`` import each
other in the wrong order (circular import). See docs/upstream-notes.md.

This module must only be imported by ``logging.config`` (i.e. after settings are loaded).
"""

import logging

import uds.core.util.log  # noqa: F401  # pylint: disable=unused-import


class ConsoleHandler(logging.StreamHandler):
    """Plain ``StreamHandler``; exists to anchor the import above."""
