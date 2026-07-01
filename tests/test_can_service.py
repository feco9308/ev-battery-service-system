from app.can_service import CanService


async def noop_status_callback(status):
    return None


def test_apply_cell_voltages_updates_summary() -> None:
    service = CanService()

    service._apply_decoded_frame(
        "cell_voltages",
        {
            "packet_index": 1,
            "first_cell_index": 3,
            "cell_voltages_mv": [3698, 3701, 3704],
        },
    )
    service._apply_decoded_frame(
        "cell_voltages",
        {
            "packet_index": 0,
            "first_cell_index": 0,
            "cell_voltages_mv": [3700, 3702, 3699],
        },
    )

    assert service.status.connected is True
    assert service.status.cell_voltages_mv == [3700, 3702, 3699, 3698, 3701, 3704]
    assert service.status.min_cell_mv == 3698
    assert service.status.max_cell_mv == 3704
    assert service.status.cell_delta_mv == 6


def test_apply_fault_maps_protocol_names_to_status_fields() -> None:
    service = CanService()

    service._apply_decoded_frame(
        "fault",
        {
            "fault_code": 10,
            "fault_detail": 20,
            "source": 2,
            "severity": 3,
            "related_index": 4,
            "uptime_s": 123,
        },
    )

    assert service.status.fault_code == 10
    assert service.status.fault_detail == 20
    assert service.status.fault_source == 2
    assert service.status.fault_severity == 3
    assert service.status.fault_related_index == 4
    assert service.status.uptime_s == 123


def test_apply_cell_resistances_updates_summary() -> None:
    service = CanService()
    service.status.resistance_measurement_running = True

    service._apply_decoded_frame(
        "cell_resistances",
        {
            "packet_index": 1,
            "first_cell_index": 3,
            "cell_resistances_mohm": [2.1, 2.4, 2.2],
        },
    )
    service._apply_decoded_frame(
        "cell_resistances",
        {
            "packet_index": 0,
            "first_cell_index": 0,
            "cell_resistances_mohm": [1.8, 1.9, 2.0],
        },
    )

    assert service.status.cell_resistances_mohm == [1.8, 1.9, 2.0, 2.1, 2.4, 2.2]
    assert service.status.max_cell_resistance_mohm == 2.4


def test_apply_cell_resistances_ignores_frames_when_measurement_stopped() -> None:
    service = CanService()

    service._apply_decoded_frame(
        "cell_resistances",
        {
            "packet_index": 0,
            "first_cell_index": 0,
            "cell_resistances_mohm": [1.8, 1.9, 2.0],
        },
    )

    assert service.status.cell_resistances_mohm == []
    assert service.status.max_cell_resistance_mohm is None


def test_apply_command_ack_updates_last_command_result() -> None:
    service = CanService()

    service._apply_decoded_frame(
        "command_ack",
        {
            "command_id": 0x10,
            "command_seq": 7,
            "result_code": 3,
            "reject_reason": 2,
        },
    )

    assert service.status.last_command_id == 0x10
    assert service.status.last_command_seq == 7
    assert service.status.last_command_result == 3
    assert service.status.last_command_reject_reason == 2


def test_add_status_callback() -> None:
    service = CanService()

    service.add_status_callback(noop_status_callback)

    assert service._callbacks == [noop_status_callback]
