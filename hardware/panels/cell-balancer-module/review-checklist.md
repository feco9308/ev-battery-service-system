# Cellánkénti balanszer STM32 modul - review checklist

## Feltöltött fájlok ellenőrzése

- [ ] Kapcsolási rajz PDF megvan.
- [ ] PCB felső nézet megvan.
- [ ] PCB alsó nézet megvan.
- [ ] 3D nézet megvan.
- [ ] BOM / alkatrészlista megvan, ha elérhető.
- [ ] Gyártási fájlok megvannak, ha elérhetőek.

## Mikrokontroller és kommunikáció

- [ ] STM32 pontos típusa dokumentálva.
- [ ] UART kommunikáció pinoutja dokumentálva.
- [ ] CAN rész szerepe tisztázva, ha be van építve.
- [ ] Programozó/debug csatlakozó ellenőrizve.
- [ ] Boot / reset feltételek ellenőrizve.

## Balansz / töltő rész

- [ ] Balanszolási áram dokumentálva.
- [ ] Töltési áram dokumentálva, ha aktív töltés is van.
- [ ] Teljesítmény alkatrészek melegedése ellenőrizve.
- [ ] Hőmérsékletmérés dokumentálva.
- [ ] Reset állapotban a kimenet biztonságos állapotban van.

## Szoftverhez szükséges adatok

- [ ] Modul címzési módja.
- [ ] UART sebesség.
- [ ] Parancslista.
- [ ] Timeout idő.
- [ ] Hibaállapotok.
- [ ] Hőmérséklet határértékek.
