# Hardware dokumentáció

A hardver dokumentációt panel funkció szerint bontjuk szét. Jelenleg csak a ténylegesen használt négy panel szerepel a struktúrában.

## Panel alapú struktúra

```text
hardware/panels/
  cell-balancer-module/     Cellánkénti balanszer STM32 modul
  cell-measure-isospi/      Cella feszültségmérő / isoSPI panel
  current-sense/            Shunt / árammérő rész
  main-controller/          Fő vezérlő panel
```

## Fájlfeltöltési javaslat panelenként

```text
schematic.pdf              Kapcsolási rajz
pcb-top.png                PCB felső oldal
pcb-bottom.png             PCB alsó oldal
pcb-3d-top.png             3D felső nézet, ha van
pcb-3d-bottom.png          3D alsó nézet, ha van
bom.csv vagy bom.xlsx      Alkatrészlista
gerber.zip                 Gyártási fájlok
pinout.md                  Csatlakozó kiosztás
review-checklist.md        Ellenőrzési jegyzetek
```

## Általános ellenőrzési szempontok

- Reset vagy hiba esetén a kimenetek biztonságos alapállapotba kerüljenek.
- isoSPI transzformátor, lezárás és polaritás.
- CAN lezárás és transceiver bekötés.
- UART busz topológia.
- I2C pullup feszültségszint.
- Shunt árammérő Kelvin bekötés.
- Tápágak sorrendje és izoláció.
- Emergency stop lehetőség, ha van ilyen a hardveren.

## Megjegyzés

A kapcsolási rajzokat PDF-ben érdemes feltölteni, a panelnézeteket pedig nagy felbontású PNG-ben. JPG is használható, de a PNG jobb, ha apró feliratokat kell olvasni.
