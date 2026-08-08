import itertools
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker

from simulator.app.models.alarms import Alarm
from simulator.app.models.analytics import KPIDefinition
from simulator.app.models.assets import AssetMetadata
from simulator.app.models.recommendations import Recommendation
from ticketing.app.models import Ticket, TicketStatus

SEED = 42
OUT_DIR = Path(__file__).resolve().parent.parent / "test-data"
# Naive on purpose: already-ingested test-data/*.json was generated against this
# anchor; adding tzinfo would change every isoformat() string and diverge from it.
NOW = datetime(2026, 8, 8)  # noqa: DTZ001

# Explicit per-asset site/unit/type mapping — NOT a modulo cycle. Each unit is
# deliberately tied to the chaining scenario / default request body that
# references it:
#   Unit 2 -> pumps        (base collection's flood-analysis example body uses "Unit 2")
#   Unit 3 -> compressors  (base collection's calculation-code/generate example uses "Unit 3")
#   Unit 5 -> motors        (CHAIN-08 "Motor Assets Unit 5" needs both motors here, together)
ASSET_DEFS = {
    "Boiler Feed Pump 101": {"site": "EastRefinery", "unit": "Unit 2", "asset_type": "pump"},
    "Boiler Feed Pump 102": {"site": "EastRefinery", "unit": "Unit 2", "asset_type": "pump"},
    "Compressor C-201": {"site": "EastRefinery", "unit": "Unit 3", "asset_type": "compressor"},
    "Compressor C-202": {"site": "EastRefinery", "unit": "Unit 3", "asset_type": "compressor"},
    "Motor M-301": {"site": "WestRefinery", "unit": "Unit 5", "asset_type": "motor"},
    "Motor M-302": {"site": "WestRefinery", "unit": "Unit 5", "asset_type": "motor"},
}

SEVERITIES = ["info", "low", "medium", "high", "critical"]
MANUFACTURERS = ["Flowserve", "Sulzer", "Emerson", "Siemens"]
CRITICALITIES = ["low", "medium", "high", "critical"]
ALARM_NAMES = ["High Vibration", "High Discharge Pressure", "Low Flow"]
ALARM_STATUS = ["active", "acknowledged", "cleared"]

_id_counter = itertools.count(1)


def next_alarm_id() -> str:
    return f"ALM-{next(_id_counter):05d}"


def get_asset(assets: list[AssetMetadata], asset_name: str) -> AssetMetadata:
    return next(a for a in assets if a.asset_name == asset_name)


# ---------- assets ----------

def generate_assets(fake: Faker) -> list[AssetMetadata]:
    assets = []
    for i, (asset_name, defs) in enumerate(ASSET_DEFS.items(), start=1):
        assets.append(AssetMetadata(
            asset_id=f"AST-{i:04d}",
            asset_name=asset_name,
            site=defs["site"],
            unit=defs["unit"],
            asset_type=defs["asset_type"],
            manufacturer=random.choice(MANUFACTURERS),
            install_date=fake.date_between(start_date="-15y", end_date="-1y").isoformat(),
            criticality=random.choice(CRITICALITIES),
        ))
    return assets


# ---------- baseline "noise" alarms ----------

def generate_noise_alarms(fake: Faker, assets: list[AssetMetadata], count: int) -> list[Alarm]:
    alarms = []
    for _ in range(count):
        asset = random.choice(assets)
        start = NOW - timedelta(days=random.randint(0, 90), hours=random.randint(0, 23), minutes=random.randint(0, 59))
        alarms.append(Alarm(
            alarm_id=next_alarm_id(),
            asset_id=asset.asset_id,
            site=asset.site,
            alarm_name=random.choice(ALARM_NAMES),
            severity=random.choices(SEVERITIES, weights=[10, 20, 30, 25, 15])[0],
            status=random.choices(ALARM_STATUS, weights=[10, 20, 70])[0],
            start_time=start,
            end_time=start + timedelta(minutes=random.randint(5, 240)),
            ack_delay_seconds=random.randint(30, 1800),
        ))
    return alarms


# ---------- engineered "signal" patterns ----------
# Pure random placement won't reliably trigger the analytics endpoints'
# thresholds (flood needs a tight burst, rationalization needs real
# recurrence/staleness, correlation needs real co-occurrence). Each function
# below deliberately manufactures one of those patterns.

def inject_flood_burst(assets: list[AssetMetadata]) -> list[Alarm]:
    """12 alarms inside a 10-minute window on a Unit 2 asset -> triggers
    /alarms/flood-analysis (threshold_count=10, rolling_window_minutes=10)."""
    asset = next(a for a in assets if a.unit == "Unit 2")
    window_start = NOW - timedelta(days=10, hours=3)
    return [
        Alarm(
            alarm_id=next_alarm_id(),
            asset_id=asset.asset_id,
            site=asset.site,
            alarm_name=random.choice(ALARM_NAMES),
            severity=random.choice(["high", "critical"]),
            status="active",
            start_time=window_start + timedelta(minutes=i * 0.8),
            end_time=None,
            ack_delay_seconds=None,
        )
        for i in range(12)
    ]


