# Cellánkénti balanszer UART protokoll - v0.1

## Cél

A fő vezérlő UART-on parancsokat küld a cellánkénti balanszer STM32 moduloknak.

```text
Fő vezérlő STM32 <-> UART busz / pont-pont UART <-> cell-balancer-module STM32
```

A Linux gateway első körben nem közvetlenül beszél a balanszer modulokkal. A Linux csak CAN-en keresztül kér állapotot vagy küld magas szintű parancsot a fő vezérlőnek.

## Fizikai réteg

Ezt később a hardver alapján pontosítani kell:

```text
baudrate: 115200 első javaslat
adat: 8 bit
paritás: none
stop: 1
flow control: none
```

## Keretformátum

Bináris keret CRC-vel.

```text
Byte0: 0xA5 start byte
Byte1: address
Byte2: command
Byte3: length
Byte4..N: payload
Last-2: crc low
Last-1: crc high
```

CRC javaslat:

```text
CRC-16/CCITT-FALSE
```

## Címzés

```text
0x00 broadcast
0x01..0xFE modul címek
0xFF reserved
```

Broadcast parancsokra normál esetben ne válaszoljon minden modul egyszerre, kivéve ha külön időosztás van definiálva.

## Parancsok

```text
0x01 PING
0x02 GET_STATUS
0x03 RESET_FAULT
0x10 OUTPUT_OFF
0x11 BALANCE_ON
0x12 BALANCE_OFF
0x20 SET_TARGET_VOLTAGE
0x21 SET_CURRENT_LIMIT
0x30 GET_TEMPERATURE
0x31 GET_MEASUREMENT
```

## GET_STATUS response payload

```text
Byte0: module_state
Byte1: fault_code
Byte2-3: cell_voltage_mV
Byte4-5: temperature_cdegC, signed, 0.01 C / bit
Byte6-7: current_mA, signed
```

## module_state

```text
0 BOOT
1 IDLE
2 BALANCING
3 CHARGING
4 DISABLED
100 FAULT
```

## Timeout

A balanszer modul minden veszélyes kimenetet kikapcsol, ha adott időn belül nem kap érvényes parancsot vagy keepalive-ot.

Első javaslat:

```text
1000 ms
```

## Hibaelv

Kommunikációs hiba esetén:

```text
balanszer kimenet OFF
fault vagy disabled állapot
fő vezérlő felé hiba visszajelzés
```

## Linux oldal kapcsolata

A Linux gateway ezt csak közvetetten látja CAN-en:

```text
Linux gateway -> CAN command -> fő vezérlő -> UART -> balanszer modul
```

## Következő teendő

- UART topológia tisztázása: közös busz vagy külön UART csatornák.
- Modul címzés módja.
- CRC implementáció kiválasztása.
- Szimulátor később opcionálisan.
