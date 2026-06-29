# Panel alapú hardver dokumentáció

A hardver dokumentációt panel funkció szerint bontjuk szét. Így minden panelhez külön helyen lehet tárolni:

- kapcsolási rajz PDF-et,
- PCB nézeteket PNG/JPG formában,
- gyártási fájlokat,
- BOM-ot,
- pinoutot,
- kommunikációs leírást,
- ellenőrzési jegyzeteket.

## Javasolt panel mappák

```text
main-controller/          Fő vezérlő panel
cell-measure-isospi/      Cella feszültségmérő / isoSPI panel
cell-balancer-module/     Cellánkénti balanszer STM32 modul
relay-load-switch/        Relé / terheléskapcsoló rész
power-supply-interface/   RS232 tápegység interfész
current-sense/            Shunt / árammérő rész
connectors-harness/       Csatlakozók, kábelezés, harness
```

## Fájlelnevezési javaslat

```text
schematic.pdf
pcb-top.png
pcb-bottom.png
pcb-3d-top.png
pcb-3d-bottom.png
bom.xlsx vagy bom.csv
gerber.zip
pick-and-place.csv
pinout.md
notes.md
review-checklist.md
```

Ha egy panelből több verzió van, a fájlnevekbe kerüljön verzió:

```text
main-controller-v1.0-schematic.pdf
main-controller-v1.0-pcb-top.png
main-controller-v1.0-gerber.zip
```
