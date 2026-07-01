import importlib.util
from pathlib import Path


SIMULATOR_PATH = Path(__file__).resolve().parents[1] / "tools" / "can-simulator" / "send_status.py"
spec = importlib.util.spec_from_file_location("send_status", SIMULATOR_PATH)
send_status = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(send_status)


def test_build_cell_voltages_uses_protocol_packet_id() -> None:
    msg = send_status.build_cell_voltages(counter=0, packet_index=2, cell_count=18)

    assert msg.arbitration_id == 0x112
    assert bytes(msg.data[:2]) == bytes([2, 6])


def test_build_fault_includes_related_index_and_uptime() -> None:
    msg = send_status.build_fault(counter=0x1234)

    assert msg.arbitration_id == 0x180
    assert bytes(msg.data) == bytes([1, 2, 1, 1, 0, 0, 0x34, 0x12])


def test_build_cell_resistances_uses_protocol_packet_id() -> None:
    msg = send_status.build_cell_resistances(counter=0, packet_index=2, cell_count=18)

    assert msg.arbitration_id == 0x192
    assert bytes(msg.data[:2]) == bytes([2, 6])
