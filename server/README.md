# Távoli szerver

## Szerep

A távoli szerver biztosítja a kapcsolatot olyan helyszínekhez, ahol nincs publikus IP cím.

## Lehetséges szolgáltatások

- WireGuard VPN szerver.
- MQTT broker TLS-sel.
- Reverse proxy.
- Távoli web dashboard.
- Felhasználó- és jogosultságkezelés.

## Első javasolt irány

1. WireGuard VPN a Linux gateway és a szerver között.
2. A helyi gateway web UI VPN-en keresztül érhető el.
3. Később MQTT telemetria és szerver oldali dashboard.

## Biztonsági szabály

A szerver nem vezérli közvetlenül a veszélyes kimeneteket. Minden parancs a fő STM32 vezérlő biztonsági logikáján keresztül érvényesül.