def inject_recurring_pattern(assets: list[AssetMetadata]) -> list[Alarm]:
    """'High Vibration' on Boiler Feed Pump 101, 7 times over 90 days, mostly
    unacknowledged -> triggers /alarms/rationalization-candidates
    (recurrence_threshold=5, stale_minutes_threshold=180)."""
    asset = get_asset(assets, "Boiler Feed Pump 101")
    alarms = []
    for i in range(7):
        start = NOW - timedelta(days=i * 11 + 2, hours=random.randint(0, 23))
        alarms.append(Alarm(
            alarm_id=next_alarm_id(),
            asset_id=asset.asset_id,
            site=asset.site,
            alarm_name="High Vibration",
            severity=random.choice(["high", "critical"]),
            status="active",  # stays unacknowledged
            start_time=start,
            end_time=None,
            ack_delay_seconds=random.randint(200 * 60, 400 * 60),  # well past 180 min
        ))
    return alarms


def inject_correlated_pair(assets: list[AssetMetadata]) -> list[Alarm]:
    """'High Vibration' on Motor M-301 firing ~10 min before 'High Discharge
    Pressure' on Motor M-302, three times -> triggers /alarms/correlation
    (lag_window_minutes=15, min_support=1)."""
    m301 = get_asset(assets, "Motor M-301")
    m302 = get_asset(assets, "Motor M-302")
    alarms = []
    for i in range(3):
        base = NOW - timedelta(days=i * 20 + 5, hours=6)
        alarms.append(Alarm(
            alarm_id=next_alarm_id(), asset_id=m301.asset_id, site=m301.site,
            alarm_name="High Vibration", severity="high", status="cleared",
            start_time=base, end_time=base + timedelta(minutes=20), ack_delay_seconds=180,
        ))
        alarms.append(Alarm(
            alarm_id=next_alarm_id(), asset_id=m302.asset_id, site=m302.site,
            alarm_name="High Discharge Pressure", severity="high", status="cleared",
            start_time=base + timedelta(minutes=10), end_time=base + timedelta(minutes=30), ack_delay_seconds=210,
        ))
    return alarms


def inject_guaranteed_priority_alarm(assets: list[AssetMetadata]) -> list[Alarm]:
    """One critical + active alarm on an EastRefinery asset, started recently
    -> guarantees "highest-priority active alarm in EastRefinery" resolves to
    something real, and anchors the mandatory 90-day E2E scenario."""
    asset = get_asset(assets, "Boiler Feed Pump 101")
    return [Alarm(
        alarm_id=next_alarm_id(),
        asset_id=asset.asset_id,
        site=asset.site,
        alarm_name="High Vibration",
        severity="critical",
        status="active",
        start_time=NOW - timedelta(hours=2),
        end_time=None,
        ack_delay_seconds=None,
    )]


def generate_alarms(fake: Faker, assets: list[AssetMetadata]) -> list[Alarm]:
    alarms = generate_noise_alarms(fake, assets, count=160)
    alarms += inject_flood_burst(assets)                 # +12
    alarms += inject_recurring_pattern(assets)            # +7
    alarms += inject_correlated_pair(assets)              # +6
    alarms += inject_guaranteed_priority_alarm(assets)    # +1
    return alarms  # 186 total; adjust the noise count above if you want closer to 200


# ---------- tickets ----------

TICKET_LABELS_BY_ALARM = {
    "High Vibration": ["vibration", "bearing", "mechanical"],
    "High Discharge Pressure": ["pressure", "discharge", "process"],
    "Low Flow": ["flow", "suction", "process"],
}

TICKET_RESOLUTION_NOTES = {
    "High Vibration": "Realigned coupling and replaced worn bearing; vibration levels returned to baseline after re-commissioning.",
    "High Discharge Pressure": "Cleared a partially closed downstream valve; discharge pressure normalized within 30 minutes.",
    "Low Flow": "Cleaned the suction strainer and confirmed no cavitation on restart; flow restored to nominal.",
}

TICKET_STATUSES: list[TicketStatus] = ["open", "in_progress", "resolved", "closed"]

_ticket_counter = itertools.count(1)


def next_ticket_id() -> str:
    return f"TKT-{next(_ticket_counter):04d}"


