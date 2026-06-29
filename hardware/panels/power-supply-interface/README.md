# Tápegység interfész / RS232 rész

## Funkció

Ez a rész biztosítja a kommunikációt és illesztést a vezérelhető tápegység modulok felé.

## Tervezett feladatok

- RS232 kommunikáció tápegységek felé.
- Feszültség beállítás.
- Áramlimit beállítás.
- Output ON/OFF parancs.
- Tápegység státusz és hibaolvasás.

## Feltöltendő fájlok

```text
schematic.pdf
pcb-top.png
pcb-bottom.png
bom.csv vagy bom.xlsx
gerber.zip
psu-protocol-notes.md
connector-pinout.md
review-checklist.md
```

## Ellenőrzési fókusz

- Valódi RS232 szintillesztés vagy TTL UART tisztázása.
- Több tápegység esetén portkiosztás.
- Földelési viszonyok.
- Izoláció szükségessége.
- Csatlakozó pinout.
- Hibás kommunikáció esetén output OFF stratégia.
