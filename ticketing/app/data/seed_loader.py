import json
import sqlite3
from pathlib import Path

TEST_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "test-data"


def load_fixtures(conn: sqlite3.Connection) -> None:
    """Load test-data/tickets.json into the tickets table.

    Args:
        conn: an open sqlite3 connection.

    Returns:
        None
    """
    tickets = json.loads((TEST_DATA_DIR / "tickets.json").read_text())
    rows = [{**t, "labels": json.dumps(t["labels"])} for t in tickets]
    conn.executemany(
        """INSERT INTO tickets
           (ticket_id, summary, description, status, labels, asset_id, alarm_id, priority,
            created_at, updated_at, resolution_notes)
           VALUES (:ticket_id, :summary, :description, :status, :labels, :asset_id, :alarm_id, :priority,
                   :created_at, :updated_at, :resolution_notes)""",
        rows,
    )
    conn.commit()
