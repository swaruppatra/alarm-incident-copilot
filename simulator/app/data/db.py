import sqlite3
from collections.abc import Iterator
from pathlib import Path

from simulator.app.config import get_settings
from simulator.app.data.seed_loader import load_fixtures

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    asset_id TEXT PRIMARY KEY,
    asset_name TEXT NOT NULL,
    site TEXT NOT NULL,
    unit TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    manufacturer TEXT NOT NULL,
    install_date TEXT NOT NULL,
    criticality TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alarms (
    alarm_id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL,
    site TEXT NOT NULL,
    alarm_name TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    ack_delay_seconds INTEGER
);

CREATE TABLE IF NOT EXISTS kpi_definitions (
    kpi_name TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    unit TEXT
);

CREATE TABLE IF NOT EXISTS recommendation_playbook (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alarm_name TEXT NOT NULL,
    action TEXT NOT NULL,
    rationale TEXT NOT NULL,
    confidence REAL NOT NULL
);
"""


def _resolve_db_path() -> Path:
    """Resolve the configured DB_PATH to an absolute filesystem path.

    Args:
        None

    Returns:
        Path: absolute path to the sqlite database file, parent dir created.
    """
    path = Path(get_settings().db_path)
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
        row = conn.execute("SELECT COUNT(*) FROM assets").fetchone()
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
