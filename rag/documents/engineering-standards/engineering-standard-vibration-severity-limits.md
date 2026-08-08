---
title: Engineering Standard — Vibration Severity Limits
doc_type: engineering_standard
assets: [AST-0001, AST-0002, AST-0003, AST-0004, AST-0005, AST-0006]
sites: [EastRefinery, WestRefinery]
tags: [engineering-standard, vibration, iso-10816, severity-zones]
---

# Engineering Standard — Vibration Severity Limits

## Basis

Vibration severity zones in this document are adapted from the general principles of ISO 10816/20816
(mechanical vibration evaluation of machines by measurements on non-rotating parts), simplified to four zones
for site use.

## Severity Zones (RMS velocity, mm/s)

| Zone | Range (mm/s RMS) | Interpretation |
|---|---|---|
| A | 0 – 2.8 | Newly commissioned or recently overhauled equipment; excellent condition |
| B | 2.8 – 4.5 | Acceptable for continuous long-term operation |
| C | 4.5 – 7.1 | Unsatisfactory for continuous operation; plan corrective action |
| D | > 7.1 | Vibration of a severity considered capable of causing damage; immediate action required |

## Asset-Class Thresholds Applied On Site

- **Boiler Feed Pumps (AST-0001, AST-0002):** High Vibration alarm threshold set at 4.5 mm/s (Zone B/C
  boundary), consistent with continuous-duty pump practice.
- **Compressors (AST-0003, AST-0004):** High Vibration alarm threshold set at 4.5 mm/s, same boundary as the
  pumps given similar duty cycle.
- **Motors (AST-0005, AST-0006):** High Vibration alarm threshold set at 4.0 mm/s, slightly tighter given both
  units are newer (installed 2021) and a lower baseline is expected and achievable.

## Using This Standard in Diagnosis

A single alarm crossing into Zone C does not by itself indicate imminent failure — sustained operation at Zone
C, or any excursion into Zone D, is what warrants immediate corrective action rather than scheduled
maintenance. When reviewing a vibration trend as part of an incident investigation, classify each reading
against these zones rather than relying on the alarm/no-alarm boundary alone, since the alarm threshold in this
fleet is deliberately set at the B/C boundary to give an early warning ahead of Zone D.

## Related Documents

- Troubleshooting — High Vibration
- Operating Procedure — Pumps / Compressors and Motors
- Maintenance Guide — Pumps / Compressors and Motors
