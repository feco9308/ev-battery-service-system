# Mérési jegyzőkönyv / riport terv - v0.1

## Cél

A rendszer minden mérésből egységes, letölthető jegyzőkönyvet készítsen.

A jegyzőkönyv ne csak nyers adat legyen, hanem műhelyben és ügyfél felé is használható dokumentum:

- mérési összefoglaló,
- cellafeszültség grafikonok,
- áram/feszültség/idő grafikonok,
- belső ellenállás eredmények,
- hibák és figyelmeztetések,
- export PDF vagy DOCX formátumba.

## Riport formátumok

Első verzióban javasolt:

```text
PDF    végleges, ügyfélnek adható jegyzőkönyv
DOCX   szerkeszthető műhely / belső dokumentum
CSV    nyers mérési adatok exportja
JSON   teljes gépi adat export, debug és újragenerálás célra
```

## Jegyzőkönyv fő részei

```text
1. Címlap / mérés azonosító
2. Akkumulátor adatok
3. Mérési körülmények
4. Gyors teszt eredmény
5. Cellafeszültség összefoglaló
6. Belső ellenállás mérés
7. Grafikonok
8. Hibák / figyelmeztetések
9. Nyers adat melléklet vagy export hivatkozás
```

## Címlap adatok

```text
report_id
measurement_id
device_id
operator_name
customer_name opcionális
vehicle_type opcionális
battery_type opcionális
date_time
software_version
protocol_version
```

## Akkumulátor összefoglaló

```text
cell_count
pack_voltage_start_v
pack_voltage_end_v
min_cell_v
max_cell_v
delta_cell_v
current_a
state_of_test
result_summary
```

## Grafikonok

A riportban legalább ezek legyenek:

### 1. Cellafeszültség oszlopdiagram

Minden cella feszültsége egy mérési pillanatban.

```text
x tengely: cella index
 y tengely: feszültség V
```

### 2. Cella delta grafikon

A cellák eltérése az átlagtól.

```text
x tengely: cella index
 y tengely: delta mV
```

### 3. Pack feszültség / áram időben

Terheléses vagy töltéses mérésnél.

```text
x tengely: idő
 y1: pack feszültség
 y2: áram
```

### 4. Belső ellenállás cellánként

Ha a mérés támogatja.

```text
x tengely: cella index
 y tengely: belső ellenállás mOhm
```

## Riport generálási architektúra

```text
Mérés fut
  |
Adatok SQLite/JSON formában mentve
  |
Report service
  |-- grafikon PNG/SVG generálás
  |-- HTML riport sablon
  |-- PDF export
  |-- DOCX export opcionális
  `-- CSV/JSON export
```

## Javasolt technológia Linux gateway oldalon

```text
Python
FastAPI
SQLite
matplotlib vagy plotly statikus grafikon exporthoz
Jinja2 HTML sablonhoz
WeasyPrint vagy Playwright PDF exporthoz
python-docx DOCX exporthoz
```

## Riport adatmodell - első váz

```json
{
  "report_id": "RPT-2026-0001",
  "measurement_id": "MEAS-2026-0001",
  "device_id": "evsys-001",
  "created_at": "2026-06-30T12:00:00+02:00",
  "operator_name": "",
  "battery": {
    "cell_count": 96,
    "nominal_voltage_v": 355.2,
    "note": ""
  },
  "summary": {
    "pack_voltage_start_v": 360.0,
    "pack_voltage_end_v": 358.7,
    "min_cell_v": 3.812,
    "max_cell_v": 3.957,
    "delta_cell_v": 0.145,
    "result": "WARNING"
  },
  "charts": {
    "cell_voltage_chart": "cell_voltage.png",
    "cell_resistance_chart": "cell_resistance.png",
    "pack_time_chart": "pack_time.png"
  }
}
```

## Web UI funkciók

A webappban legyen:

```text
Mérés indítása
Mérés leállítása
Mérés mentése
Riport előnézet
PDF letöltés
DOCX letöltés
CSV letöltés
JSON letöltés
```

## Következő fejlesztési lépés

- `linux-gateway/app/reporting/` modul létrehozása.
- Measurement session adatmodell létrehozása.
- Grafikon generáló service.
- `/api/reports/{measurement_id}/pdf` végpont.
- `/api/reports/{measurement_id}/docx` végpont később.
