# Shunt / árammérő rész

## Funkció

Ez a rész végzi a pack vagy terhelési áram mérését shunt alapú árammérő IC-vel.

## Tervezett feladatok

- Shunt feszültség mérése.
- I2C kommunikáció a fő vezérlővel.
- Áram, feszültség, teljesítmény számítás.
- Offset és gain kalibráció.
- Túláram detektálás.

## Feltöltendő fájlok

```text
schematic.pdf
pcb-top.png
pcb-bottom.png
bom.csv vagy bom.xlsx
gerber.zip
current-sensor-notes.md
calibration-notes.md
review-checklist.md
```

## Ellenőrzési fókusz

- Kelvin bekötés a shuntra.
- Shunt teljesítmény és melegedés.
- I2C pullup feszültség.
- Mérési föld és teljesítmény föld viszonya.
- Szűrés és zajvédelem.
- Kalibrációs pontok.
