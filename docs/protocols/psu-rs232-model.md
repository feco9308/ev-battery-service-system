# Tápegység RS232 kommunikációs modell - v0.1

## Cél

Ez a dokumentum a tápegység modulok kommunikációs modelljét írja le. A konkrét parancsok a választott tápegység típusától függenek, ezért ez első körben absztrakt modell.

```text
Linux gateway -> CAN -> fő vezérlő -> RS232 -> tápegység modul
```

A Linux gateway nem közvetlenül vezérli a tápegységet, hanem CAN-en keresztül magas szintű parancsot küld a fő vezérlőnek.

## Alap funkciók

A fő vezérlőnek ezekre a műveletekre lesz szüksége:

```text
set_voltage
set_current_limit
output_on
output_off
read_status
read_voltage
read_current
read_fault
clear_fault, ha támogatott
```

## Linux API / belső modell

```json
{
  "psu_count": 1,
  "supplies": [
    {
      "index": 0,
      "online": true,
      "output_enabled": false,
      "set_voltage_v": 400.0,
      "set_current_a": 5.0,
      "measured_voltage_v": 0.0,
      "measured_current_a": 0.0,
      "fault": false,
      "fault_code": 0
    }
  ]
}
```

## CAN PSU command terv

```text
CAN ID: 0x230
Byte0: psu_command
Byte1: psu_index
Byte2-5: parameter_u32 little-endian
Byte6: flags
Byte7: reserved
```

### psu_command

```text
0x01 SET_VOLTAGE
0x02 SET_CURRENT_LIMIT
0x03 OUTPUT_ON
0x04 OUTPUT_OFF
0x05 READ_STATUS
0x06 CLEAR_FAULT
```

## Skálázás

```text
voltage parameter: millivolt
current parameter: milliampere
```

Példa:

```text
SET_VOLTAGE 400000 -> 400.000 V
SET_CURRENT_LIMIT 5000 -> 5.000 A
```

## CAN PSU status terv

```text
CAN ID: 0x140 + psu_index
Byte0: online
Byte1: output_enabled
Byte2-3: measured_voltage_dV
Byte4-5: measured_current_cA
Byte6: fault_code
Byte7: status_flags
```

## Timeout

Ha a tápegység nem válaszol adott időn belül:

```text
fő vezérlő fault vagy warning állapotot állít
output_off parancsot próbál küldeni
veszélyes folyamatot megszakít
CAN fault frame-et küld Linux felé
```

Első javaslat:

```text
RS232 command timeout: 500 ms
PSU periodic status timeout: 2000 ms
```

## Következő teendő

- Konkrét tápegység típus és parancskészlet rögzítése.
- RS232 szint és portkiosztás tisztázása.
- Linux UI PSU panel megtervezése.
- CAN PSU command/status dekódolás implementálása.
