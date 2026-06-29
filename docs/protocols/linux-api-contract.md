# Linux gateway API szerződés - v0.1

## Cél

Ez a dokumentum rögzíti a web UI és a Linux backend közötti API-t.

```text
Web UI <-> HTTP REST / WebSocket <-> Linux gateway backend <-> CAN <-> fő vezérlő
```

## REST végpontok

## GET /api/status

Visszaadja az aktuális gateway és fő vezérlő állapotot.

### Response példa

```json
{
  "connected": true,
  "system_state": 2,
  "fault_state": 0,
  "relay_flags": 0,
  "supply_flags": 0,
  "balancer_flags": 0,
  "active_profile": 0,
  "uptime_s": 123,
  "pack_voltage_v": 360.0,
  "current_a": 12.34,
  "power_w": 4442.0,
  "measurement_valid": true,
  "last_can_rx_ms": 123456789
}
```

## POST /api/command

Parancs küldése a fő vezérlőnek.

### Request

```json
{
  "command": "emergency_stop",
  "value": 0
}
```

### Támogatott parancsok első verzióban

```text
ping
clear_fault
measurement_start
measurement_stop
relay_all_off
supply_output_off
balancer_all_off
emergency_stop
```

### Response

```json
{
  "ok": true,
  "command": "emergency_stop"
}
```

## GET /api/cells

Későbbi végpont cellafeszültségekhez.

### Response terv

```json
{
  "valid": true,
  "cell_count": 96,
  "min_cell_v": 3.812,
  "max_cell_v": 3.957,
  "delta_v": 0.145,
  "cells": [
    {"index": 0, "voltage_v": 3.812, "valid": true},
    {"index": 1, "voltage_v": 3.815, "valid": true}
  ]
}
```

## GET /api/faults

Későbbi végpont aktív és korábbi hibákhoz.

### Response terv

```json
{
  "active_fault": true,
  "faults": [
    {
      "code": 12,
      "source": "cell_measure",
      "severity": "ERROR",
      "message": "Cell measurement timeout",
      "timestamp_ms": 123456789
    }
  ]
}
```

## WebSocket /ws/status

Élő státusz adatfolyam.

### Message

A payload megegyezik a `/api/status` response formátumával.

## UI biztonsági szabályok

A következő parancsokhoz UI oldali megerősítés kell:

```text
measurement_start
supply_output_on később
relay kézi kapcsolás később
balancer indítás később
emergency_stop kivétel: azonnal fusson
```

## Backend biztonsági szabályok

A backend nem kerülheti meg a fő vezérlő állapotgépét. Ha a fő vezérlő elutasít egy parancsot, azt a UI-n láthatóvá kell tenni.

## Következő teendő

- Command ACK bevezetése.
- A `/api/command` később ne csak küldje a parancsot, hanem várja vagy megjelenítse az ACK állapotot.
- `/api/cells` modell előkészítése a CAN cellafesz frame-ekhez.
