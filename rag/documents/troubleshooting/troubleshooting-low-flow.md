---
title: Troubleshooting Manual — Low Flow Alarm
doc_type: troubleshooting_manual
assets: [AST-0001, AST-0002]
sites: [EastRefinery]
tags: [low-flow, cavitation, suction-strainer, troubleshooting]
---

# Troubleshooting Manual — Low Flow Alarm

## Applies To

Boiler Feed Pumps 101/102 (Unit 2, EastRefinery). Low Flow is primarily a pump-side alarm in this fleet; it is
not currently configured on the Unit 3 compressors or Unit 5 motors.

## Symptom

A Low Flow alarm fires when suction or discharge flow falls below the minimum continuous flow rate (40 gpm)
for the asset. Left uncorrected, sustained low flow risks cavitation damage to the impeller.

## Immediate Checks (first 5 minutes)

1. Confirm the flow reading against pump discharge pressure — a genuine low-flow condition with stable or
   rising discharge pressure supports a suction-side restriction rather than a flow-meter fault.
2. Listen for cavitation noise at the pump casing (a rattling or "marbles in a can" sound); this is a strong
   confirming signal and warrants immediate attention regardless of the numeric flow reading.
3. Check whether the alarm coincides with a High Vibration alarm on the same pump — the two are frequently
   linked in this fleet.

## Likely Cause (highest confidence)

Low flow with stable pressure most often indicates a suction-side restriction. Inspect the suction strainer for
fouling and check for cavitation. Boiler Feed Pump 101 in particular has a documented history of partial
strainer fouling — see the Resolution Note on its vibration history, which traces one recurring vibration
episode back to an under-diagnosed strainer restriction.

## Diagnostic Steps

1. Check suction strainer differential pressure against baseline; a rising differential confirms fouling.
2. Confirm the suction valve is fully open and has not drifted closed.
3. Check upstream tank/vessel level to rule out a low suction head condition rather than a strainer issue.
4. If strainer and suction path are confirmed clear, check for internal wear (impeller or wear-ring erosion)
   reducing effective flow at a given speed.

## Corrective Actions

- Clean or replace the suction strainer; this is the most common fix and typically requires only a short
  isolation, not a full pump outage.
- Correct upstream level or valve position issues where identified.
- If internal wear is confirmed, schedule an impeller/wear-ring inspection at the next planned outage unless
  the flow deficit is severe enough to warrant immediate action.

## Escalation Criteria

Escalate immediately if cavitation noise is present and flow remains below minimum for more than 10 minutes —
continued operation under cavitation risks impeller damage that will convert a strainer-cleaning job into a
much larger repair.

## Related Documents

- Troubleshooting — High Vibration
- Operating Procedure — Pumps
- Maintenance Guide — Pumps
- Resolution Note — Boiler Feed Pump 101 Vibration History
