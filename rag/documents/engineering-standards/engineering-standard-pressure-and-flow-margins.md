---
title: Engineering Standard — Pressure and Flow Margins
doc_type: engineering_standard
assets: [AST-0001, AST-0002, AST-0003, AST-0004]
sites: [EastRefinery]
tags: [engineering-standard, pressure, flow, relief-margin, cavitation]
---

# Engineering Standard — Pressure and Flow Margins

## Discharge Pressure Design Margins

| Asset | Normal Range (psig) | Alarm Threshold (psig) | Mechanical Relief Setpoint (psig) |
|---|---|---|---|
| Boiler Feed Pump 101/102 | 145–165 | 175 | 210 |
| Compressor C-201/C-202 | 210–240 | 250 | 285 |

The gap between the alarm threshold and the mechanical relief setpoint is intentional operating margin. An
alarm that persists and continues trending upward toward the relief setpoint should be escalated immediately
rather than waiting for a standard troubleshooting cycle — relief valve lifting has downstream safety and
environmental reporting implications beyond the equipment itself.

## Minimum Flow / Cavitation Margin (Pumps Only)

| Asset | Minimum Continuous Flow (gpm) | Cavitation Risk Onset |
|---|---|---|
| Boiler Feed Pump 101/102 | 40 | Sustained operation below minimum flow for more than 10 minutes |

Cavitation risk is time-dependent, not instantaneous — a brief dip below minimum flow during a transient
(e.g. startup) is expected and not itself damaging. Sustained operation below the minimum flow threshold is
what causes impeller erosion, which is why the Low Flow troubleshooting manual's escalation criterion is based
on duration (10 minutes) rather than the alarm firing alone.

## How These Margins Relate to Alarm Configuration

Alarm thresholds in this fleet are deliberately set with margin below both the mechanical relief setpoint and
the point of actual equipment damage, to give operators time to intervene. When investigating why an alarm
threshold seems conservative relative to a given reading, this margin is the reason — it is not a
miscalibration.

## Related Documents

- Troubleshooting — High Discharge Pressure / Low Flow
- Operating Procedure — Pumps / Compressors and Motors
- Resolution Note — Compressor C-201 Discharge Pressure
