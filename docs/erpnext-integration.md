# ERPNext integráció

## Cél

A Linux gateway adminisztrációs kapcsolatot tart az ERPNext rendszerrel:

- nyitott akkumulátor javítási munkalapok lekérése,
- munkalap kiválasztása méréshez,
- javítás előtti / utáni mérési státusz visszaírása,
- mérési payload lokális JSON mentése.

Az ERPNext integráció nem biztonsági vezérlő, és nem kapcsolhat közvetlenül hardverkimenetet.

## Környezeti változók

Példa:

```bash
ERPNEXT_BASE_URL=https://erp.example.hu
ERPNEXT_API_KEY=change_me
ERPNEXT_API_SECRET=change_me
ERPNEXT_REPAIR_JOB_DOCTYPE=Battery Repair Job
ERPNEXT_BATTERY_MEASUREMENT_DOCTYPE=Battery Measurement
```

Ha az ERPNext ugyanazon a Linux gépen fut nginx mögött, akkor az `ERPNEXT_BASE_URL` lehet helyi cím is:

```bash
ERPNEXT_BASE_URL=http://127.0.0.1
```

Ez hasznos, ha a publikus domain a gateway gépről rossz LAN IP-re oldódik.

A gateway API saját tokenje:

```bash
GATEWAY_API_TOKEN=change_me
```

A `.env` fájl nincs GitHubra feltöltve. A publikus minta: `.env.example`.

## Szükséges ERPNext mezők

A `Battery Repair Job` DocType első verzióban ezeket a mezőket használja:

```text
name
customer
license_plate
vehicle_make
vehicle_model
vehicle_year
vin
job_status
pre_measurement_done
post_measurement_done
last_measurement_status
```

A `module_count` a `Battery Repair Job` listázó query része. Ha ERPNext-ből megérkezik, a gateway ezt használja, és a webes felületen az összes modul mezőt lezárja, hogy ne lehessen véletlenül eltéríteni. A `cell_count` továbbra is jöhet CAN javaslatból vagy későbbi ERP bővítésből.

Későbbi ERPNext bővítésként javasolt egy munkalaphoz tartozó modul child table is, ha modulonként eltérő cellaszámot kell kezelni:

```text
module_no
cell_count
module_note
```

Nyitott, mérésre alkalmas státuszok:

```text
Diagnosztika alatt
Akkumulátor szétszedve
Akkumulátor újrateszt alatt
Balanszírozás alatt
```

## ERPNext API user

Az API usernek legalább ezekre van szüksége a `Battery Repair Job` DocType-on:

```text
read
write
```

Ha a kapcsolat teszt `ERPNext permission denied` vagy `No permission for Battery Repair Job` hibát ad, akkor az API user már hitelesítve van, de hiányzik ez a DocType jogosultság.

Ha a munkalap `Submitted` állapotú (`docstatus = 1`), akkor az ERPNext oldalon azt is engedni kell, hogy az API user a submitált dokumentum mérési mezőit frissítse. A gateway jelenleg ezeket írja:

```text
pre_measurement_done
post_measurement_done
last_measurement_status
```

Az `last_measurement_status` ERPNext Select mezőbe a gateway a megengedett `Mérés kész` értéket írja. Azt, hogy javítás előtti vagy javítás utáni mérés készült el, a `pre_measurement_done` és `post_measurement_done` checkbox jelöli.

Ezeknél a mezőknél ERPNext oldalon szükséges lehet az `Allow on Submit` beállítás is.

Hitelesítés:

```text
Authorization: token API_KEY:API_SECRET
```

Az API key és secret csak backend oldalon van használva, frontend JavaScriptbe nem kerül.

## Gateway endpointok

Kapcsolat ellenőrzés:

```bash
curl -H "Authorization: Bearer $GATEWAY_API_TOKEN" \
  http://127.0.0.1:8000/api/erpnext/health
```

Nyitott munkalapok:

```bash
curl -H "Authorization: Bearer $GATEWAY_API_TOKEN" \
  http://127.0.0.1:8000/api/erpnext/repair-jobs
```

