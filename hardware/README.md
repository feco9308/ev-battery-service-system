# Hardware dokumentáció

A hardver dokumentációt panel funkció szerint bontjuk szét. Ez azért jó, mert minden panelhez külön lehet kezelni a kapcsolási rajzot, PCB képeket, BOM-ot, pinoutot és ellenőrzési jegyzeteket.

## Panel alapú struktúra

```text
hardware/panels/
  main-controller/          Fő vezérlő panel
  cell-measure-isospi/      Cella feszültségmérő / isoSPI panel
  cell-balancer-module/     Cellánkénti balanszer STM32 modul
  relay-load-switch/        Relé / terheléskapcsoló rész
  power-supply-interface/   RS232 tápegység interfész
  current-sense/            Shunt / árammérő rész
  connectors-harness/       Csatlakozók és kábelezés
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

## Ellenőrzési szempontok

- Relé alapállapota resetnél.
- Flyback diódák / TVS védelem.
- isoSPI transzformátor, lezárás és polaritás.
- CAN lezárás és transceiver bekötés.
- UART busz topológia.
- RS232 valódi szintillesztés vagy TTL UART.
- I2C pullup feszültségszint.
- Shunt árammérő Kelvin bekötés.
- Tápágak sorrendje és izoláció.
- Emergency stop lehetőség.

## Megjegyzés

A kapcsolási rajzokat PDF-ben érdemes feltölteni, a panelnézeteket pedig nagy felbontású PNG-ben. JPG is használható, de a PNG jobb, ha apró feliratokat kell olvasni.
