# CAN gateway protokoll - v0.1

## Cél

A CAN protokoll köti össze a Linux gateway alkalmazást és a fő STM32 vezérlőt.

```text
Linux gateway <-> CAN / CAN-FD <-> fő STM32 vezérlő
```

A Linux gateway magas szintű parancsokat küld és állapotot jelenít meg. A fő vezérlő végzi a valós idejű és biztonsági döntéseket.

## Alapelv

- A CAN frame bináris, nem JSON.
- A web/API oldalon már lehet JSON.
- A skálázások fixek legyenek.
- Minden veszélyes parancsnak legyen visszaigazolása vagy fault állapota.
- A fő vezérlő heartbeat hiányában biztonságos állapotba lép.

## CAN ID tartományok

```text
0x100  Main controller system status
0x110  Cell voltage packet base
0x120  Pack measurement
0x130  Relay/output status
0x140  PSU status
0x150  Balancer summary status
0x160  Temperature packet base
0x180  Fault frame

0x200  Command base
0x210  Measurement command
0x220  Output/relay command
0x230  PSU command
0x240  Balancer command
0x250  Configuration command
0x260  Gateway heartbeat
0x270  Command acknowledge
```

## 0x100 - System status

Irány: fő vezérlő -> Linux gateway

```text
Byte0: system_state
Byte1: fault_state
Byte2: relay_flags
Byte3: supply_flags
Byte4: balancer_flags
Byte5: active_profile
Byte6: uptime_s low
Byte7: uptime_s high
```

### system_state

```text
0   BOOT
1   SELF_TEST
2   IDLE
3   MEASURE
4   CHARGE
5   BALANCE
100 FAULT
101 EMERGENCY_OFF
```

## 0x120 - Pack measurement

Irány: fő vezérlő -> Linux gateway

```text
Byte0-1: pack_voltage_dV, unsigned, 0.1 V / bit
Byte2-3: current_cA, signed, 0.01 A / bit
Byte4-5: power_W, unsigned, 1 W / bit
Byte6: measurement_valid, 0/1
Byte7: reserved
```

Példa:

```text
pack_voltage_dV = 3600 -> 360.0 V
current_cA = 1234 -> 12.34 A
power_W = 4442 -> 4442 W
```

## 0x110 + packet_index - Cell voltage packet

Irány: fő vezérlő -> Linux gateway

Sima CAN esetén egy frame 3 cellafeszültséget tartalmaz.

```text
CAN ID: 0x110 + packet_index
Byte0: packet_index
Byte1: first_cell_index
Byte2-3: cell_0_mV
Byte4-5: cell_1_mV
Byte6-7: cell_2_mV
```

Cellák indexelése 0-tól indul a szoftverben.

## 0x180 - Fault frame

Irány: fő vezérlő -> Linux gateway

```text
Byte0: fault_code
Byte1: fault_detail
Byte2: source
Byte3: severity
Byte4: related_index
Byte5: reserved
Byte6: uptime_s low
Byte7: uptime_s high
```

### severity

```text
0 INFO
1 WARNING
2 ERROR
3 CRITICAL
```

## 0x260 - Gateway heartbeat

Irány: Linux gateway -> fő vezérlő

```text
Byte0: sequence
Byte1: enable_flags
Byte2-7: reserved
```

A fő vezérlőnek meg kell szakítania a veszélyes műveleteket, ha a heartbeat adott időn túl nem érkezik.

Javasolt timeout első verzióban:

```text
1000 ms
```

## 0x200 - Command frame

Irány: Linux gateway -> fő vezérlő

```text
Byte0: command_id
Byte1: command_seq
Byte2-5: parameter_u32 little-endian
Byte6: flags
Byte7: reserved
```

### command_id

```text
0x01 PING
0x02 GET_STATUS
0x03 CLEAR_FAULT
0x10 MEASUREMENT_START
0x11 MEASUREMENT_STOP
0x20 RELAY_ALL_OFF
0x30 SUPPLY_OUTPUT_OFF
0x40 BALANCER_ALL_OFF
0xF0 EMERGENCY_STOP
```

## 0x270 - Command acknowledge

Irány: fő vezérlő -> Linux gateway

```text
Byte0: command_id
Byte1: command_seq
Byte2: result_code
Byte3: reject_reason
Byte4-7: reserved
```

### result_code

```text
0 OK
1 REJECTED
2 BUSY
3 INVALID_STATE
4 INVALID_PARAMETER
5 FAULT_ACTIVE
```

## Következő teendő

- A `linux-gateway/app/can_protocol.py` igazítása ehhez a dokumentumhoz.
- Unit tesztek a dekódolásra.
- CAN szimulátor bővítése cella és fault frame-ekkel.
