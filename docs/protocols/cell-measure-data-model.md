# Cella mérési adatmodell - v0.1

## Cél

Ez a dokumentum nem az isoSPI alacsony szintű IC parancsait írja le, hanem azt az adatmodellt, amit a fő vezérlő a cellamérő láncból előállít, majd CAN-en továbbít a Linux gateway felé.

```text
cell-measure-isospi panel -> fő vezérlő -> CAN -> Linux gateway -> Web UI
```

## Alap fogalmak

```text
cell_index: 0-tól induló szoftveres cellaszám
voltage_mV: cellafeszültség millivoltban
valid: mérés érvényes-e
open_wire_fault: open-wire gyanú
under_voltage: cella alulfesz határ alatt
over_voltage: cella túlfesz határ felett
```

## Linux API modell

```json
{
  "valid": true,
  "cell_count": 96,
  "min_cell_v": 3.812,
  "max_cell_v": 3.957,
  "delta_v": 0.145,
  "cells": [
    {
      "index": 0,
      "voltage_v": 3.812,
      "valid": true,
      "open_wire_fault": false,
      "under_voltage": false,
      "over_voltage": false
    }
  ]
}
```

## CAN cellafesz csomagolás

Sima CAN esetén egy frame 3 cellát tartalmaz.

```text
CAN ID: 0x110 + packet_index
Byte0: packet_index
Byte1: first_cell_index
Byte2-3: cell_0_mV
Byte4-5: cell_1_mV
Byte6-7: cell_2_mV
```

Példa:

```text
CAN ID: 0x110
Byte0: 0
Byte1: 0
Byte2-3: 3812
Byte4-5: 3815
Byte6-7: 3819
```

Ez a következőt jelenti:

```text
cell[0] = 3.812 V
cell[1] = 3.815 V
cell[2] = 3.819 V
```

## Mérési érvényesség

A fő vezérlő csak akkor jelölje validnak a cellaadatokat, ha:

- az isoSPI kommunikáció sikeres volt,
- minden szükséges IC válaszolt,
- nincs aktív open-wire hiba,
- a mérési adatok tartományon belül vannak.

## Határértékek

Első szoftveres modellben konfigurálható legyen:

```text
cell_undervoltage_mV
cell_overvoltage_mV
cell_delta_warning_mV
cell_delta_error_mV
```

## Web UI megjelenítés

A web UI-n szükséges értékek:

- cellaszám,
- minimum cella,
- maximum cella,
- delta,
- cellalista,
- hibás cellák kiemelése,
- mérés érvényessége.

## Következő teendő

- A Linux gatewayben `CellStatus` és `CellMeasurement` modellek létrehozása.
- CAN dekóder bővítése 0x110 cellafesz csomagokra.
- Szimulátor bővítése cellafesz frame-ekkel.
- Web UI cellatáblázat.
