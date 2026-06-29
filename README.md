# EV Battery Service System

Elektromos autó akkumulátor mérő, töltő, terhelő és balanszoló rendszer többpaneles STM32 hardverrel, Linux gateway géppel és webes kezelőfelülettel.

## Cél

A projekt célja egy többpaneles akkumulátor szervizrendszer fejlesztése, amely képes:

- cellafeszültségek mérésére isoSPI alapú mérőláncon keresztül,
- terhelés kapcsolására reléken vagy félvezetős kapcsolókon keresztül,
- shunt alapú árammérésre,
- tápegység modulok RS232 vezérlésére,
- cellánkénti balanszer/töltő modulok vezérlésére,
- CAN kommunikációra Linux gateway felé,
- helyi és távoli webes kezelőfelület biztosítására.

## Fő rendszerfelépítés

```text
STM32 fő vezérlő panel
  |-- isoSPI --> cellafesz mérő / balansz panel
  |-- UART   --> cellánkénti balanszer modulok
  |-- I2C    --> shunt árammérő
  |-- RS232  --> tápegység modulok
  |-- GPIO   --> relék / terheléskapcsolás
  `-- CAN    --> Linux gateway PC

Linux gateway PC
  |-- SocketCAN
  |-- backend service
  |-- web UI
  |-- adatbázis / logolás
  `-- távoli kapcsolat saját szerveren keresztül
```

## Fontos biztonsági alapelv

A Linux app, a webapp és a távoli szerver nem biztonsági vezérlő. A veszélyes kimeneteket a fő STM32 vezérlőnek kell hiba esetén önállóan kikapcsolnia.

Kommunikációvesztés vagy mérési hiba esetén alapállapot:

- relék OFF,
- tápegység output OFF,
- balansz/töltés OFF,
- terhelés OFF,
- hibaállapot naplózása.

## Repo felépítése

```text
docs/                  Rendszertervek és protokollok
firmware/              STM32 firmware projektek
linux-gateway/         Linux gateway backend és helyi webapp
server/                Távoli szerver, MQTT/VPN/reverse proxy tervek
hardware/              Kapcsolási rajzok, pinoutok, BOM jegyzetek
tools/                 Teszt, CAN szimulátor, log parser
tests/                 Protokoll és biztonsági tesztek
```

## Első MVP

MVP-1 cél:

1. Linux gateway kommunikál CAN-en a fő vezérlővel.
2. A fő vezérlő státuszt küld.
3. A Linux app webes felületen megjeleníti az állapotot.
4. A web UI biztonságos START / STOP / EMERGENCY STOP parancsot tud küldeni.

## Fejlesztési irány

- Firmware: STM32CubeIDE / C / HAL vagy LL.
- Linux backend: Python FastAPI.
- CAN: SocketCAN + python-can.
- Frontend: első körben egyszerű web UI, később React/Vue.
- Adatbázis: SQLite első verzióban, PostgreSQL később.
- Távoli elérés: WireGuard VPN vagy MQTT TLS saját szerveren keresztül.
