import sqlite3
from collections.abc import Iterator
from pathlib import Path

from ticketing.app.config import get_settings
from ticketing.app.data.seed_loader import load_fixtures

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id TEXT PRIMARY KEY,
    summary TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    labels TEXT NOT NULL,
    asset_id TEXT,
    alarm_id TEXT,
    priority TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    resolution_notes TEXT
);
"""


def _resolve_db_path() -> Path:
    """Resolve the configured TICKETING_DB_PATH to an absolute filesystem path.

    Args:
        None

    Returns:
        Path: absolute path to the sqlite database file, parent dir created.
    """
    path = Path(get_settings().ticketing_db_path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def init_db() -> None:
    """Create tables if missing and seed fixtures once, if the DB is empty.

    Args:
        None

    Returns:
        None
    """
    conn = sqlite3.connect(_resolve_db_path())
    try:
        conn.executescript(SCHEMA)
        row = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()
        if row[0] == 0:
            load_fixtures(conn)
    finally:
        conn.close()


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency yielding a request-scoped sqlite3 connection.

    Args:
        None

    Returns:
        Iterator[sqlite3.Connection]: connection with row_factory = sqlite3.Row.
    """
    conn = sqlite3.connect(_resolve_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
