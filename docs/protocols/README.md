# Protokoll dokumentáció

Ez a mappa rögzíti a rendszer kommunikációs szerződéseit. A cél az, hogy a Linux backend, a web UI és a későbbi STM32 firmware ugyanarra a pontos adatmodellre épüljön.

## Protokollok

```text
can-gateway-protocol.md      Linux gateway <-> fő vezérlő CAN protokoll
linux-api-contract.md        Web UI <-> Linux backend REST/WebSocket API
balancer-uart-protocol.md    Fő vezérlő <-> cellánkénti balanszer UART protokoll
cell-measure-data-model.md   isoSPI cellamérés szoftveres adatmodell
psu-rs232-model.md           Tápegység RS232 kommunikációs modell
```

## Fejlesztési szabály

A protokollokat előbb dokumentálni kell, utána kell a kódot hozzáigazítani.

Minden protokollnál legyen:

- irány,
- adatmezők,
- skálázás,
- timeout,
- hibakezelés,
- szimulátorhoz szükséges példaüzenet.
