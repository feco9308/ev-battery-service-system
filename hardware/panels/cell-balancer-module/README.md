# Cellánkénti balanszer STM32 modul

## Funkció

Ez a panel cellánként vagy cellacsoportonként végzi a balanszolást / helyi töltésvezérlést STM32 mikrokontrollerrel.

## Tervezett feladatok

- UART kommunikáció a fő vezérlővel.
- CAN kommunikáció későbbi bővítéshez.
- Balansz/töltő fokozat vezérlése.
- Hőmérséklet mérés.
- Helyi hibakezelés.
- Kommunikációvesztés esetén automatikus OFF.

## Feltöltendő fájlok

```text
schematic.pdf
pcb-top.png
pcb-bottom.png
bom.csv vagy bom.xlsx
gerber.zip
pinout.md
uart-protocol-notes.md
review-checklist.md
```

## Ellenőrzési fókusz

- STM32 tápellátás.
- Balansz/töltő teljesítményfokozat.
- Hőmérséklet mérés.
- UART szintillesztés és csatlakozás.
- CAN transceiver és lezárás, ha be van építve.
- Safe default: minden kimenet OFF resetnél.
