#!/usr/bin/env python3
import argparse
import itertools
import time

import can


def build_system_status(counter: int) -> can.Message:
    system_state = 2  # IDLE
    fault_state = 0
    relay_flags = counter & 0x03
    supply_flags = 0
    balancer_flags = 0
    active_profile = 0
    uptime_s = counter & 0xFFFF
    data = bytes([
        system_state,
        fault_state,
        relay_flags,
        supply_flags,
        balancer_flags,
        active_profile,
        uptime_s & 0xFF,
        (uptime_s >> 8) & 0xFF,
    ])
    return can.Message(arbitration_id=0x100, data=data, is_extended_id=False)


def build_pack_measurement(counter: int) -> can.Message:
    voltage_dv = 3600 + (counter % 20)  # 360.0 V körül
    current_ca = 1234  # 12.34 A
    power_w = 4442
    data = bytes([
        voltage_dv & 0xFF,
        (voltage_dv >> 8) & 0xFF,
        current_ca & 0xFF,
        (current_ca >> 8) & 0xFF,
        power_w & 0xFF,
        (power_w >> 8) & 0xFF,
        1,
        0,
    ])
    return can.Message(arbitration_id=0x120, data=data, is_extended_id=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="EV battery gateway CAN simulator")
    parser.add_argument("--channel", default="vcan0")
    parser.add_argument("--period", type=float, default=0.5)
    args = parser.parse_args()

    bus = can.Bus(interface="socketcan", channel=args.channel)
    for counter in itertools.count():
        bus.send(build_system_status(counter))
        bus.send(build_pack_measurement(counter))
        time.sleep(args.period)


if __name__ == "__main__":
    main()
