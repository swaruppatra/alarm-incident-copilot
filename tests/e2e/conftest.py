"""Shared setup for tests/e2e.

Mirrors tests/integration/conftest.py's rationale: mcp-servers/alarm-management
builds its HTTP client (and therefore reads Settings()) at *module import
time*, so the required env vars must exist before that module is imported.
simulator.app.config.Settings also reads ALARM_API_TOKEN (same env var name
by design -- the simulator validates the same bearer token the MCP client
sends) and DB_PATH.

DB_PATH is pointed at a fresh temp sqlite file so the orchestration test
seeds its own deterministic copy of test-data/*.json rather than depending
on (or mutating) whatever ./var/alarm_simulator.sqlite3 a real docker-compose
run might have produced.
"""

import os
import tempfile
from pathlib import Path

_tmp_db = Path(tempfile.mkdtemp(prefix="alarm-e2e-")) / "alarm_simulator.sqlite3"

os.environ.setdefault("DB_PATH", str(_tmp_db))
os.environ.setdefault("ALARM_API_TOKEN", "test-alarm-token")
# Never actually dialed -- the client's transport is swapped for an
# in-process ASGI transport before any request is made. Still required
# because AlarmManagementClient.__init__ reads it unconditionally.
os.environ.setdefault("ALARM_API_BASE_URL", "http://simulator.e2e.invalid")
os.environ.setdefault("TICKETING_API_URL", "http://ticketing.e2e.invalid")
os.environ.setdefault("TICKETING_API_TOKEN", "test-ticketing-token")
