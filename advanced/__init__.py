"""Production blogging agent package.

Public surface (most callers should reach for these):
    from advanced import Settings, CrewService, create_app, main
"""

import os

# Opt out of CrewAI's anonymous telemetry before anything imports crewai, so no
# run metadata leaves the process. `setdefault` lets an operator override via the
# real environment if they ever want telemetry back on.
os.environ.setdefault("CREWAI_TELEMETRY_OPT_OUT", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

from advanced.api import create_app  # noqa: E402
from advanced.cli import main  # noqa: E402
from advanced.config import Settings, get_settings  # noqa: E402
from advanced.services import CrewService  # noqa: E402

__all__ = [
    "Settings",
    "get_settings",
    "CrewService",
    "create_app",
    "main",
]
