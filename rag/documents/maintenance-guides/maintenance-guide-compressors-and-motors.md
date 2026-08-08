---
title: Maintenance Guide — Compressors and Motors
doc_type: maintenance_guide
assets: [AST-0003, AST-0004, AST-0005, AST-0006]
sites: [EastRefinery, WestRefinery]
tags: [compressor, motor, lubrication, bearing, preventive-maintenance]
---

# Maintenance Guide — Compressors and Motors

## Section 1: Compressors C-201 / C-202 (Unit 3, EastRefinery)

| Task | Interval | Notes |
|---|---|---|
| Vibration baseline survey | Monthly | Compressors run continuously; trend more tightly than intermittent pumps |
| Anti-surge valve function test | Quarterly | Stuck-closed valves are a documented cause of High Discharge Pressure alarms |
| Bearing lubrication | Every 6 months | |
| Discharge line inspection | Annually | Check for internal fouling contributing to restricted flow |

**C-201** (Sulzer, installed 2015, medium criticality): higher operating hours than C-202; prioritize
discharge-pressure-related checks given its documented resolution history (see Resolution Note — Compressor
C-201 Discharge Pressure).

**C-202** (Flowserve, installed 2014, low criticality): standard schedule, no elevated alarm history to date.

## Section 2: Motors M-301 / M-302 (Unit 5, WestRefinery)

| Task | Interval | Notes |
|---|---|---|
| Vibration baseline survey | Quarterly | Both units installed 2021; establish clean baselines early |
| Bearing lubrication | Annually | Newer sealed-bearing design requires less frequent service than the Unit 2/3 fleet |
| Electrical connection torque check | Annually | Relevant given the documented correlated-trip history between these two motors |
| Insulation resistance test | Annually | |

**Correlated-asset note**: M-301 and M-302 share upstream electrical distribution and have a documented
history of correlated trip events (see Resolution Note — Motor M-301/M-302 Correlated Trip). When scheduling
maintenance on one, check whether the shared electrical feed or breaker is due for inspection as well.

## Condition-Based Triggers (both sections)

- Vibration alarm exceeding Zone C per the Engineering Standard on vibration severity limits.
- Discharge pressure approaching the mechanical relief setpoint on either compressor.
- A trip or alarm on one of M-301/M-302 without a corresponding process cause — check the other unit and the
  shared electrical feed before returning the tripped unit to service.

## Related Documents

- Operating Procedure — Compressors and Motors
- Troubleshooting — High Discharge Pressure / High Vibration
- Engineering Standard — Vibration Severity Limits / Pressure and Flow Margins
- Resolution Note — Compressor C-201 Discharge Pressure
- Resolution Note — Motor M-301/M-302 Correlated Trip
