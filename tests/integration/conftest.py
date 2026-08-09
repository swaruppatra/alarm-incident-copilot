"""Shared setup for tests/integration.

Both mcp-servers/alarm-management/mcp.py and mcp-servers/ticketing/mcp.py
build their HTTP client (and therefore call Settings()) at *module import
time* -- `client = AlarmManagementClient()` / `client = TicketingClient()`
run as soon as the module is imported, not inside a function. Settings()
has no defaults for the API base URL / token fields, so importing either
module without these env vars already set raises a pydantic ValidationError
before a single test can even be collected.

This conftest sets them (if not already set, e.g. via a real .env) before
pytest imports any test module in this directory, since pytest always
imports a directory's conftest.py before collecting its test files.
"""

import os

os.environ.setdefault("ALARM_API_BASE_URL", "http://test-alarm-api.invalid")
os.environ.setdefault("ALARM_API_TOKEN", "test-alarm-token")
os.environ.setdefault("TICKETING_API_URL", "http://test-ticketing-api.invalid")
os.environ.setdefault("TICKETING_API_TOKEN", "test-ticketing-token")
