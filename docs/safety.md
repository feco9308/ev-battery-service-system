# Biztonsági alapelvek

## Alapelv

A rendszerben a veszélyes kimenetek vezérlése nem függhet kizárólag a Linux alkalmazástól, web UI-tól vagy távoli szervertől.

A fő STM32 vezérlőnek önállóan kell tudnia biztonságos állapotba vinni a rendszert.

## Biztonságos alapállapot

Reset, firmware hiba, kommunikációs hiba vagy tápindulás esetén:

- relék OFF,
- terhelés OFF,
- tápegység output OFF,
- balanszer/töltő kimenetek OFF,
- fault állapot aktív,
- felhasználói jóváhagyás kell az újraindításhoz.

## Kötelező watchdogok

### Fő STM32 watchdog

Hardveres vagy független watchdog szükséges. Watchdog reset után minden kimenet maradjon OFF.

### CAN heartbeat watchdog

Ha a Linux gateway nem küld heartbeat-et időben, a fő vezérlő tiltson minden veszélyes funkciót.

### isoSPI watchdog

Ha a cellafeszültség mérés hibás vagy timeoutol:

- töltés tiltás,
- terhelés tiltás,
- balansz tiltás.

### I2C shunt watchdog

Ha az árammérő IC nem válaszol vagy irreális adatot ad:

- terhelés OFF,
- tápegység OFF,
- fault állapot.

### RS232 tápegység watchdog

Ha a tápegység nem válaszol vagy hibaállapotban van:

- output OFF parancs,
- relék OFF,
- fault állapot.

### UART balanszer watchdog

Ha egy balanszer modul nem válaszol:

- adott modul tiltás,
- globális balansz tiltás opcionálisan,
- fault vagy warning állapot.

## Határértékek

Minden határértéket konfigurálhatóvá, de védetten kell tenni.

Példák:

- max cellafeszültség,
- min cellafeszültség,
- max pack feszültség,
- max töltőáram,
- max terhelőáram,
- max hőmérséklet,
- max mérési idő,
- max balanszolási idő.

## Hiba esetén végrehajtandó sorrend

```text
1. Veszélyes kimenetek OFF
2. Tápegység output OFF parancs
3. Relék OFF
4. Balanszer modulok OFF
5. Fault kód rögzítése
6. CAN fault frame küldése
7. Web UI értesítése Linux gatewayen keresztül
8. Várakozás manuális resetre vagy clear fault parancsra
```

## Web UI korlátozás

Távolról indítható veszélyes műveleteknél külön megerősítés szükséges:

- töltés indítása,
- terhelés indítása,
- tápegység output ON,
- balanszolás indítása,
- relék kézi kapcsolása.

Emergency stop mindig legyen közvetlenül elérhető.
