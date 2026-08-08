---
title: Operating Procedure — Boiler Feed Pumps (Unit 2, EastRefinery)
doc_type: operating_procedure
assets: [AST-0001, AST-0002]
sites: [EastRefinery]
units: [Unit 2]
tags: [pump, boiler-feed-pump, startup, shutdown, operating-envelope]
---

# Operating Procedure — Boiler Feed Pumps (Unit 2, EastRefinery)

## Scope

This procedure applies to Boiler Feed Pump 101 (AST-0001, Flowserve, installed 2020) and Boiler Feed Pump 102
(AST-0002, Emerson, installed 2011), both located in Unit 2, EastRefinery. These pumps run in a duty/standby
configuration and supply feedwater to the boiler drum.

## Normal Operating Envelope

- Discharge pressure: 145–165 psig. Sustained readings above 175 psig should be treated as abnormal.
- Suction flow: minimum continuous flow is 40 gpm; operating below this for more than 5 minutes risks
  cavitation, particularly on Pump 101 where the suction strainer has a documented history of partial fouling.
- Bearing vibration: normal operation stays under 4.5 mm/s RMS. See the Engineering Standard on vibration
  severity limits for the full zone classification.
- Bearing temperature: normal range is 60–85°C. Trending above 90°C for longer than 15 minutes warrants an
  immediate vibration and lubrication check.

## Startup Sequence

1. Confirm suction valve is fully open and suction strainer differential pressure is within normal range.
2. Verify lubrication reservoir level and oil condition (clear, no visible contamination).
3. Bump-start the motor briefly to confirm rotation direction, then bring the pump to full speed.
4. Open the discharge valve gradually over 30–60 seconds while monitoring discharge pressure ramp.
5. Confirm discharge pressure stabilizes within the normal operating envelope before handing control back to
   the automated control loop.
6. Log startup vibration and bearing temperature readings as the baseline for the run.

## Shutdown Sequence

1. Reduce flow demand gradually where possible rather than a hard stop, to limit water-hammer risk on the
   discharge line.
2. Close the discharge valve before stopping the motor.
3. Allow the pump to coast to a stop; do not apply mechanical braking.
4. If the pump will be idle for more than 24 hours, isolate and drain per the site's lockout/tagout procedure
   (see Safety — LOTO and Rotating Equipment).

## Monitoring Points and Escalation

Operators should treat the following as early-warning indicators requiring a work order, not just an
acknowledged alarm:

- Three or more High Vibration alarms on the same pump within a 24-hour window — this matches the
  `suppression_candidate_rate` KPI's recurrence threshold and should be escalated to maintenance rather than
  repeatedly acknowledged.
- Any Low Flow alarm accompanied by an audible cavitation noise ("marbles in a can") at the pump casing.
- Discharge pressure alarms that persist after downstream valve position is confirmed correct — this points
  toward an internal pump or piping issue rather than a process condition.

## Related Documents

- Troubleshooting — High Vibration
- Troubleshooting — Low Flow
- Maintenance Guide — Pumps
- Engineering Standard — Vibration Severity Limits
- Resolution Note — Boiler Feed Pump 101 Vibration History
