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
