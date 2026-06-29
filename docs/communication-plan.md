# Kommunikációs terv

## Kiindulás

A hardver gyártás és beszerzés alatt van, ezért a Linux alapú szoftvert és a protokollokat hardver nélkül kell elkezdeni.

Első fejlesztési cél: a Linux gateway, a CAN protokoll, a web API és a szimulációs környezet elkészítése úgy, hogy később a valódi STM32 panelek rákapcsolhatók legyenek.

## Kommunikációs szintek

```text
Web UI / távoli kliens
        |
        | HTTP REST + WebSocket
        |
Linux gateway app
        |
        | SocketCAN
        |
Fő STM32 vezérlő panel
        |-- isoSPI cellafesz mérés
        |-- UART cellánkénti balanszer modulok
        |-- RS232 tápegység modulok
        |-- I2C shunt árammérő
        `-- GPIO relék / terhelés
```

## Linux gateway mint app szerver

A Linux gateway futtatja:

- a backend alkalmazást,
- a helyi webes kezelőfelületet,
- a CAN kommunikációt,
- az adatnaplózást,
- a távoli elérés kapcsolatát.

A web UI alapból helyileg fut a Linux gatewayen, például:

```text
http://gateway.local:8000
```

Távolról VPN-en vagy más kimenő kapcsolaton keresztül érhető el.

## Távoli publikálás

Mivel a helyszínen nincs publikus IP, a gateway kifelé épít kapcsolatot.

Első javasolt megoldás:

```text
Linux gateway -> WireGuard VPN -> saját publikus szerver
```

Alternatívák:

- MQTT TLS telemetriára és parancsokra,
- reverse tunnel,
- Cloudflare Tunnel,
- saját HTTPS reverse proxy.

## Panelok közötti kommunikáció

### Linux gateway <-> fő vezérlő

Javasolt: CAN vagy CAN-FD.

Feladatok:

- rendszer státusz,
- cellaadatok,
- áram/feszültség/teljesítmény,
- reléállapot,
- tápegység állapot,
- hibák,
- mérési parancsok,
- emergency stop.

### Fő vezérlő <-> cellafesz mérő

Javasolt: isoSPI.

Feladatok:

- cellafeszültség olvasás,
- open-wire teszt,
- hőmérséklet vagy GPIO olvasás, ha támogatott,
- mérési hibák kezelése.

### Fő vezérlő <-> cellánkénti balanszer modulok

Jelenlegi terv: UART.

Feladatok:

- modul címzés,
- PING,
- GET_STATUS,
- OUTPUT_OFF,
- balansz/töltés parancs,
- timeout kezelés,
- hibaállapot visszajelzés.

Későbbi lehetőség: CAN alapú balanszer modulok.

### Fő vezérlő <-> tápegység modulok

Javasolt: RS232.

Feladatok:

- feszültség beállítás,
- áramlimit beállítás,
- output ON/OFF,
- státusz olvasás,
- hibaállapot olvasás.

## Hardver nélküli fejlesztés

Hardver nélkül az első fejlesztési kör:

- vcan0 virtuális CAN interfész,
- CAN szimulátor,
- FastAPI backend,
- WebSocket élő adat,
- egyszerű webes dashboard,
- protokoll dekóder/enkóder tesztek.

## Döntések, amelyeket még pontosítani kell

- Sima CAN vagy CAN-FD lesz?
- Milyen bitrate?
- Hány cella van maximum?
- Hány balanszer modul lesz?
- A balanszer UART busz közös busz vagy külön portok?
- A tápegységek RS232-n külön porton vagy buszosítva vannak?
- Milyen shunt mérő IC lesz?
- Milyen isoSPI cellamérő IC lesz?
