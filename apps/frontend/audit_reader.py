import json
import sqlite3

from apps.frontend.config import get_settings

# Read-only mirror of apps.backend.audit's audit_log schema. Duplicated
# rather than imported because apps/frontend is its own Docker build context
# (see docker-compose.yml's copilot-frontend service) and can't reach into
# apps/backend at build time; for local (non-Docker) dev this reads the same
# file apps.backend.audit writes, via the shared AUDIT_DB_PATH env var.
COLUMNS = [
    "id", "thread_id", "event_type", "name", "status", "duration_seconds", "payload", "prompt_version", "created_at",
]


def read_audit_trail(thread_id: str | None = None, limit: int = 200) -> list[dict]:
    """Read recent audit_log rows, newest first.

    Args:
        thread_id (str | None): restrict to one conversation thread, or None for all threads.
        limit (int): maximum rows to return.

    Returns:
        list[dict]: audit_log rows as plain dicts, with "payload" decoded from
            JSON where possible. Empty list if the audit database doesn't
            exist yet (e.g. no conversation has happened).
    """
    settings = get_settings()
    if not settings.audit_db_path.exists():
        return []

    query = "SELECT * FROM audit_log"
    params: list = []
    if thread_id:
        query += " WHERE thread_id = ?"
        params.append(thread_id)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    conn = sqlite3.connect(f"file:{settings.audit_db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(row) for row in conn.execute(query, params).fetchall()]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()

    for row in rows:
        try:
            row["payload"] = json.loads(row["payload"]) if row["payload"] else None
        except json.JSONDecodeError:
            pass
    return rows
