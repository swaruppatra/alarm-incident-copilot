---
title: Resolution Note — Boiler Feed Pump 101 Recurring Vibration History
doc_type: resolution_note
assets: [AST-0001]
sites: [EastRefinery]
tags: [high-vibration, pump, resolution-history, root-cause]
---

# Resolution Note — Boiler Feed Pump 101 Recurring Vibration History

## Background

Boiler Feed Pump 101 (AST-0001, Unit 2, EastRefinery) has generated more recurring High Vibration alarms than
any other asset in this document set's history. This note summarizes three prior incidents and what ultimately
resolved the pattern, for use as contributing-factor evidence on future incidents.

## Incident 1 — Initial Recurring Vibration Episode

Multiple High Vibration alarms were logged over several consecutive days, most acknowledged without a
corrective work order. When finally investigated, the bearing itself was found to be within tolerance. Root
cause was eventually traced to a partially fouled suction strainer causing intermittent cavitation, which
manifested as vibration rather than a clear Low Flow reading at the time because the flow deficit was
intermittent rather than sustained.

**Resolution:** suction strainer cleaned; vibration returned to baseline within 24 hours. No bearing work was
required.

**Lesson:** a High Vibration alarm on this specific pump should prompt a suction strainer check alongside the
standard bearing inspection, not after it.

## Incident 2 — Coupling Wear

A second recurring episode, several months later, showed a clean bearing and a clean suction strainer. The
eventual root cause was a worn elastomeric coupling element, identified only after both of the more commonly
checked items were ruled out.

**Resolution:** coupling replaced and alignment re-verified.

**Lesson:** don't stop the investigation at "bearing is fine" — the coupling check step in the official
troubleshooting manual is not optional even though it's listed as secondary-confidence.

## Incident 3 — Genuine Bearing Wear

The most recent episode did show genuine bearing wear consistent with normal end-of-life degradation,
confirmed by vibration spectral analysis showing classic bearing defect frequencies.

**Resolution:** bearing replaced at the next planned outage; lubrication schedule tightened from 6-month to
4-month intervals for this specific asset going forward, given its higher-than-average alarm recurrence
relative to its install date.

## Summary of Contributing Factors Across All Three Incidents

1. Suction strainer fouling (most common root cause for this specific asset)
2. Coupling wear (secondary, easy to miss if investigation stops early)
3. Genuine bearing wear (least common, but the one the standard manual leads with)

Any investigation of a new recurring High Vibration alarm on this asset should check all three, in the order
above, based on this asset's specific history — not strictly in the general troubleshooting manual's default
order, which is optimized for the fleet as a whole rather than this specific pump's documented pattern.

## Related Documents

- Troubleshooting — High Vibration / Low Flow
- Knowledge Article — Recurring Vibration Tribal Knowledge
- Maintenance Guide — Pumps
- Operating Procedure — Pumps