def generate_tickets(assets: list[AssetMetadata], alarms: list[Alarm]) -> list[Ticket]:
    """One ticket per (asset, alarm_name) combo with a real matching alarm,
    plus a few generic asset-only tickets with no alarm_id, so search has
    both alarm-linked and plain historical data to match against."""
    alarms_by_asset_and_name: dict[tuple[str, str], list[Alarm]] = {}
    for alarm in alarms:
        alarms_by_asset_and_name.setdefault((alarm.asset_id, alarm.alarm_name), []).append(alarm)

    tickets: list[Ticket] = []
    for asset in assets:
        for alarm_name in ALARM_NAMES:
            candidates = alarms_by_asset_and_name.get((asset.asset_id, alarm_name))
            if not candidates:
                continue
            alarm = random.choice(candidates)
            ticket_status = random.choice(TICKET_STATUSES)
            resolved = ticket_status in ("resolved", "closed")
            created = alarm.start_time + timedelta(minutes=random.randint(5, 60))
            tickets.append(Ticket(
                ticket_id=next_ticket_id(),
                summary=f"{alarm_name} on {asset.asset_name}",
                description=(
                    f"Investigate {alarm_name.lower()} reported on {asset.asset_name} "
                    f"({asset.site}, {asset.unit})."
                ),
                status=ticket_status,
                labels=TICKET_LABELS_BY_ALARM[alarm_name],
                asset_id=asset.asset_id,
                alarm_id=alarm.alarm_id,
                priority=random.choice(["low", "medium", "high"]),
                created_at=created,
                updated_at=created + timedelta(hours=random.randint(1, 48)),
                resolution_notes=TICKET_RESOLUTION_NOTES[alarm_name] if resolved else None,
            ))

    generic_tickets = [
        ("Routine inspection follow-up", "Scheduled inspection flagged a minor anomaly requiring follow-up.", ["maintenance", "inspection"]),
        ("Spare parts request", "Requesting spare parts be staged ahead of next planned outage.", ["logistics", "planning"]),
        ("Documentation update needed", "Asset documentation is out of date and needs revision.", ["documentation"]),
    ]
    for asset, (summary, description, labels) in zip(assets[:3], generic_tickets, strict=False):
        created = NOW - timedelta(days=random.randint(1, 60))
        tickets.append(Ticket(
            ticket_id=next_ticket_id(),
            summary=f"{summary} — {asset.asset_name}",
            description=description,
            status=random.choice(TICKET_STATUSES),
            labels=labels,
            asset_id=asset.asset_id,
            alarm_id=None,
            priority=random.choice(["low", "medium"]),
            created_at=created,
            updated_at=created + timedelta(hours=random.randint(1, 24)),
            resolution_notes=None,
        ))
    return tickets


# ---------- static reference fixtures (not random, just committed directly) ----------

KPI_DEFINITIONS = [
    KPIDefinition(kpi_name="alarm_count", description="Total number of alarms in the period", unit="count"),
    KPIDefinition(kpi_name="recurring_rate", description="Share of alarms that are repeat occurrences of the same alarm_name on the same asset", unit="ratio"),
    KPIDefinition(kpi_name="avg_ack_delay", description="Average time between an alarm starting and being acknowledged", unit="seconds"),
    KPIDefinition(kpi_name="suppression_candidate_rate", description="Share of alarms belonging to an (asset_id, alarm_name) pair recurring at least 3 times in the window", unit="ratio"),
    KPIDefinition(kpi_name="critical_count", description="Number of alarms with severity == critical in the period", unit="count"),
]

RECOMMENDATION_PLAYBOOK: dict[str, list[Recommendation]] = {
    "High Vibration": [
        Recommendation(action="Inspect bearing alignment and lubrication", rationale="High vibration is most commonly caused by bearing wear or misalignment", confidence=0.8),
        Recommendation(action="Check coupling condition", rationale="Secondary cause if bearing inspection is clean", confidence=0.4),
    ],
    "High Discharge Pressure": [
        Recommendation(action="Check downstream valve position and line blockage", rationale="Elevated discharge pressure typically indicates restricted flow downstream", confidence=0.75),
    ],
    "Low Flow": [
        Recommendation(action="Inspect suction strainer and check for cavitation", rationale="Low flow with stable pressure often indicates a suction-side restriction", confidence=0.7),
    ],
}


def main() -> None:
    random.seed(SEED)
    Faker.seed(SEED)
    fake = Faker()

    assets = generate_assets(fake)
    alarms = generate_alarms(fake, assets)
    tickets = generate_tickets(assets, alarms)

    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "assets.json").write_text(
        json.dumps([a.model_dump(mode="json") for a in assets], indent=2)
    )
    (OUT_DIR / "alarms.json").write_text(
        json.dumps([a.model_dump(mode="json") for a in alarms], indent=2)
    )
    (OUT_DIR / "kpi_definitions.json").write_text(
        json.dumps([k.model_dump() for k in KPI_DEFINITIONS], indent=2)
    )
    (OUT_DIR / "recommendation_playbook.json").write_text(
        json.dumps(
            {name: [r.model_dump() for r in recs] for name, recs in RECOMMENDATION_PLAYBOOK.items()},
            indent=2,
        )
    )
    (OUT_DIR / "tickets.json").write_text(
        json.dumps([t.model_dump(mode="json") for t in tickets], indent=2)
    )
    print(
        f"Wrote {len(assets)} assets, {len(alarms)} alarms, "
        f"{len(KPI_DEFINITIONS)} KPI defs, {len(RECOMMENDATION_PLAYBOOK)} playbook entries, "
        f"{len(tickets)} tickets to {OUT_DIR}"
    )


if __name__ == "__main__":
    main()
