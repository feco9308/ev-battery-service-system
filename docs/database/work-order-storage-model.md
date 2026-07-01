# Munkaszám alapú adattárolási modell - v0.1

## Cél

A Linux gateway minden munkaszámhoz / munkalaphoz külön mérési adatcsomagot hozzon létre, de közben legyen egy központi adatbázis is, amiben gyorsan lehet keresni, listázni és riportot generálni.

## Javasolt megoldás

Ne csak egyetlen fájlban tároljunk mindent, hanem két rétegben:

```text
1. Központi SQLite adatbázis
2. Munkaszámonkénti adatcsomag mappa
```

## Miért két réteg?

## SQLite adatbázis

Előny:

- gyors keresés,
- munkalap lista,
- mérési sessionök listázása,
- web UI gyors működés,
- riport generálás,
- később ERP szinkron státuszok kezelése.

## Munkaszámonkénti adatcsomag

Előny:

- könnyen archiválható,
- könnyen menthető,
- ügyfelenként / munkalaponként külön kezelhető,
- tartalmazhat PDF, CSV, JSON, grafikon PNG fájlokat,
- ERP-be visszatöltéshez egyben kezelhető.

## Javasolt mappastruktúra

```text
linux-gateway/data/
  gateway.sqlite

  work-orders/
    AKKU-2026-00001/
      work-order.json
      battery-layout.json
      measurements/
        MEAS-2026-00001/
          measurement.json
          raw-can-log.csv
          samples.csv
          cells.csv
          results.json
          charts/
            cell-voltage-rest.png
            cell-voltage-load.png
            cell-resistance.png
            pack-voltage-current.png
          reports/
            report.pdf
            report.docx
            report.json
            report.csv
```

## Fő szabály

A SQLite az index és működési adatbázis.

A munkaszám mappa az archiválható mérési csomag.

Ha a rendszer később másik gépre kerül, a munkaszám mappa önmagában is értelmezhető legyen.

## SQLite táblák első verzióban

## work_orders

```text
id
work_order_id
customer_name
vehicle_vin
vehicle_model
battery_asset_id
status
created_at
updated_at
erp_sync_status
```

## battery_assets

```text
id
battery_asset_id
work_order_id
battery_type
nominal_voltage_v
nominal_capacity_ah
module_count
total_series_cells
layout_id
```

## battery_layouts

```text
id
layout_id
name
module_count
total_series_cells
layout_json
```

## measurements

```text
id
measurement_id
work_order_id
battery_asset_id
test_type
measurement_scope
module_index
global_cell_start
global_cell_end
started_at
finished_at
status
result
report_pdf_path
report_docx_path
report_json_path
```

## cell_results

```text
id
measurement_id
global_cell_index
module_index
local_cell_index
voltage_rest_v
voltage_load_v
voltage_recovery_v
voltage_drop_mv
resistance_mohm
result
warning_flags
```

## pack_samples

```text
id
measurement_id
timestamp_ms
pack_voltage_v
current_a
power_w
state
```

## faults

```text
id
measurement_id
timestamp_ms
fault_code
source
severity
message
```

## ERP kapcsolat

## ERP-ből lekérve

Munkalap indításkor:

```text
work_order_id
vehicle_vin
vehicle_model
customer_name
battery_asset_id
battery_layout
module_count
total_series_cells
```

Ezek bekerülnek:

```text
SQLite adatbázisba
work-order.json fájlba
battery-layout.json fájlba
```

## ERP-be visszatöltve

Mérés végén:

```text
measurement_id
result
summary
cell_results
module_results
faults
report.pdf
report.json vagy report link
```

## Offline működés

A rendszer akkor is működjön, ha az ERP épp nem érhető el.

Ilyenkor:

```text
erp_sync_status = pending
mérés helyben mentve
később újrapróbálható a feltöltés
```

## Adatcsomag export

Egy munkaszám mappa ZIP-be csomagolható:

```text
AKKU-2026-00001.zip
```

Ez tartalmazza:

- munkalap JSON,
- akkumulátor layout,
- összes mérés,
- nyers adatok,
- grafikonok,
- riportok.

## Linux gateway API javaslat

```text
GET  /api/work-orders
POST /api/work-orders/import-from-erp
GET  /api/work-orders/{work_order_id}
GET  /api/work-orders/{work_order_id}/measurements
POST /api/work-orders/{work_order_id}/measurements
GET  /api/measurements/{measurement_id}
GET  /api/measurements/{measurement_id}/report/pdf
POST /api/measurements/{measurement_id}/sync-to-erp
```

## Javasolt első implementáció

Első körben:

```text
SQLite adatbázis
work-orders mappák
measurement.json
cells.csv
samples.csv
report.pdf később
```

Nem kell azonnal mindent adatbázisba tenni. A fontos összesítő adatok menjenek SQLite-ba, a nagy idősoros adatok mehetnek CSV/JSON fájlba.

## Miért jobb ez, mint csak egy adatbázis?

Mert a mérési jegyzőkönyv és a nyers adatok egyben mozgathatók.

## Miért jobb ez, mint csak fájlok?

Mert a web UI és a keresés sokkal gyorsabb adatbázisból.

## Végső javaslat

```text
SQLite = gyors lista, keresés, állapot, ERP sync
Munkaszám mappa = teljes mérési archívum
PDF/DOCX/CSV/JSON = export és ügyfél/javítási dokumentáció
```
