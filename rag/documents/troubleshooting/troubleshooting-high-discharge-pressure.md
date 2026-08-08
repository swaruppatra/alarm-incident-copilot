---
title: Troubleshooting Manual — High Discharge Pressure Alarm
doc_type: troubleshooting_manual
assets: [AST-0001, AST-0002, AST-0003, AST-0004]
sites: [EastRefinery]
tags: [high-discharge-pressure, valve, blockage, troubleshooting]
---

# Troubleshooting Manual — High Discharge Pressure Alarm

## Applies To

Boiler Feed Pumps 101/102 (Unit 2) and Compressors C-201/C-202 (Unit 3), EastRefinery.

## Symptom

A High Discharge Pressure alarm fires when discharge pressure exceeds the asset's normal operating envelope
(165 psig for the boiler feed pumps, 240 psig for the Unit 3 compressors) for a sustained period.

## Immediate Checks (first 5 minutes)

1. Confirm the reading against a second pressure indication if available (local gauge vs. transmitter) to rule
   out a transmitter fault.
2. Check downstream valve positions — a partially closed or fully closed downstream valve is the single most
   common cause of this alarm in this fleet.
3. Check for a recent process setpoint change that could explain the reading as expected behavior rather than
   a fault.

## Likely Cause (highest confidence)

Elevated discharge pressure typically indicates restricted flow downstream of the asset. Check the downstream
valve position and inspect the line for blockage before considering any internal fault with the pump or
compressor itself. This single check resolves the majority of High Discharge Pressure alarms without requiring
equipment disassembly.

## Diagnostic Steps

1. Confirm downstream valve position matches the control system's commanded position — a valve that is stuck
   or has lost feedback will show a mismatch.
2. Trace the discharge line for any recently closed manual isolation valves, especially after maintenance work
   on downstream equipment.
3. If downstream path is confirmed clear, check for internal recirculation or minimum-flow valve
   malfunction, which can cause an apparent discharge pressure rise under low demand.
4. For compressors, check the anti-surge valve is not stuck closed, which will drive discharge pressure up
   under low-flow conditions.

## Corrective Actions

- Clear or reposition the downstream restriction; this typically requires no equipment outage.
- If a control valve is at fault, place it in manual and dispatch instrumentation to investigate the
  feedback/actuator issue.
- Only escalate to a mechanical inspection of the pump or compressor internals if the downstream path and
  control valves are confirmed healthy and the pressure remains elevated.

## Escalation Criteria

Escalate immediately if discharge pressure approaches the mechanical relief setpoint (see the Engineering
Standard on pressure and flow margins) — do not wait for a second alarm occurrence in this case, since relief
valve lifting has downstream safety and environmental implications.

## Related Documents

- Engineering Standard — Pressure and Flow Margins
- Operating Procedure — Pumps / Compressors and Motors
- Resolution Note — Compressor C-201 Discharge Pressure
