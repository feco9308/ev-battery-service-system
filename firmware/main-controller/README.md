# Fő vezérlő firmware

## Szerep

A fő STM32 vezérlő a rendszer valós idejű és biztonsági központja.

Feladata:

- relék és terhelés kapcsolása,
- isoSPI cellafeszültség mérés kezelése,
- I2C shunt árammérő olvasása,
- RS232 tápegység modulok vezérlése,
- UART kommunikáció cellánkénti balanszer modulokkal,
- CAN kommunikáció Linux gateway felé,
- biztonsági állapotgép futtatása.

## Javasolt modulok

```text
App/
  state_machine/
  protection/
  can_protocol/
  relay_manager/
  current_measure/
  cell_measure_isospi/
  psu_rs232/
  balancer_uart/
  config/
  diagnostics/
```

## Biztonsági alapállapot

Minden reset vagy fault esetén:

- relé OFF,
- tápegység OFF,
- balansz OFF,
- terhelés OFF.

## Első fejlesztési cél

- CAN heartbeat fogadás.
- Fő státusz CAN frame küldés.
- Emergency stop parancs kezelése.
