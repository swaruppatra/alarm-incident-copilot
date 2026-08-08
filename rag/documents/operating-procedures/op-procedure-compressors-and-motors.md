---
title: Operating Procedure — Compressors and Motors (Unit 3 & Unit 5)
doc_type: operating_procedure
assets: [AST-0003, AST-0004, AST-0005, AST-0006]
sites: [EastRefinery, WestRefinery]
units: [Unit 3, Unit 5]
tags: [compressor, motor, startup, shutdown, operating-envelope]
---

# Operating Procedure — Compressors and Motors

## Section 1: Compressors C-201 / C-202 (Unit 3, EastRefinery)

Compressor C-201 (AST-0003, Sulzer, installed 2015) and C-202 (AST-0004, Flowserve, installed 2014) provide
process gas compression for Unit 3.

### Normal Operating Envelope

- Discharge pressure: 210–240 psig under normal load. Readings above 250 psig for more than 2 minutes require
  operator intervention.
- Suction pressure: should track within 5 psig of the upstream process target; a falling suction pressure
  combined with a rising discharge pressure usually indicates a downstream restriction rather than a
  compressor fault.
- Vibration: normal operation stays under 4.5 mm/s RMS on the drive-end bearing.

### Startup

1. Confirm suction and discharge block valves are open and the anti-surge valve is in automatic control.
2. Start the driver and allow the compressor to reach rated speed before loading.
3. Load gradually while watching discharge pressure and surge margin.
4. Log baseline vibration and discharge pressure once stable.

### Shutdown

1. Unload the compressor (reduce discharge pressure toward suction conditions) before stopping the driver.
2. Confirm the anti-surge valve opens fully on shutdown to prevent reverse flow through the machine.
3. For extended outages, isolate per the site's lockout/tagout procedure.

## Section 2: Motors M-301 / M-302 (Unit 5, WestRefinery)

Motor M-301 (AST-0005, Siemens, installed 2021) and M-302 (AST-0006, Flowserve, installed 2021) are drive
motors for correlated process equipment and are known to trip together under certain fault conditions — see
the Resolution Note on the M-301/M-302 correlated trip for the documented history.

### Normal Operating Envelope

- Vibration: under 4.0 mm/s RMS given both units are relatively new (installed 2021).
- Bearing temperature: 55–80°C normal range.
- Load current: should track the driven equipment's process demand; a current spike without a corresponding
  process change points toward an electrical or mechanical fault rather than a process condition.

### Startup

1. Confirm the driven equipment is ready to accept load and any associated interlocks are clear.
2. Start the motor and confirm smooth ramp to rated speed with no unusual noise or vibration.
3. Log baseline vibration and current draw.

### Shutdown

1. Reduce driven-equipment load before stopping the motor where the process allows it.
2. For extended outages, isolate per the site's lockout/tagout procedure.

### Correlated-Asset Note

Because M-301 and M-302 share upstream electrical distribution, an alarm on one should prompt a check of the
other before assuming an isolated fault — this is the basis for the "show open tickets linked to correlated
assets" workflow.

## Related Documents

- Troubleshooting — High Discharge Pressure
- Troubleshooting — High Vibration
- Maintenance Guide — Compressors and Motors
- Resolution Note — Compressor C-201 Discharge Pressure
- Resolution Note — Motor M-301/M-302 Correlated Trip