Egy munkalap:

```bash
curl -H "Authorization: Bearer $GATEWAY_API_TOKEN" \
  http://127.0.0.1:8000/api/erpnext/repair-jobs/AKKU-2026-00001
```

Javítás előtti mérés kész:

```bash
curl -X PUT \
  -H "Authorization: Bearer $GATEWAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  http://127.0.0.1:8000/api/erpnext/repair-jobs/AKKU-2026-00001/measurement-status \
  -d '{
    "measurement_type": "pre",
    "measurement_id": "MEAS-2026-00001",
    "measurement_datetime": "2026-07-01T14:30:00Z",
    "status": "done"
  }'
```

Javítás utáni mérés kész:

```bash
curl -X PUT \
  -H "Authorization: Bearer $GATEWAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  http://127.0.0.1:8000/api/erpnext/repair-jobs/AKKU-2026-00001/measurement-status \
  -d '{
    "measurement_type": "post",
    "measurement_id": "MEAS-2026-00002",
    "measurement_datetime": "2026-07-01T16:30:00Z",
    "status": "done"
  }'
```

Lokális mérésmentés:

```bash
curl -X POST \
  -H "Authorization: Bearer $GATEWAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  http://127.0.0.1:8000/api/measurements/local \
  -d '{
    "repair_job": "AKKU-2026-00001",
    "measurement_type": "pre",
    "api_measurement_id": "MEAS-2026-00001",
    "measurement_datetime": "2026-07-01T14:30:00Z",
    "cells": [
      {
        "module_no": 1,
        "cell_group_no": 1,
        "voltage": 3.7,
        "internal_resistance": 2.1,
        "temperature": null,
        "status": "OK",
        "note": null
      }
    ],
    "summary": "OK"
  }'
```

Külön indítható szervizfolyamatok listája:

```bash
curl -H "Authorization: Bearer $GATEWAY_API_TOKEN" \
  http://127.0.0.1:8000/api/service-processes
```

Szervizfolyamat eredményének mentése és Battery Measurement feltöltése:

```bash
curl -X POST \
  -H "Authorization: Bearer $GATEWAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  http://127.0.0.1:8000/api/service-processes/start \
  -d '{
    "process_key": "incoming_resistance",
    "repair_job": "AKKU-2026-00001",
    "cell_count": 18,
    "load_level": 2,
    "auto_upload": true
  }'
```

Támogatott `process_key` értékek:

```text
cell_voltage_measurement
incoming_resistance
module_cell_resistance
balance_to_highest_cell
short_discharge_test
post_discharge_resistance
pack_charge
final_balancing
full_post_repair_cycle
```

A `full_post_repair_cycle` első körben auditálható vezetett lépéssort és záró összefoglaló payloadot készít. Veszélyes hardverkimenetet nem vezérel közvetlenül ERPNext-ből.

Cellafeszültség mérés mentése:

```bash
curl -X POST \
  -H "Authorization: Bearer $GATEWAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  http://127.0.0.1:8000/api/service-processes/start \
  -d '{
    "process_key": "cell_voltage_measurement",
    "repair_job": "AKKU-2026-00001",
    "measurement_stage": "Beérkezéskori mérés",
    "cell_count": 18,
    "module_count": 1,
    "voltage_warn_low": 3.0,
    "voltage_warn_high": 4.2,
    "max_delta_mv": 20,
    "auto_upload": true
  }'
```

ERPNext Battery Measurement feltöltésnél a gateway ezeket a mezőket küldi, ha van adat:

```text
name
repair_job
module_no
measurement_no
measurement_code
measurement_stage
test_type
measurement_start
measurement_end
api_measurement_id
measurement_status
duration_minutes
cell_measurements
resistance_measurements
```

A gateway fix mérési slot nevet képez a munkalap, modul, mérési típus és mérési szakasz alapján:

```text
AKKU-2026-00001-MOD01-M01-01
```

Ebben a `MOD01` az 1. modul, az első `Mxx` szám a `test_type`, a második szám a `measurement_stage` kódja. Példa: `MOD01-M01-01` = 1. modul + `Nyugalmi mérés` + `Beérkezéskori mérés`.

