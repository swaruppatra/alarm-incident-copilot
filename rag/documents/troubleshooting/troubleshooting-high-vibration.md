---
title: Troubleshooting Manual — High Vibration Alarm
doc_type: troubleshooting_manual
assets: [AST-0001, AST-0002, AST-0003, AST-0004, AST-0005, AST-0006]
sites: [EastRefinery, WestRefinery]
tags: [high-vibration, bearing, misalignment, coupling, troubleshooting]
---

# Troubleshooting Manual — High Vibration Alarm

## Applies To

All rotating equipment: Boiler Feed Pumps 101/102, Compressors C-201/C-202, Motors M-301/M-302.

## Symptom

A High Vibration alarm fires when bearing vibration (RMS velocity) exceeds the asset's configured threshold,
typically 4.5 mm/s for pumps and compressors, 4.0 mm/s for the newer Unit 5 motors. See the Engineering
Standard on vibration severity limits for the full zone classification (A/B/C/D).

## Immediate Checks (first 5 minutes)

1. Confirm the reading is not a sensor fault: check for a simultaneous alarm on an adjacent, unrelated
   measurement point on the same asset. An isolated single-sensor spike with no correlated symptom is more
   likely instrumentation than a real mechanical condition.
2. Check whether this is a recurring alarm for the same asset. Three or more High Vibration alarms on the same
   asset within a short window (the `suppression_candidate_rate` KPI's threshold) indicates a developing
   mechanical condition, not a one-off event, and should not simply be re-acknowledged.
3. Listen and, if safe, visually inspect for obvious signs: unusual noise, visible shaft wobble, or loose
   guarding.

## Likely Causes, Ranked

1. **Bearing wear or misalignment (highest confidence).** The most common root cause across all asset types in
   this fleet. Inspect bearing alignment and lubrication condition first. On pumps, check coupling alignment
   between the driver and the pump shaft; on motors, check the mounting base for looseness.
2. **Coupling condition (secondary cause).** If the bearing inspection comes back clean, inspect the coupling
   for wear, misalignment, or degraded elastomeric elements. This is a lower-confidence cause and should only
   be pursued after bearing/alignment is ruled out.
3. **Cavitation-induced vibration (pumps only).** If the High Vibration alarm co-occurs with a Low Flow alarm
   on the same pump, treat this as a suction-side problem first — see the Low Flow troubleshooting manual —
   rather than a pure bearing/mechanical issue.
4. **Foundation or piping-induced resonance (less common).** Consider this only after bearing, coupling, and
   process-driven causes have been ruled out; it typically requires a vibration analyst with spectral data.

## Diagnostic Steps

1. Pull the vibration trend for the asset over the prior 90 days via the alarm trends tool — a slowly rising
   baseline supports bearing wear; a sudden step change supports a discrete event (e.g. a coupling failure or
   a process upset).
2. Cross-check acknowledgment history: alarms that are repeatedly acknowledged without a corrective work order
   are a documented pattern that precedes larger failures in this fleet (see the Resolution Note on Boiler
   Feed Pump 101's vibration history).
3. If available, review spectral vibration data for characteristic bearing defect frequencies before opening
   the equipment.

## Corrective Actions

- Schedule a bearing inspection and re-lubrication at the next planned outage; do not defer past two
  additional recurrences of the alarm.
- Correct shaft alignment if misalignment is confirmed.
- Replace the coupling only if bearing/alignment inspection is clean and the coupling shows physical wear.
- For critical or high-severity active alarms, open a ticket immediately rather than waiting for the next
  planned maintenance window.

## Escalation Criteria

Escalate to a mechanical engineer if vibration exceeds Zone D per the engineering standard, if the trend shows
a sudden step change rather than a gradual rise, or if the same asset has three or more unresolved High
Vibration tickets in the last 90 days.

## Related Documents

- Engineering Standard — Vibration Severity Limits
- Maintenance Guide — Pumps / Compressors and Motors
- Resolution Note — Boiler Feed Pump 101 Vibration History
- Knowledge Article — Recurring Vibration Tribal Knowledge
