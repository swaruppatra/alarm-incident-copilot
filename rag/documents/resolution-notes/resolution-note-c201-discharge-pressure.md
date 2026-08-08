---
title: Resolution Note — Compressor C-201 Discharge Pressure History
doc_type: resolution_note
assets: [AST-0003]
sites: [EastRefinery]
tags: [high-discharge-pressure, compressor, resolution-history, root-cause]
---

# Resolution Note — Compressor C-201 Discharge Pressure History

## Background

Compressor C-201 (AST-0003, Sulzer, Unit 3, EastRefinery) has had a recurring High Discharge Pressure alarm
pattern tied to its anti-surge valve. This note documents the resolution history for use as contributing-factor
evidence on future incidents involving this asset.

## Incident — Anti-Surge Valve Sticking

Discharge pressure alarms recurred over several weeks, initially diagnosed each time as a downstream valve
restriction per the standard troubleshooting manual's highest-confidence cause. Downstream valve position was
repeatedly confirmed correct, which did not match the standard explanation.

Further investigation found the anti-surge valve was intermittently sticking in a near-closed position under
certain load conditions, which drove discharge pressure up in a way that mimicked a downstream restriction on
the trend data, since both produce a similar pressure signature at the discharge transmitter.

**Resolution:** anti-surge valve actuator serviced and stroke-tested; a quarterly function test was added to
the Maintenance Guide for this specific asset going forward, beyond the general schedule applied to C-202.

**Lesson:** for C-201 specifically, if downstream valve position is confirmed correct and discharge pressure
remains elevated, check anti-surge valve function before escalating further — this is a known asset-specific
pattern that isn't yet reflected as the default first check in the general troubleshooting manual.

## Related Documents

- Troubleshooting — High Discharge Pressure
- Engineering Standard — Pressure and Flow Margins
- Maintenance Guide — Compressors and Motors
- Operating Procedure — Compressors and Motors
