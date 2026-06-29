from dataclasses import dataclass
from enum import IntEnum


class CanId(IntEnum):
    SYSTEM_STATUS = 0x100
    CELL_VOLTAGES = 0x110
    PACK_MEASUREMENT = 0x120
    FAULT = 0x180
    COMMAND = 0x200
    HEARTBEAT = 0x260


class CommandId(IntEnum):
    PING = 0x01
    GET_STATUS = 0x02
    CLEAR_FAULT = 0x03
    MEASUREMENT_START = 0x10
    MEASUREMENT_STOP = 0x11
    RELAY_ALL_OFF = 0x20
    SUPPLY_OUTPUT_OFF = 0x30
    BALANCER_ALL_OFF = 0x40
    EMERGENCY_STOP = 0xF0


@dataclass
class DecodedFrame:
    arbitration_id: int
    name: str
    payload: dict


def decode_frame(arbitration_id: int, data: bytes) -> DecodedFrame | None:
    if arbitration_id == CanId.SYSTEM_STATUS:
        return _decode_system_status(data)
    if arbitration_id == CanId.CELL_VOLTAGES:
        return _decode_cell_voltages(arbitration_id, data)
    if arbitration_id == CanId.PACK_MEASUREMENT:
        return _decode_pack_measurement(data)
    if arbitration_id == CanId.FAULT:
        return _decode_fault(data)
    return None


def _decode_system_status(data: bytes) -> DecodedFrame:
    padded = data.ljust(8, b"\x00")
    uptime_s = padded[6] | (padded[7] << 8)
    return DecodedFrame(
        arbitration_id=CanId.SYSTEM_STATUS,
        name="system_status",
        payload={
            "system_state": padded[0],
            "fault_state": padded[1],
            "relay_flags": padded[2],
            "supply_flags": padded[3],
            "balancer_flags": padded[4],
            "active_profile": padded[5],
            "uptime_s": uptime_s,
        },
    )


def _decode_pack_measurement(data: bytes) -> DecodedFrame:
    padded = data.ljust(8, b"\x00")
    voltage_raw = padded[0] | (padded[1] << 8)
    current_raw = padded[2] | (padded[3] << 8)
    if current_raw >= 0x8000:
        current_raw -= 0x10000
    power_raw = padded[4] | (padded[5] << 8)
    return DecodedFrame(
        arbitration_id=CanId.PACK_MEASUREMENT,
        name="pack_measurement",
        payload={
            "pack_voltage_v": voltage_raw / 10.0,
            "current_a": current_raw / 100.0,
            "power_w": float(power_raw),
            "measurement_valid": bool(padded[6]),
        },
    )


def _decode_cell_voltages(arbitration_id: int, data: bytes) -> DecodedFrame:
    padded = data.ljust(8, b"\x00")
    packet_index = padded[0]
    first_cell_index = padded[1]
    cell_voltages_mv = [
        padded[2] | (padded[3] << 8),
        padded[4] | (padded[5] << 8),
        padded[6] | (padded[7] << 8),
    ]
    return DecodedFrame(
        arbitration_id=arbitration_id,
        name="cell_voltages",
        payload={
            "packet_index": packet_index,
            "first_cell_index": first_cell_index,
            "cell_voltages_mv": cell_voltages_mv,
        },
    )


def _decode_fault(data: bytes) -> DecodedFrame:
    padded = data.ljust(8, b"\x00")
    return DecodedFrame(
        arbitration_id=CanId.FAULT,
        name="fault",
        payload={
            "fault_code": padded[0],
            "fault_detail": padded[1],
            "source": padded[2],
            "severity": padded[3],
        },
    )


def encode_heartbeat(sequence: int, enable_flags: int = 0) -> tuple[int, bytes]:
    data = bytes([
        sequence & 0xFF,
        enable_flags & 0xFF,
        0, 0, 0, 0, 0, 0,
    ])
    return int(CanId.HEARTBEAT), data


def encode_command(command_id: CommandId, sequence: int, parameter: int = 0, flags: int = 0) -> tuple[int, bytes]:
    parameter &= 0xFFFFFFFF
    data = bytes([
        int(command_id) & 0xFF,
        sequence & 0xFF,
        parameter & 0xFF,
        (parameter >> 8) & 0xFF,
        (parameter >> 16) & 0xFF,
        (parameter >> 24) & 0xFF,
        flags & 0xFF,
        0,
    ])
    return int(CanId.COMMAND), data
