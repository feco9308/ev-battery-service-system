# Linux gateway

## Szerep

A Linux gateway PC a CAN buszon kommunikál a fő vezérlő panellel, helyi webes kezelőfelületet biztosít, adatokat naplóz és kapcsolatot tart a távoli szerverrel.

## Javasolt technológia

- Python 3
- FastAPI
- python-can
- SocketCAN
- SQLite első verzióban
- WebSocket élő adatokhoz
- Docker Compose opcionálisan

## Javasolt struktúra

```text
app/
  main.py
  can_bus/
  api/
  websocket/
  database/
  services/
  config/
web/
  index.html
requirements.txt
docker-compose.yml
```

## Első fejlesztési cél

- SocketCAN interfész megnyitása.
- CAN frame-ek olvasása.
- Fő vezérlő státusz értelmezése.
- REST API `/api/status` végpont.
- WebSocket élő státusz.
