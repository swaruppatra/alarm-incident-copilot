import json
import sqlite3
from pathlib import Path

TEST_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "test-data"


def load_fixtures(conn: sqlite3.Connection) -> None:
    assets = json.loads((TEST_DATA_DIR / "assets.json").read_text())
    alarms = json.loads((TEST_DATA_DIR / "alarms.json").read_text())
    kpi_definitions = json.loads((TEST_DATA_DIR / "kpi_definitions.json").read_text())
    playbook = json.loads((TEST_DATA_DIR / "recommendation_playbook.json").read_text())

    conn.executemany(
        """INSERT INTO assets
        (asset_id, asset_name, site, unit, asset_type, manufacturer, install_date, criticality)
        VALUES (:asset_id, :asset_name, :site, :unit, :asset_type, :manufacturer, :install_date, :criticality)""",
        assets,
    )
    conn.executemany(
        """INSERT INTO alarms
           (alarm_id, asset_id, site, alarm_name, severity, status, start_time, end_time, ack_delay_seconds)
           VALUES (:alarm_id, :asset_id, :site, :alarm_name, :severity, :status, :start_time, :end_time, :ack_delay_seconds)""",
        alarms,
    )
    conn.executemany(
        "INSERT INTO kpi_definitions (kpi_name, description, unit) VALUES (:kpi_name, :description, :unit)",
        kpi_definitions,
    )
    # recommendation_playbook.json is {alarm_name: [recommendation, ...]} — flatten
    # to one row per recommendation before inserting.
    playbook_rows = [
        {"alarm_name": alarm_name, **rec}
        for alarm_name, recs in playbook.items()
        for rec in recs
    ]
    conn.executemany(
        """INSERT INTO recommendation_playbook (alarm_name, action, rationale, confidence)
           VALUES (:alarm_name, :action, :rationale, :confidence)""",
        playbook_rows,
    )
    conn.commit()