A `Battery Measurement.module_no` szabálya:

```text
0 = teljes pakk mérés
1..n = adott modul mérése
```

Nyugalmi cellafeszültség mérésnél modulonként mérünk, ezért a fő rekord `module_no` értéke a kiválasztott mért modul száma.

Test type kódok:

```text
01 Nyugalmi mérés
02 Ellenállásmérés
03 Merítés
04 Töltés
05 Balanszírozás
06 Terheléses mérés
09 Teljes ciklus
```

Measurement stage kódok:

```text
01 Beérkezéskori mérés
02 Javítás utáni mérés
03 Merítés utáni mérés
04 Végső mérés
05 Köztes ellenőrző mérés
```

A `measurement_status` értéke Battery Measurement esetén az ERPNext Select mezőhöz igazodik:

```text
Kész
```

A cellafeszültség mérés `test_type` értéke:

```text
Nyugalmi mérés
```

A `cell_measurements` child table javasolt mezői:

```text
module_no
cell_no
cell_voltage
cell_status
```

Az ellenállásmérés `test_type` értéke:

```text
Ellenállásmérés
```

Az ellenállásmérés `M02` kóddal kerül névképzésre, például:

```text
AKKU-2026-00001-MOD03-M02-01
```

Ellenállásmérésnél a gateway nem a `cell_measurements` táblát tölti, hanem a `resistance_measurements` child table-t. Javasolt DocType:

```text
Battery Resistance Measurement
```

Javasolt mezők:

```text
module_no
cell_no
rest_voltage
load_voltage
load_current
voltage_drop_mv
internal_resistance_mohm
resistance_status
note
```

Számítás:

```text
voltage_drop_mv = (rest_voltage - load_voltage) * 1000
internal_resistance_mohm = ((rest_voltage - load_voltage) / load_current) * 1000
```

Ha a terhelőáram hiányzik vagy `0`, illetve a terhelt feszültség nagyobb, mint a nyugalmi feszültség, akkor a sor `resistance_status` értéke `Nem mért`.

A kisütés mérés `test_type` értéke:

```text
Merítés
```

A kisütés `M03` kóddal kerül névképzésre, például:

```text
AKKU-2026-00001-MOD04-M03-02
```

Kisütésnél a gateway a `discharge_measurements` child table-t tölti. Javasolt DocType:

```text
Battery Discharge Measurement
```

Javasolt mezők:

```text
module_no
cell_no
cell_voltage
pack_voltage
discharge_current
discharge_power
discharged_energy_wh
discharge_status
note
```

A balanszírozás mérés `test_type` értéke:

```text
Balanszírozás
```

A balanszírozás `M05` kóddal kerül névképzésre, például:

```text
AKKU-2026-00001-MOD01-M05-04
```

Balanszírozásnál a gateway a `balance_measurements` child table-t tölti. Javasolt DocType:

```text
Battery Balance Measurement
```

Javasolt mezők:

```text
module_no
cell_no
start_voltage
end_voltage
target_voltage
voltage_change_mv
balance_current
balance_duration_minutes
charged_ah
charged_wh
balance_status
balance_direction
cutoff_reason
note
```

## Tipikus munkafolyamat

1. ERPNext-ben létrejön a `Battery Repair Job`.
2. Linux gateway lekéri a nyitott munkalapokat.
3. Technikus kiválasztja a munkalapot a webes felületen.
4. Mérőrendszer elvégzi a javítás előtti mérést.
5. Linux gateway lokálisan menti a mérési adatot.
6. Linux gateway visszaírja ERPNext-be: `Javítás előtti mérés kész`.
7. Javítás után ugyanez `post` measurement típussal.
8. Később ebből készül grafikon, PDF jegyzőkönyv és ERPNext File csatolmány.

## Későbbi bővítés

- `Battery Measurement` DocType létrehozása.
- Cellaadatok feltöltése child table-be.
- Grafikon generálása.
- PDF jegyzőkönyv csatolása ERPNext File-ként.
