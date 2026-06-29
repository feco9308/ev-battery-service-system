# Rendszerarchitektúra

## Áttekintés

A rendszer több STM32 alapú panelből, egy Linux gateway gépből és opcionális távoli szerverből áll.

```text
[Web UI]
   |
[Linux gateway PC]
   |
   | CAN / CAN-FD
   |
[Fő vezérlő STM32]
   |-- isoSPI cellafesz mérés
   |-- UART cellánkénti balanszer modulok
   |-- I2C shunt árammérő
   |-- RS232 tápegység modulok
   `-- GPIO relé / terhelés kapcsolás
```

## Fő vezérlő panel

Feladatok:

- relék vezérlése terhelés kapcsolására,
- isoSPI cellafeszültség mérés kezelése,
- UART kommunikáció a cellánkénti balanszer modulokkal,
- I2C kommunikáció shunt árammérővel,
- RS232 kommunikáció tápegység modulokkal,
- CAN kommunikáció Linux gateway felé,
- védelmi logika és állapotgép futtatása.

## Cella feszültségmérő / balansz panel

Feladatok:

- cellafeszültségek mérése,
- open-wire teszt,
- cella hibaállapotok felismerése,
- mérési adatok biztosítása a fő vezérlő felé isoSPI-n keresztül.

## Cellánkénti balanszer STM32 modul

Feladatok:

- saját cella vagy cellacsoport balanszolása / töltése,
- helyi hőmérséklet mérés,
- saját hibák figyelése,
- UART parancsok fogadása a fő vezérlőtől,
- későbbi CAN kommunikáció előkészítése.

## Linux gateway

Feladatok:

- CAN kommunikáció a fő vezérlővel,
- mérési és töltési folyamatok magas szintű kezelése,
- webes UI kiszolgálása,
- adatnaplózás,
- távoli szerverrel való kapcsolat,
- diagnosztika és fejlesztési interfész.

## Távoli szerver

Mivel a helyszínen nincs publikus IP, a Linux gateway kifelé épít kapcsolatot egy saját publikus szerver felé.

Lehetséges megoldások:

- WireGuard VPN,
- MQTT TLS,
- reverse tunnel,
- HTTPS/WebSocket szerveres átjáró.

Első javasolt megoldás: WireGuard VPN + opcionális MQTT telemetria.
