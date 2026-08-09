"""SQLite audit trail: every MCP tool call and write-confirmation decision,
tagged with the prompt_version active at the time. Written by main.py after
each /chat and /confirm call; get_audit_trail() is intended to back a future
GUI Ops tab (see the build plan's Phase 5 design).

Deliberately reads AUDIT_DB_PATH via os.environ directly rather than through
apps.backend.config.Settings, to avoid touching config.py without asking
first. Fold this into a proper pydantic-settings field if/when that's wanted
-- everything else in this repo follows that pattern and this should too.

RAG queries are NOT logged here yet. Reconstructing "what was queried, when"
from outside the graph (in main.py, by diffing citations before/after) is
fragile once citations accumulate across a whole conversation thread. The
cleaner place for that is a direct audit.log_rag_query(...) call inside
rag_docs_node itself, once nodes.py changes are approved.
"""

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from apps.backend.models import McpTraceEntry

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = Path(os.environ.get("AUDIT_DB_PATH", str(REPO_ROOT / "var" / "audit_trail.sqlite3")))


def _connect() -> sqlite3.Connection:
    """Open a connection to the audit database, creating its parent directory if needed.

    Args:
        None

    Returns:
        sqlite3.Connection: a row-factory-enabled connection to DB_PATH.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the audit_log table (and its thread_id index) if they don't exist yet.

    Safe to call on every process startup -- mirrors ticketing/app/data/db.py's init_db().

    Args:
        None

    Returns:
        None
    """
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                event_type TEXT NOT NULL,      -- 'tool_call' | 'confirmation'
                name TEXT,                      -- tool name, or the pending write's tool name
                status TEXT,                     -- 'success' | 'error' | 'approved' | 'rejected'
                duration_seconds REAL,
                payload TEXT,                      -- JSON: args/retry_count, or the pending_write payload
                prompt_version TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_thread_id ON audit_log(thread_id)")


def _insert(
    thread_id: str,
    event_type: str,
    name: str | None,
    status: str | None,
    duration_seconds: float | None,
    payload: dict,
    prompt_version: str,
) -> None:
    """Insert one audit_log row. Internal helper shared by every log_* function.

    Args:
        thread_id (str): the conversation thread this event belongs to.
        event_type (str): 'tool_call' or 'confirmation'.
        name (str | None): tool name, or the pending write's tool name.
        status (str | None): outcome status, meaning depends on event_type.
        duration_seconds (float | None): wall-clock duration, when applicable.
        payload (dict): event-specific structured detail, JSON-encoded (never full document text or secrets).
        prompt_version (str): the prompt_version active when this event happened.

    Returns:
        None
    """
    with _connect() as conn:
        conn.execute(
            """INSERT INTO audit_log
               (thread_id, event_type, name, status, duration_seconds, payload, prompt_version, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                thread_id,
                event_type,
                name,
                status,
                duration_seconds,
                json.dumps(payload, default=str),
                prompt_version,
                datetime.now(UTC).isoformat(),
            ),
        )


def log_mcp_trace(thread_id: str, entries: list[McpTraceEntry], prompt_version: str) -> None:
    """Log MCP tool-call trace entries. Pass only entries not already logged
    (main.py does this by diffing mcp_trace length before/after each graph call,
    since AgentState accumulates mcp_trace across the whole thread).

    Args:
        thread_id (str): the conversation thread these calls belong to.
        entries (list[McpTraceEntry]): the new trace entries to log.
        prompt_version (str): the prompt_version active for this turn.

    Returns:
        None
    """
    for entry in entries:
        _insert(
            thread_id,
            "tool_call",
            entry.name,
            entry.status,
            entry.duration,
            {"args": entry.args, "retry_count": entry.retry_count, "result": entry.result},
            prompt_version,
        )


def log_confirmation(thread_id: str, pending_write: dict | None, approved: bool, prompt_version: str) -> None:
    """Log a write-operation confirmation decision (approve/reject).

    Args:
        thread_id (str): the conversation thread this decision belongs to.
        pending_write (dict | None): the {"name", "args", ...} payload that was pending.
        approved (bool): the user's decision.
        prompt_version (str): the prompt_version active for this turn.

    Returns:
        None
    """
    _insert(
        thread_id,
        "confirmation",
        (pending_write or {}).get("name"),
        "approved" if approved else "rejected",
        None,
        {"pending_write": pending_write},
        prompt_version,
    )


def get_audit_trail(thread_id: str | None = None, limit: int = 200) -> list[dict]:
    """Read recent audit rows, newest first.

    Args:
        thread_id (str | None): restrict to one conversation thread, or None for all threads.
        limit (int): maximum rows to return.

    Returns:
        list[dict]: audit_log rows as plain dicts (JSON payload left as a string; caller
            can json.loads it if needed).
    """
    query = "SELECT * FROM audit_log"
    params: list = []
    if thread_id is not None:
        query += " WHERE thread_id = ?"
        params.append(thread_id)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]
