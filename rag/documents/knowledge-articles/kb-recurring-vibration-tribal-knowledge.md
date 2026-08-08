---
title: Knowledge Article — Recurring Vibration, What the Manual Doesn't Tell You
doc_type: knowledge_article
assets: [AST-0001, AST-0002]
sites: [EastRefinery]
tags: [high-vibration, tribal-knowledge, misdiagnosis, pump]
---

# Recurring Vibration, What the Manual Doesn't Tell You

This is an informal knowledge-base note from the reliability team, meant to supplement (not replace) the
official Troubleshooting Manual — High Vibration.

## The Most Common Misdiagnosis

When a High Vibration alarm recurs on Boiler Feed Pump 101, the reflex response has historically been "check
the bearing" and stop there once the bearing looks acceptable on a quick visual. In practice, several past
recurring-vibration episodes on Pump 101 turned out to trace back to a partially fouled suction strainer rather
than the bearing itself — the vibration was a secondary symptom of a suction-side flow disturbance, not a
primary bearing fault. If a bearing inspection comes back clean but the alarm keeps recurring, check the
strainer differential pressure before escalating to a full bearing replacement.

## Acknowledgment Fatigue Is a Real Pattern

On a busy shift, it's tempting to acknowledge a recurring vibration alarm and move on, especially if the
numeric value is only just over threshold. The alarm philosophy document's `suppression_candidate_rate` KPI
exists precisely because this fleet has a documented history of alarms being acknowledged three, four, five
times before anyone opened a work order — by which point the underlying condition had usually progressed
further than it needed to. Treat the third occurrence of the same alarm on the same asset within a day as a
mandatory work-order trigger, not a judgment call.

## Coupling Checks Are Frequently Skipped

Because bearing inspection is the first step in the official manual, coupling condition often doesn't get
checked at all once the bearing looks fine — instead the alarm just gets rationalized as "normal for this
pump." If you're closing out a vibration ticket without a clear root cause, do the coupling check before
writing "no fault found."

## A Note on Pump 102 vs Pump 101

Pump 102 is the older unit (installed 2011) and its vibration issues, when they occur, are more consistently
bearing-wear-related — age-related wear is the more likely explanation there. Pump 101 is newer (2020) and its
vibration history is more mixed, so don't assume "newer machine, must be a sensor issue" — it has a real
mechanical/process history worth taking seriously.

## Related Documents

- Troubleshooting — High Vibration
- Alarm Philosophy
- Resolution Note — Boiler Feed Pump 101 Vibration History
