# Cella feszültségmérő / isoSPI panel

## Funkció

Ez a panel méri az akkumulátor cellafeszültségeit isoSPI kommunikáción keresztül.

## Tervezett feladatok

- Összes cellafeszültség mérése.
- isoSPI kommunikáció a fő vezérlő felé.
- Open-wire teszt lehetősége.
- Hőmérséklet vagy GPIO mérés, ha a mérő IC támogatja.

## Feltöltendő fájlok

```text
schematic.pdf
pcb-top.png
pcb-bottom.png
bom.csv vagy bom.xlsx
gerber.zip
pinout.md
cell-channel-map.md
review-checklist.md
```

## Ellenőrzési fókusz

- isoSPI transzformátor / csatolás.
- Cellabemenetek szűrése és védelme.
- Mérő IC tápellátása.
- Cellasorrend és csatlakozó kiosztás.
- Open-wire mérés lehetősége.
- Nagyfeszültségű részek távolságai.
