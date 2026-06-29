# Codex fejlesztési útmutató - Linux gateway

## Projekt célja

A `linux-gateway` mappa egy Linuxon futó alkalmazásszerver, amely:

- SocketCAN-en kommunikál az STM32 fő vezérlővel,
- webes kezelőfelületet biztosít,
- REST API-t ad külső / helyi klienseknek,
- WebSocketen élő adatokat küld,
- később adatbázisba naplóz,
- VPN-en vagy más biztonságos csatornán keresztül távolról is elérhető.

A hardver jelenleg nincs kéznél, ezért a fejlesztés `vcan0` virtuális CAN interfésszel és CAN szimulátorral történik.

## Fontos szabályok

1. A Linux app nem biztonsági vezérlő.
2. A veszélyes kimenetek végső védelme az STM32 fő vezérlő feladata.
3. A Linux app csak parancsot küld és állapotot jelenít meg.
4. Minden veszélyes parancshoz külön backend oldali ellenőrzés és UI oldali megerősítés kell.
5. Hardver nélkül minden funkciót szimulátorral és unit teszttel kell ellenőrizni.

## Jelenlegi technológia

- Python 3
- FastAPI
- Uvicorn
- python-can
- SocketCAN / vcan0
- Pydantic modellek
- WebSocket státusz frissítés

## Jelenlegi fájlok

```text
linux-gateway/
  app/
    __init__.py
    main.py
    models.py
    can_protocol.py
    can_service.py
  requirements.txt
  RUN.md
  CODEX.md
```

## Első fejlesztési célok

### 1. CAN protokoll réteg tisztítása

Feladat:

- `can_protocol.py` maradjon hardverfüggetlen.
- Legyen külön encode/decode minden ismert frame-re.
- Legyenek unit tesztek a dekódolásra.

### 2. Gateway állapotkezelés

Feladat:

- A beérkező CAN frame-ekből egy központi `GatewayStatus` állapot épüljön.
- Legyen timeout figyelés, ha régóta nincs CAN RX.
- A status JSON legyen stabil API szerződés.

### 3. Web API

Feladat:

- `/api/status`
- `/api/command`
- `/api/cells` később
- `/api/faults` később
- `/api/config` később

### 4. WebSocket

Feladat:

- `/ws/status` élő státusz.
- Később külön cellafeszültség adatfolyam.

### 5. CAN szimulátor

Feladat:

- `tools/can-simulator/send_status.py` bővítése.
- Tudjon cellafesz csomagokat küldeni.
- Tudjon fault frame-et küldeni.
- Tudjon parancsokat logolni.

## Futtatás

Lásd:

```text
linux-gateway/RUN.md
```

## Fejlesztési elv

Kis, tesztelhető lépésekben kell haladni:

1. Protokoll definiálás.
2. Szimulátor.
3. Backend dekódolás.
4. API.
5. Web UI.
6. Tesztek.
7. Csak ezután valódi hardver.
