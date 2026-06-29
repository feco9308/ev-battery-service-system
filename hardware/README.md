# Hardware dokumentáció

Ide kerülnek a kapcsolási rajzok, pinoutok, BOM jegyzetek és hardveres ellenőrzési listák.

## Panelek

- Fő vezérlő panel
- Cella feszültségmérő / isoSPI panel
- Cellánkénti balanszer STM32 panel
- Tápegység interfész / RS232 rész
- Relé / terheléskapcsoló rész

## Ellenőrzési szempontok

- Relé alapállapota resetnél.
- Flyback diódák / TVS védelem.
- isoSPI transzformátor, lezárás és polaritás.
- CAN lezárás és transceiver bekötés.
- UART busz topológia.
- RS232 valódi szintillesztés vagy TTL UART.
- I2C pullup feszültségszint.
- Shunt árammérő Kelvin bekötés.
- Tápágak sorrendje és izoláció.
- Emergency stop lehetőség.
