# Panelek és funkciók

## 1. Fő vezérlő panel

### Hardveres funkciók

- Relék vezérlése terhelés kapcsolására.
- isoSPI cellafeszültség mérés.
- UART kommunikáció cellánkénti balanszer modulok felé.
- I2C átalakító / shunt alapú árammérés.
- RS232 kommunikáció tápegység modulok felé.
- CAN kommunikáció Linux gateway felé.

### Firmware feladatok

- Fő állapotgép.
- Mérési ciklusok vezérlése.
- Töltési ciklusok vezérlése.
- Balanszer modulok parancsolása.
- Védelmi logika.
- Hibakódok és státusz CAN-en.

## 2. Cella feszültségmérő / balansz panel

### Hardveres funkciók

- Összes cellafeszültség mérése.
- isoSPI kommunikáció.
- Open-wire ellenőrzés lehetősége.
- Hőmérséklet mérés, ha a hardver támogatja.

### Firmware / driver oldal

Ha a panelen nincs külön mikrokontroller, akkor a fő vezérlő kezeli az isoSPI cellamérő IC-ket.

Ha van külön mikrokontroller, akkor külön firmware szükséges:

- cellafesz lekérdezés,
- hibák helyi kezelése,
- CAN vagy UART státusz küldés.

## 3. Cellánkénti balanszer modul

### Hardveres funkciók

- STM32 mikrokontroller.
- Cellánkénti balansz / töltő fokozat.
- UART kommunikáció a fő vezérlő felé.
- CAN kommunikáció későbbi funkcióhoz.
- Hőmérséklet mérés.

### Firmware feladatok

- Parancs fogadás UART-on.
- Helyi töltő / balansz kimenet vezérlése.
- Hőmérséklet és hibafigyelés.
- Watchdog.
- Biztonságos OFF állapot kommunikációvesztés esetén.

## 4. Linux gateway

### Hardveres kapcsolat

- CAN adapter, például USB-CAN vagy beépített CAN interfész.
- Hálózati kapcsolat saját szerver felé.

### Szoftveres funkciók

- SocketCAN kommunikáció.
- Webes kezelőfelület.
- REST API.
- WebSocket élő adatokhoz.
- SQLite vagy PostgreSQL adatbázis.
- Távoli szerver kapcsolat.
