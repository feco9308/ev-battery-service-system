# Linux gateway futtatás hardver nélkül

Ez az első fejlesztői verzió `vcan0` virtuális CAN interfésszel tesztelhető.

## Gyors indítás

A repo gyökeréből:

```bash
./start-dev.sh
```

Ez létrehozza a virtuális környezetet, felhúzza a `vcan0` interfészt, elindítja
a CAN szimulátort és a webes gatewayt.

Böngészőből:

```text
http://127.0.0.1:8000
```

Példák:

```bash
./start-dev.sh --cells 18
./start-dev.sh --cells 48 --port 8001
./start-dev.sh --no-sim
```

Leállítás:

```bash
./stop-dev.sh
```

Ha a virtuális CAN interfészt is le akarod venni:

```bash
./stop-dev.sh --remove-vcan
```

## Next ERP / külső rendszer hívás

Fejlesztés közben a riport API token nélkül is hívható. Élesebb használathoz állíts be
egy tokent indítás előtt:

```bash
export GATEWAY_API_TOKEN='valami-hosszu-titkos-token'
./start-dev.sh
```

Riport létrehozása számla vagy munkalap mellé:

```bash
curl -s -X POST http://127.0.0.1:8000/api/reports \
  -H 'Authorization: Bearer valami-hosszu-titkos-token' \
  -H 'Content-Type: application/json' \
  -d '{
    "battery_id": "BAT-001",
    "operator_name": "ERP",
    "customer_name": "Teszt ügyfél",
    "vehicle_type": "Teszt jármű",
    "measurement_type": "quick_test_internal_resistance",
    "erp_reference": "NEXT-ERP-12345",
    "invoice_number": "SZ-2026-0001",
    "work_order_id": "ML-2026-0001"
  }'
```

Exportok:

```bash
curl -H 'Authorization: Bearer valami-hosszu-titkos-token' \
  http://127.0.0.1:8000/api/reports/MEAS-.../json

curl -H 'Authorization: Bearer valami-hosszu-titkos-token' \
  -o report.csv \
  http://127.0.0.1:8000/api/reports/MEAS-.../csv
```

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
python tools/can-simulator/send_status.py --channel vcan0 --cells 48
```

A `--cells` paraméterrel állítható, hány cellát szimuláljon. Példák:

```bash
python tools/can-simulator/send_status.py --channel vcan0 --cells 18
python tools/can-simulator/send_status.py --channel vcan0 --cells 36
python tools/can-simulator/send_status.py --channel vcan0 --cells 48
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
