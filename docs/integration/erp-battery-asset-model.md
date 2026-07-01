# ERP és akkumulátor hierarchia adatmodell - v0.1

## Probléma

A mérőrendszer fizikailag egyszerre csak egy mérési konfigurációt / packot vagy modulcsoportot tud ellenőrizni, de egy autó akkumulátora nem feltétlenül egyetlen 18 cellás egység.

Ezért nem fix cellaszámban kell gondolkodni, hanem hierarchikus adatmodellben:

```text
Autó / munkalap
  |
  |-- Akkumulátor pack
        |
        |-- Modul 1
        |     |-- Cella / cellacsoport 1
        |     |-- Cella / cellacsoport 2
        |
        |-- Modul 2
        |     |-- Cella / cellacsoport ...
        |
        |-- Modul N
```

## Cél

Az ERP-ből lekérhető legyen:

- munkalap,
- autó adatai,
- akkumulátor típusa,
- pack azonosító,
- elvárt cella/modul struktúra,
- korábbi mérések,
- ügyfél / javítási adatok.

A mérés után visszatölthető legyen:

- mérési jegyzőkönyv,
- cella/modul eredmények,
- hibák,
- grafikonok / PDF riport hivatkozás,
- javítási státusz.

## Fő entitások

## Work Order / Munkalap

ERP oldali fő azonosító.

```json
{
  "work_order_id": "AKKU-2026-00001",
  "customer_name": "",
  "vehicle_vin": "",
  "vehicle_model": "",
  "battery_asset_id": "BAT-00001",
  "status": "in_progress"
}
```

## Battery Asset / Akkumulátor egység

Az akkumulátor pack vagy vizsgált akkumulátor azonosítója.

```json
{
  "battery_asset_id": "BAT-00001",
  "battery_type": "Kia/Hyundai pack példa",
  "nominal_voltage_v": 360.0,
  "nominal_capacity_ah": 0,
  "module_count": 12,
  "total_series_cells": 96,
  "chemistry": "Li-ion NMC"
}
```

## Battery Layout / Pack struktúra

Ez írja le, hogyan épül fel az adott akku.

```json
{
  "layout_id": "LAYOUT-HYUNDAI-001",
  "module_count": 12,
  "modules": [
    {
      "module_index": 0,
      "name": "Module 1",
      "series_cell_count": 8,
      "parallel_count": 1,
      "global_cell_start": 0,
      "global_cell_end": 7
    },
    {
      "module_index": 1,
      "name": "Module 2",
      "series_cell_count": 8,
      "parallel_count": 1,
      "global_cell_start": 8,
      "global_cell_end": 15
    }
  ]
}
```

## Measurement Session / Mérési session

Egy konkrét mérés egy konkrét munkalaphoz és akkuhoz.

```json
{
  "measurement_id": "MEAS-2026-00001",
  "work_order_id": "AKKU-2026-00001",
  "battery_asset_id": "BAT-00001",
  "layout_id": "LAYOUT-HYUNDAI-001",
  "test_type": "quick_test_internal_resistance",
  "started_at": "2026-06-30T12:00:00+02:00",
  "finished_at": null,
  "status": "running"
}
```

## Cell Result / Cella eredmény

A szoftver mindig globális cella indexet használ.

```json
{
  "measurement_id": "MEAS-2026-00001",
  "global_cell_index": 15,
  "module_index": 1,
  "local_cell_index": 7,
  "voltage_rest_v": 3.812,
  "voltage_load_v": 3.792,
  "voltage_drop_mv": 20,
  "resistance_mohm": 2.0,
  "result": "OK"
}
```

## Miért kell globális cella index?

A mérőrendszer és a riport szempontjából ez a legtisztább:

```text
cell[0]
cell[1]
cell[2]
...
cell[95]
```

A modulhoz tartozást a layout mondja meg:

```text
cell[15] = module[1], local_cell[7]
```

Így a grafikonokon lehet teljes pack nézet, és modulonkénti bontás is.

## Mérési módok

## 1. Teljes pack mérés

A rendszer egyben látja az összes soros cellát.

```text
measurement_scope = full_pack
cell_count = total_series_cells
```

## 2. Modul mérés

Csak egy modult mérünk.

```text
measurement_scope = module
module_index = 3
cell_count = module.series_cell_count
```

A mért lokális cellákat az ERP/layout alapján vissza kell térképezni globális cellaszámra.

## 3. Részleges mérés

Csak bizonyos cellatartományt mérünk.

```text
measurement_scope = cell_range
global_cell_start = 24
global_cell_end = 41
```

## ERP integráció irányai

## ERP -> Linux gateway

Mérés indításakor a gateway lekéri:

```text
munkalap adatok
akku azonosító
akku layout
elvárt cellaszám
korábbi mérési adatok opcionálisan
```

## Linux gateway -> ERP

Mérés végén visszatölti:

```text
measurement_id
result summary
cell/module eredmények
faultok
PDF riport link vagy fájl
CSV/JSON export link vagy fájl
javítási javaslat / státusz
```

## Web UI logika

Mérés indításakor a kezelő kiválasztja vagy beolvassa:

```text
munkalap azonosító
akku / pack azonosító
mérési mód: full_pack / module / cell_range
ha module: module_index
ha cell_range: start/end cell
```

Ezután a Linux gateway tudja, hogy a bejövő cellaadatokat hová kell tenni a pack struktúrában.

## Riport megjelenítés

A jegyzőkönyvben legyen két nézet:

### Teljes pack nézet

```text
cell[0] ... cell[N]
```

Grafikon:

- minden cella feszültsége,
- minden cella belső ellenállása,
- gyenge cellák kiemelése.

### Modul nézet

```text
Module 1
  cell 0..7
Module 2
  cell 8..15
...
```

Grafikon:

- modulonként min/max/delta,
- modulon belüli gyenge cellák,
- modul összehasonlítás.

## Első MVP javaslat

Első verzióban ne akarjunk minden autótípust tökéletesen előre lemodellezni.

Elég legyen ez:

```text
work_order_id
vehicle_vin opcionális
battery_asset_id
layout_name
module_count
default_cells_per_module
total_series_cells
measurement_scope
```

Ha eltérő modulméretek vannak, akkor később jön a részletes module list.

## Következő fejlesztési feladatok

- Linux gateway adatmodell bővítése WorkOrder, BatteryAsset, BatteryLayout, MeasurementSession modellekkel.
- ERP API kliens váz létrehozása.
- Web UI mérésindító képernyő: munkalap kiválasztás + mérési scope.
- Riport generátor bővítése teljes pack és modul nézettel.
- ERP visszatöltési payload megtervezése.
