# Linux gateway fejlesztési terv

## Miért ezzel kezdünk?

A hardver még nincs kéznél, de a PC-s / Linuxos szoftver nagy része hardver nélkül is fejleszthető:

- CAN protokoll,
- szimulátor,
- backend API,
- webes kezelőfelület,
- adatmodellek,
- parancslogika,
- távoli elérés előkészítése.

## Fejlesztési környezet

Javasolt rendszer:

- Linux desktop vagy laptop,
- Python 3.11+,
- vcan0 virtuális CAN,
- VS Code vagy Cursor / Codex alapú fejlesztés,
- GitHub repo,
- opcionálisan Docker később.

## Fejlesztési fázisok

### Fázis 1: vcan0 és alap gateway

Cél:

- A FastAPI app elindul.
- A vcan0 interfész működik.
- A CAN szimulátor státusz frame-et küld.
- A web UI élőben mutatja az adatokat.

Eredmény:

```text
Böngészőben látható: connected, system_state, current, voltage, uptime.
```

### Fázis 2: CAN protokoll bővítése

Cél:

- Cellafeszültség frame-ek.
- Fault frame-ek.
- Relé / tápegység / balanszer státusz frame-ek.
- Parancs visszaigazolás.

Eredmény:

```text
A gateway képes minden fontos CAN üzenetet dekódolni és megjeleníteni.
```

### Fázis 3: Webes dashboard

Cél:

- Áttekintő státusz oldal.
- Cellafeszültség táblázat.
- Hibák listája.
- Emergency stop gomb.
- Start/stop parancsok.

Eredmény:

```text
Egyszerű, de használható műhely dashboard.
```

### Fázis 4: Adatnaplózás

Cél:

- SQLite adatbázis.
- Mérés session fogalom.
- Feszültség/áram/cellák mentése.
- CSV export.

Eredmény:

```text
Mérések visszakereshetők és exportálhatók.
```

### Fázis 5: Távoli elérés

Cél:

- Linux gateway helyi webappként működik.
- Saját szerveren keresztül VPN-nel elérhető.
- Később MQTT telemetria opcionális.

Első javasolt megoldás:

```text
WireGuard VPN
```

## Codexnek adható első konkrét feladat

```text
A linux-gateway mappában fejleszd tovább a FastAPI + SocketCAN gateway alkalmazást.

Cél:
- legyen stabil CAN protokoll dekóder,
- legyen unit teszt a can_protocol.py-hoz,
- a CAN szimulátor tudjon system status, pack measurement és fault frame-et küldeni,
- a web UI jelenítse meg az utolsó státuszt,
- legyen emergency_stop parancs küldés.

Ne nyúlj a firmware és hardware mappákhoz.
A hardver még nem elérhető, ezért minden teszt vcan0-val fusson.
```
