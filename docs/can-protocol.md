# CAN protokoll - első vázlat

## Cél

A CAN busz feladata a Linux gateway és a fő STM32 vezérlő közötti megbízható, determinisztikus kommunikáció.

A CAN-en ne JSON vagy szöveges protokoll fusson, hanem fix bináris frame-ek.

## Kommunikációs szerepek

```text
Linux gateway = magas szintű vezérlő / UI / adatnaplózó
Fő STM32 vezérlő = biztonsági és valós idejű vezérlő
```

A Linux gateway parancsokat küld, a fő vezérlő végrehajt vagy elutasít. A fő vezérlő önállóan kapcsol le hiba esetén.

## Javasolt CAN ID tartományok

```text
0x100 - fő vezérlő rendszer státusz
0x110 - cellafeszültség adatcsomagok
0x120 - pack feszültség / áram / teljesítmény
0x130 - relé állapotok
0x140 - tápegység állapotok
0x150 - balanszer állapotok
0x160 - hőmérséklet adatok
0x180 - hiba / fault frame

0x200 - Linux parancs fő vezérlőnek
0x210 - mérési parancsok
0x220 - relé parancsok
0x230 - tápegység parancsok
0x240 - balanszer parancsok
0x250 - konfigurációs parancsok
0x260 - heartbeat / watchdog
```

## Heartbeat

A Linux gateway periodikusan heartbeat frame-et küld.

```text
CAN ID: 0x260
Byte0: sequence counter
Byte1: command enable flags
Byte2..7: reserved
```

Ha a fő vezérlő nem kap heartbeat-et adott időn belül, akkor biztonságos állapotba lép.

## Fő vezérlő státusz

```text
CAN ID: 0x100
Byte0: system_state
Byte1: fault_state
Byte2: relay_flags
Byte3: supply_flags
Byte4: balancer_flags
Byte5: active_profile
Byte6: uptime low
Byte7: uptime high
```

## Áram / feszültség / teljesítmény

```text
CAN ID: 0x120
Byte0-1: pack_voltage_dV vagy scale szerint
Byte2-3: current_cA, signed
Byte4-5: power_W
Byte6: measurement_valid
Byte7: reserved
```

## Cellafeszültség adatcsomag

Sima CAN esetén darabolni kell.

```text
CAN ID: 0x110 + packet_index
Byte0: packet_index
Byte1: first_cell_index
Byte2-3: cell_1_mV
Byte4-5: cell_2_mV
Byte6-7: cell_3_mV
```

CAN-FD esetén egy frame több cellát is tartalmazhat.

## Parancs frame

```text
CAN ID: 0x200
Byte0: command_id
Byte1: command_seq
Byte2: parameter_0
Byte3: parameter_1
Byte4: parameter_2
Byte5: parameter_3
Byte6: flags
Byte7: checksum vagy reserved
```

## Alap parancsok

```text
0x01 = PING
0x02 = GET_STATUS
0x03 = CLEAR_FAULT
0x10 = MEASUREMENT_START
0x11 = MEASUREMENT_STOP
0x20 = RELAY_ALL_OFF
0x21 = RELAY_SET
0x30 = SUPPLY_OUTPUT_OFF
0x31 = SUPPLY_SET_VOLTAGE
0x32 = SUPPLY_SET_CURRENT
0x40 = BALANCER_ALL_OFF
0x41 = BALANCER_SET_CELL
0xF0 = EMERGENCY_STOP
```

## Biztonsági elv

Minden veszélyes parancs csak akkor hajtható végre, ha:

- nincs aktív fault,
- érvényes heartbeat érkezik,
- a fő vezérlő állapota engedi,
- a parancs paraméterei határértéken belül vannak.
