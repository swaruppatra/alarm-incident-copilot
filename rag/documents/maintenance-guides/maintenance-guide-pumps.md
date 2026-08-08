---
title: Maintenance Guide — Boiler Feed Pumps
doc_type: maintenance_guide
assets: [AST-0001, AST-0002]
sites: [EastRefinery]
tags: [pump, lubrication, bearing, seal, preventive-maintenance]
---

# Maintenance Guide — Boiler Feed Pumps

## Scope

Boiler Feed Pump 101 (AST-0001, Flowserve, installed 2020) and Boiler Feed Pump 102 (AST-0002, Emerson,
installed 2011), Unit 2, EastRefinery.

## Preventive Maintenance Schedule

| Task | Interval | Notes |
|---|---|---|
| Bearing lubrication check | Monthly | Verify oil level, clarity, and absence of water contamination |
| Bearing lubrication replacement | Every 6 months | Sooner if a High Vibration alarm investigation implicates lubrication |
| Suction strainer inspection | Quarterly | More frequent on Pump 101, which has a documented fouling history |
| Coupling inspection | Every 6 months | Check alignment and elastomeric element condition |
| Vibration baseline survey | Quarterly | Compare against the Engineering Standard vibration severity zones |
| Mechanical seal inspection | Annually | Check for weepage and wear |

## Asset-Specific Notes

**Pump 101** (installed 2020, lower criticality but higher alarm recurrence): this unit has generated more
recurring High Vibration alarms than Pump 102 despite being newer, traced in a prior incident to a suction
strainer restriction rather than a bearing defect. Maintenance should not assume "newer equipment" means
"lower priority" for this specific asset — see the Resolution Note on Pump 101's vibration history before
closing out a vibration work order without a strainer check.

**Pump 102** (installed 2011, medium criticality): as the older unit, standard age-related bearing wear is the
more likely driver of any vibration trend. Prioritize bearing/alignment inspection first for this asset.

## Condition-Based Triggers

Independent of the fixed schedule above, open a maintenance work order immediately if any of the following
occur:

- Three or more High Vibration alarms on the same pump within 24 hours.
- Any Low Flow alarm accompanied by audible cavitation.
- Bearing temperature trending above 90°C for more than 15 minutes.
- Discharge pressure alarm that persists after downstream valve position is confirmed correct.

## Related Documents

- Operating Procedure — Pumps
- Troubleshooting — High Vibration / High Discharge Pressure / Low Flow
- Engineering Standard — Vibration Severity Limits
- Safety — LOTO and Rotating Equipment
