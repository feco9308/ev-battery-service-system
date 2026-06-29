# Panel alapú hardver dokumentáció

A hardver dokumentációt panel funkció szerint bontjuk szét. Jelenleg csak a ténylegesen használt panelmappák szerepelnek itt.

## Aktív panelmappák

```text
cell-balancer-module/     Cellánkénti balanszer STM32 modul
cell-measure-isospi/      Cella feszültségmérő / isoSPI panel
current-sense/            Shunt / árammérő rész
main-controller/          Fő vezérlő panel
```

## Fájlelnevezési javaslat panelenként

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
