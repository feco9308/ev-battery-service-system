# Gyors teszt és belső ellenállás mérés - v0.1

## Cél

A gyors teszt célja, hogy rövid idő alatt adjon képet az akkumulátor állapotáról:

- cellafeszültségek,
- cella delta,
- pack feszültség,
- árammérés,
- terhelés alatti feszültségesés,
- becsült belső ellenállás.

## Alapelv

A belső ellenállás terheléses módszerrel becsülhető:

```text
R = (U_nyugalmi - U_terhelt) / I_terhelt
```

Cellánként:

```text
R_cell = (U_cell_nyugalmi - U_cell_terhelt) / I_terhelt
```

Mértékegység:

```text
V / A = Ohm
mOhm = Ohm * 1000
```

## Fontos megjegyzés

Ez nem laboratóriumi EIS mérés, hanem gyors, terheléses belső ellenállás becslés. Szervizdiagnosztikára jó, de a mérési feltételeket mindig rögzíteni kell:

- terhelőáram,
- terhelési idő,
- cellahőmérséklet,
- kezdeti töltöttség,
- mérési időpont.

## Gyors teszt állapotgép

```text
IDLE
  |
PRE_CHECK
  |
REST_MEASUREMENT
  |
LOAD_ENABLE
  |
LOAD_STABILIZE
  |
LOAD_MEASUREMENT
  |
LOAD_DISABLE
  |
RECOVERY_MEASUREMENT
  |
CALCULATE_RESULTS
  |
SAVE_MEASUREMENT
  |
REPORT_READY
```

## 1. PRE_CHECK

Ellenőrzések:

- nincs aktív fault,
- cellamérés működik,
- árammérés működik,
- relé / terhelés kapcsolás engedélyezett,
- pack feszültség tartományban,
- cellák tartományban,
- hőmérséklet tartományban, ha mérhető.

## 2. REST_MEASUREMENT

Terhelés nélkül mérjük:

```text
pack_voltage_rest_v
current_rest_a
cell_voltage_rest_v[index]
temperature_c[index]
```

Javasolt mintavétel:

```text
1-3 másodperc
átlagolás több mintából
```

## 3. LOAD_ENABLE

A fő vezérlő bekapcsolja a terhelést.

Biztonsági szabály:

- ha az áram túl nagy,
- ha cellafesz túl alacsony,
- ha kommunikáció megszakad,
- ha relé hiba gyanú van,

akkor azonnal `LOAD_DISABLE` és `FAULT` vagy `ABORTED` állapot.

## 4. LOAD_STABILIZE

Rövid várakozás, hogy az áram és feszültség beálljon.

Első javaslat:

```text
100-500 ms
```

## 5. LOAD_MEASUREMENT

Terhelés alatt mérjük:

```text
pack_voltage_load_v
current_load_a
cell_voltage_load_v[index]
```

Javasolt mintavétel:

```text
0.5-2 másodperc
átlagolás több mintából
```

## 6. LOAD_DISABLE

Terhelés kikapcsolása.

## 7. RECOVERY_MEASUREMENT

Terhelés levétele után opcionális visszaállási mérés:

```text
pack_voltage_recovery_v
cell_voltage_recovery_v[index]
```

Ez segít látni, hogy mennyire esik/visszaáll a cellafeszültség.

## 8. CALCULATE_RESULTS

Pack belső ellenállás:

```text
R_pack_mOhm = ((pack_voltage_rest_v - pack_voltage_load_v) / current_load_a) * 1000
```

Cellánkénti becsült ellenállás:

```text
R_cell_mOhm[index] = ((cell_voltage_rest_v[index] - cell_voltage_load_v[index]) / current_load_a) * 1000
```

Ha az áram túl kicsi, az eredmény nem érvényes.

Első javaslat:

```text
minimum current_load_a: 1.0 A vagy konfigurálható
```

## Eredmény minősítés

Első egyszerű minősítés:

```text
OK       minden cella tartományban, delta és R_cell elfogadható
WARNING  cella delta vagy R_cell eltérés magas
FAIL     cella alulfesz, túl nagy R_cell, mérési hiba vagy fault
ABORTED  mérés megszakadt
```

## Jegyzőkönyvbe kerülő adatok

```text
test_type = quick_test_internal_resistance
start_time
end_time
load_current_a
load_duration_ms
pack_voltage_rest_v
pack_voltage_load_v
pack_voltage_recovery_v
pack_resistance_mOhm
min_cell_voltage_rest_v
max_cell_voltage_rest_v
min_cell_voltage_load_v
max_cell_voltage_load_v
max_cell_delta_v
max_cell_resistance_mOhm
result
warnings
faults
```

## Grafikonok

A gyors teszt riportban legyen:

```text
1. cellafeszültségek nyugalmi állapotban
2. cellafeszültségek terhelés alatt
3. cellánkénti feszültségesés mV-ban
4. cellánkénti becsült belső ellenállás mOhm-ban
5. pack feszültség és áram időben, ha van idősoros adat
```

## CAN / Linux kapcsolat

A Linux gateway parancsa:

```text
MEASUREMENT_START parameter = QUICK_TEST_INTERNAL_RESISTANCE
```

A fő vezérlő végzi a valós idejű kapcsolást és védelmet. A Linux gateway gyűjti és megjeleníti az adatokat.

## Következő teendő

- Measurement session modell létrehozása Linux oldalon.
- CAN státusz kiegészítése mérési állapottal.
- Cellafesz frame-ek mentése sessionbe.
- Riport generátor elkészítése.
- Web UI gyors teszt indító oldal.
