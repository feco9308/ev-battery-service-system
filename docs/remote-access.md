# Távoli elérés publikus IP nélkül

## Kiindulási helyzet

A rendszer olyan helyen működik, ahol nincs publikus IP cím. Emiatt a helyi Linux gateway nem érhető el közvetlenül az internetről.

A megoldás: a Linux gateway kifelé épít kapcsolatot egy saját publikus szerverhez.

## Javasolt architektúra

```text
[Battery service system]
        |
[Linux gateway PC]
        |
        | kimenő kapcsolat
        |
[Publikus saját szerver]
        |
[Felhasználó böngésző / VPN kliens]
```

## Opció 1: WireGuard VPN

A Linux gateway WireGuard kliensként csatlakozik a publikus szerverhez.

Előnyök:

- biztonságos,
- stabil,
- saját kontroll alatt van,
- nem kell port forward,
- a helyi web UI VPN-en keresztül elérhető.

Javasolt első távoli hozzáférési megoldás.

## Opció 2: MQTT TLS

A Linux gateway MQTT kliensként csatlakozik a szerveren futó brokerhez.

Javasolt topic struktúra:

```text
evsys/device/001/status
evsys/device/001/cells
evsys/device/001/current
evsys/device/001/fault
evsys/device/001/cmd
evsys/device/001/result
```

Előnyök:

- jó telemetriára,
- NAT mögött jól működik,
- több gép később egyszerűen kezelhető,
- webes dashboard könnyen építhető rá.

## Opció 3: Reverse tunnel

Példák:

- SSH reverse tunnel,
- Cloudflare Tunnel,
- saját HTTPS reverse proxy.

Ez gyorsan működő webes eléréshez jó, de ipari vezérlésnél óvatosan kell használni.

## Javasolt első megoldás

```text
Helyi kezelés: Linux gateway FastAPI + web UI
Távoli kezelés: WireGuard VPN
Telemetria: opcionális MQTT TLS
```

## Biztonsági szabály

Távoli kapcsolaton keresztül érkező parancsok nem kerülhetik meg a fő STM32 vezérlő biztonsági állapotgépét.

A távoli szerver csak kommunikációs csatorna, nem biztonsági vezérlő.
