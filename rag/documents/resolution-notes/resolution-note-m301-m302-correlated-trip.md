---
title: Resolution Note — Motor M-301/M-302 Correlated Trip History
doc_type: resolution_note
assets: [AST-0005, AST-0006]
sites: [WestRefinery]
tags: [motor, correlated-alarm, electrical, resolution-history, root-cause]
---

# Resolution Note — Motor M-301/M-302 Correlated Trip History

## Background

Motors M-301 (AST-0005) and M-302 (AST-0006), Unit 5, WestRefinery, share upstream electrical distribution and
have a documented history of alarms occurring together in a short window rather than independently. This note
documents the resolution and is directly relevant to correlation-analysis and "show open tickets linked to
correlated assets" workflows.

## Incident — Correlated Vibration/Current Events

Alarms on M-301 and M-302 occurred within minutes of each other on multiple occasions, initially investigated
as two independent mechanical issues since both are similar-vintage motors (both installed 2021) and both
alarms presented as vibration/current anomalies.

Independent mechanical investigation of each motor individually found nothing conclusive. The correlation
across two otherwise-independent assets was the key clue: investigation shifted to the shared upstream
electrical feed and found a loose connection at a shared distribution breaker, causing a voltage sag that
briefly affected both motors simultaneously whenever a large downstream load stepped in.

**Resolution:** electrical connection re-torqued and thermally scanned under load to confirm the fix; the
shared breaker was added to the annual electrical connection torque check referenced in the Maintenance Guide.

**Lesson:** when M-301 and M-302 alarm within a short window of each other, check the shared electrical feed
before pursuing two parallel independent mechanical investigations — this correlated-pair pattern has a known,
documented shared root cause on this specific pair of assets, distinct from how correlation should generally
be interpreted for unrelated asset pairs.

## Related Documents

- Operating Procedure — Compressors and Motors
- Maintenance Guide — Compressors and Motors
- Troubleshooting — High Vibration
