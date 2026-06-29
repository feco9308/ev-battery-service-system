# Fő vezérlő panel - review checklist

## Feltöltött fájlok ellenőrzése

- [ ] Kapcsolási rajz PDF megvan.
- [ ] PCB felső nézet megvan.
- [ ] PCB alsó nézet megvan.
- [ ] 3D nézet megvan.
- [ ] BOM / alkatrészlista megvan, ha elérhető.
- [ ] Gyártási fájlok megvannak, ha elérhetőek.

## Kommunikációk

- [ ] CAN transceiver bekötése rendben.
- [ ] CAN lezárás tisztázva.
- [ ] isoSPI csatlakozás rendben.
- [ ] UART balanszer irány rendben.
- [ ] RS232 / UART szintek tisztázva.
- [ ] I2C árammérő pullup szintje rendben.

## Biztonság

- [ ] Reset állapotban a kritikus kimenetek biztonságos állapotban vannak.
- [ ] Watchdog használható.
- [ ] Hiba esetén a fő vezérlő képes letiltani a veszélyes funkciókat.
- [ ] Tápegység és terhelés vezérlés szoftveresen letiltható.

## Szoftverhez szükséges adatok

- [ ] STM32 pontos típusa.
- [ ] CAN lábak.
- [ ] UART lábak.
- [ ] I2C lábak.
- [ ] SPI / isoSPI lábak.
- [ ] Relé / kimenet pin mapping.
- [ ] LED / diagnosztika pin mapping.
