# Cellánkénti balanszer firmware

## Szerep

A cellánkénti STM32 balanszer modul lokálisan kezeli a saját celláját vagy cellacsoportját.

## Feladatok

- UART parancsok fogadása a fő vezérlőtől.
- Balansz/töltő fokozat vezérlése.
- Helyi hőmérséklet mérés.
- Hibafigyelés.
- Watchdog.
- Biztonságos OFF állapot kommunikációvesztés esetén.
- Későbbi CAN kommunikáció előkészítése.

## Javasolt modulok

```text
App/
  uart_protocol/
  charge_control/
  protection/
  temperature/
  diagnostics/
  can_future/
```

## Első fejlesztési cél

- PING / GET_STATUS UART parancs.
- OUTPUT_OFF parancs.
- Timeout esetén automatikus OFF.
