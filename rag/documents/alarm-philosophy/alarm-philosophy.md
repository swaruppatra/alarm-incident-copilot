---
title: Alarm Philosophy — Priority, Severity, and Rationalization
doc_type: alarm_philosophy
assets: []
sites: [EastRefinery, WestRefinery]
tags: [alarm-philosophy, severity, priority, flood, chattering, rationalization, kpi]
---

# Alarm Philosophy — Priority, Severity, and Rationalization

## Purpose

This document defines how alarms are classified, prioritized, and evaluated for nuisance/rationalization
across both sites, and explains the KPIs used to measure alarm system health. It follows the general
principles of ISA-18.2 / EEMUA 191 style alarm management, adapted for this fleet's scale.

## Severity Levels

Alarms are classified into four severity levels: `low`, `medium`, `high`, and `critical`.

- **Critical**: immediate risk to safety, environment, or major equipment damage; requires operator response
  within minutes.
- **High**: significant operational impact if not addressed within the current shift.
- **Medium**: notable deviation from normal operation; should be investigated but is not immediately urgent.
- **Low**: informational or early-warning; useful for trending but does not require immediate action.

## Priority Scoring

Priority combines severity with asset criticality and alarm recency/frequency. An alarm on a `critical`
severity level against a high-criticality asset is scored highest; the same severity on a low-criticality
asset with no recent recurrence is scored lower. This is why "the highest-priority active alarm" is not always
simply the most recent `critical` alarm — asset criticality and alarm history both factor in.

## Flood Conditions

An alarm flood is declared when an asset (or unit) generates an unusually high concentration of alarms in a
short window — in this fleet, a burst of roughly 10 or more alarms within a 10-minute window on a single asset
or unit is treated as a flood condition. Floods typically indicate either a genuine process upset or a
misconfigured/oscillating instrument, and both should be investigated before simply acknowledging every alarm
in the burst.

## Recurring and Chattering Alarms

An alarm is considered **recurring** when the same alarm name repeats on the same asset multiple times within
an analysis window. The `recurring_rate` KPI measures the share of alarms in a period that are repeat
occurrences of the same alarm on the same asset.

An (asset, alarm_name) pair recurring **three or more times** within the analysis window is flagged as a
**suppression candidate** — the `suppression_candidate_rate` KPI reports the share of alarms belonging to such
a pair. Suppression candidates are not necessarily nuisance alarms to be silenced; they should first be
investigated as a possible developing mechanical or process condition (see the High Vibration troubleshooting
manual for a concrete example), and only rationalized down if investigation confirms the alarm is genuinely
low-value.

## Key KPI Reference

- **alarm_count** — total number of alarms in the period.
- **recurring_rate** — share of alarms that are repeat occurrences of the same alarm_name on the same asset.
- **avg_ack_delay** — average time between an alarm starting and being acknowledged; a rising trend indicates
  operator alarm fatigue or an understaffed shift and should prompt a review of nuisance alarm volume.
- **suppression_candidate_rate** — share of alarms belonging to an (asset, alarm_name) pair recurring at least
  3 times in the window.
- **critical_count** — number of alarms with severity `critical` in the period.

## Rationalization Guidance

An alarm should be considered for rationalization (retuning the threshold, adding a delay timer, or in rare
cases suppressing it) only when: it has a high `recurring_rate` for a specific asset, investigation has
confirmed no underlying developing fault, and the alarm provides no actionable information beyond what a
lower-priority or trended indication already provides. Rationalization decisions should be documented, since
an alarm suppressed without investigation is the most common root cause of a missed real failure in
post-incident reviews.

## Related Documents

- Troubleshooting — High Vibration
- Engineering Standard — Vibration Severity Limits
