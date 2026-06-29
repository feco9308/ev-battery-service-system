# Fejlesztési roadmap

## MVP-1: CAN kapcsolat és állapot kijelzés

Cél:

- Linux gateway kommunikál a fő vezérlővel CAN-en.
- Fő vezérlő periodikus státusz frame-et küld.
- Linux backend fogadja és értelmezi a frame-eket.
- Web UI megjeleníti az alap státuszt.
- Emergency stop parancs működik.

Feladatok:

- CAN ID kiosztás véglegesítése.
- STM32 CAN tx/rx alap driver.
- Linux SocketCAN olvasás/írás.
- FastAPI backend váz.
- WebSocket élő státusz.
- Egyszerű web dashboard.

## MVP-2: Cellafeszültség megjelenítés

Cél:

- isoSPI cellafeszültség mérés működik.
- Fő vezérlő cellaadatokat küld CAN-en.
- Linux app cellafesz táblázatot és min/max/delta értéket mutat.

Feladatok:

- Cellamérő IC driver.
- Cellafesz CAN csomagolás.
- Web UI cellanézet.
- Határérték figyelés.

## MVP-3: Árammérés és terheléskapcsolás

Cél:

- Shunt alapú árammérés működik.
- Relék biztonságosan kapcsolhatók.
- Terheléses mérési ciklus indítható.

Feladatok:

- I2C shunt driver.
- Relé manager.
- Protection manager.
- Terheléses mérési állapotgép.

## MVP-4: Tápegység RS232 vezérlés

Cél:

- Tápegység modulok feszültség- és áramlimitje állítható.
- Output ON/OFF vezérelhető.
- Tápegység hibák megjelennek.

Feladatok:

- RS232 protocol driver.
- PSU manager.
- Web UI tápegység panel.
- Biztonsági lekapcsolási tesztek.

## MVP-5: Cellánkénti balanszer modulok

Cél:

- Fő vezérlő UART-on parancsot küld a balanszer moduloknak.
- Modulok státuszt és hibát küldenek vissza.
- Balanszolás biztonságosan indítható/leállítható.

Feladatok:

- UART master protokoll.
- Cell-balancer firmware váz.
- Modul címzés.
- Timeout és hibafigyelés.

## MVP-6: Távoli elérés

Cél:

- A helyi Linux gateway távolról elérhető publikus IP nélkül.

Feladatok:

- WireGuard szerver konfiguráció.
- Gateway kliens konfiguráció.
- Opcionális MQTT TLS telemetria.
- Jogosultságkezelés.

## MVP-7: Riport és adatnaplózás

Cél:

- Mérési adatok mentése.
- CSV export.
- Hibák visszakeresése.
- Akkumulátor riport generálás.
