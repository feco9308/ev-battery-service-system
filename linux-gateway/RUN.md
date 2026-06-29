# Linux gateway futtatás hardver nélkül

Ez az első fejlesztői verzió `vcan0` virtuális CAN interfésszel tesztelhető.

## 1. Virtuális környezet

```bash
cd linux-gateway
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. vcan0 létrehozása Linuxon

```bash
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set up vcan0
```

Ellenőrzés:

```bash
ip link show vcan0
```

## 3. Gateway app indítása

```bash
cd linux-gateway
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Böngészőből:

```text
http://localhost:8000
```

Ha a `vcan0` még nincs létrehozva, az app akkor is elindul, de a `/api/status`
válaszban a `can_error` mező jelzi a CAN kapcsolódási hibát. Parancs küldése
ilyenkor `503` választ ad.

## 4. CAN szimulátor indítása másik terminálban

```bash
source linux-gateway/.venv/bin/activate
python tools/can-simulator/send_status.py --channel vcan0 --cells 120
```

A `--cells` paraméterrel állítható, hány cellát szimuláljon. Példák:

```bash
python tools/can-simulator/send_status.py --channel vcan0 --cells 18
python tools/can-simulator/send_status.py --channel vcan0 --cells 54
python tools/can-simulator/send_status.py --channel vcan0 --cells 120
```

## 5. API teszt

```bash
curl http://localhost:8000/api/status
```

Emergency stop parancs:

```bash
curl -X POST http://localhost:8000/api/command \
  -H 'Content-Type: application/json' \
  -d '{"command":"emergency_stop"}'
```

## Megjegyzés

Ez a verzió még fejlesztői váz. A biztonsági logika véglegesítése előtt nem használható valódi akkumulátoron.
