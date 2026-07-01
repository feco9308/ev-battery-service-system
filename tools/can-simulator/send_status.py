#!/usr/bin/env python3
import argparse
import itertools
import math
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


def build_cell_voltages(counter: int, packet_index: int, cell_count: int) -> can.Message:
    first_cell_index = packet_index * 3
    base_mv = 3700 + (counter % 8)
    values: list[int] = []
    for offset in range(3):
        cell_index = first_cell_index + offset
        if cell_index >= cell_count:
            values.append(0)
        else:
            module_offset = (cell_index // 18) * 3
            ripple = (cell_index % 18) - 9
            values.append(base_mv + module_offset + ripple)
    data = bytes([
        packet_index & 0xFF,
        first_cell_index & 0xFF,
        values[0] & 0xFF,
        (values[0] >> 8) & 0xFF,
        values[1] & 0xFF,
        (values[1] >> 8) & 0xFF,
        values[2] & 0xFF,
        (values[2] >> 8) & 0xFF,
    ])
    return can.Message(arbitration_id=0x110 + packet_index, data=data, is_extended_id=False)


def build_fault(counter: int) -> can.Message:
    uptime_s = counter & 0xFFFF
    data = bytes([1, 2, 1, 1, 0, 0, uptime_s & 0xFF, (uptime_s >> 8) & 0xFF])
    return can.Message(arbitration_id=0x180, data=data, is_extended_id=False)


def build_cell_resistances(counter: int, packet_index: int, cell_count: int) -> can.Message:
    first_cell_index = packet_index * 3
    values: list[int] = []
    for offset in range(3):
        cell_index = first_cell_index + offset
        if cell_index >= cell_count:
            values.append(0)
        else:
            base_centi_mohm = 180 + (counter % 5)
            module_offset = (cell_index // 18) * 8
            ripple = (cell_index % 18) * 3
            values.append(base_centi_mohm + module_offset + ripple)
    data = bytes([
        packet_index & 0xFF,
        first_cell_index & 0xFF,
        values[0] & 0xFF,
        (values[0] >> 8) & 0xFF,
        values[1] & 0xFF,
        (values[1] >> 8) & 0xFF,
        values[2] & 0xFF,
        (values[2] >> 8) & 0xFF,
    ])
    return can.Message(arbitration_id=0x190 + packet_index, data=data, is_extended_id=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="EV battery gateway CAN simulator")
    parser.add_argument("--channel", default="vcan0")
    parser.add_argument("--period", type=float, default=0.5)
    parser.add_argument("--cells", type=int, default=48, help="Number of simulated cells to send. Current CAN ID map supports up to 48.")
    parser.add_argument("--cell-packets", type=int, default=None, help="Deprecated. Use --cells instead.")
    parser.add_argument("--fault-every", type=int, default=0, help="Send a fault frame every N cycles. 0 disables faults.")
    args = parser.parse_args()
    cell_count = max(1, min(args.cells, 48))
    cell_packets = args.cell_packets if args.cell_packets is not None else math.ceil(cell_count / 3)

    bus = can.Bus(interface="socketcan", channel=args.channel)
    try:
        for counter in itertools.count():
            bus.send(build_system_status(counter))
            bus.send(build_pack_measurement(counter))
            for packet_index in range(cell_packets):
                bus.send(build_cell_voltages(counter, packet_index, cell_count))
                bus.send(build_cell_resistances(counter, packet_index, cell_count))
            if args.fault_every > 0 and counter > 0 and counter % args.fault_every == 0:
                bus.send(build_fault(counter))
            time.sleep(args.period)
    finally:
        bus.shutdown()


if __name__ == "__main__":
    main()
