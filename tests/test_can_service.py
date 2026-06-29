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
        },
    )

    assert service.status.fault_code == 10
    assert service.status.fault_detail == 20
    assert service.status.fault_source == 2
    assert service.status.fault_severity == 3


def test_add_status_callback() -> None:
    service = CanService()

    service.add_status_callback(noop_status_callback)

    assert service._callbacks == [noop_status_callback]
