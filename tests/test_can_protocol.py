from app.can_protocol import CanId, CommandId, decode_frame, encode_command, encode_heartbeat


def test_decode_system_status() -> None:
    decoded = decode_frame(0x100, bytes([2, 0, 3, 1, 0, 4, 0x34, 0x12]))

    assert decoded is not None
    assert decoded.name == "system_status"
    assert decoded.payload == {
        "system_state": 2,
        "fault_state": 0,
        "relay_flags": 3,
        "supply_flags": 1,
        "balancer_flags": 0,
        "active_profile": 4,
        "uptime_s": 0x1234,
    }


def test_decode_pack_measurement_with_signed_current() -> None:
    decoded = decode_frame(0x120, bytes([0x10, 0x0E, 0x85, 0xFF, 0x5A, 0x00, 1, 0]))

    assert decoded is not None
    assert decoded.name == "pack_measurement"
    assert decoded.payload["pack_voltage_v"] == 360.0
    assert decoded.payload["current_a"] == -1.23
    assert decoded.payload["power_w"] == 90.0
    assert decoded.payload["measurement_valid"] is True


def test_decode_cell_voltage_packet() -> None:
    decoded = decode_frame(0x110, bytes([2, 6, 0x74, 0x0E, 0x75, 0x0E, 0x76, 0x0E]))

    assert decoded is not None
    assert decoded.name == "cell_voltages"
    assert decoded.payload == {
        "packet_index": 2,
        "first_cell_index": 6,
        "cell_voltages_mv": [3700, 3701, 3702],
    }


def test_decode_fault() -> None:
    decoded = decode_frame(0x180, bytes([1, 2, 3, 4]))

    assert decoded is not None
    assert decoded.name == "fault"
    assert decoded.payload == {
        "fault_code": 1,
        "fault_detail": 2,
        "source": 3,
        "severity": 4,
    }


def test_encode_heartbeat() -> None:
    arbitration_id, data = encode_heartbeat(sequence=0x123, enable_flags=0x02)

    assert arbitration_id == CanId.HEARTBEAT
    assert data == bytes([0x23, 0x02, 0, 0, 0, 0, 0, 0])


def test_encode_command() -> None:
    arbitration_id, data = encode_command(CommandId.EMERGENCY_STOP, sequence=7, parameter=0x12345678, flags=0xAA)

    assert arbitration_id == CanId.COMMAND
    assert data == bytes([0xF0, 7, 0x78, 0x56, 0x34, 0x12, 0xAA, 0])
