# Fő vezérlő panel

## Funkció

A fő vezérlő panel a rendszer központi vezérlője.

## Tervezett feladatok

- Relék vezérlése terhelés kapcsolására.
- isoSPI cellafeszültség mérés kezelése.
- UART kommunikáció cellánkénti balanszer modulok felé.
- I2C kommunikáció shunt árammérővel.
- RS232 kommunikáció tápegység modulokkal.
- CAN kommunikáció Linux gateway felé.
- Biztonsági és mérési állapotgép futtatása.

## Feltöltendő fájlok

```text
schematic.pdf
pcb-top.png
pcb-bottom.png
bom.csv vagy bom.xlsx
gerber.zip
pinout.md
review-checklist.md
```

## Ellenőrzési fókusz

- STM32 tápellátás és reset.
- CAN transceiver és lezárás.
- isoSPI illesztés.
- RS232 szintillesztés.
- I2C pullup szintek.
- Relévezérlő kimenetek alapállapota.
- Watchdog / emergency stop lehetőség.
