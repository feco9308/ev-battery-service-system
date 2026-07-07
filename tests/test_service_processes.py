from datetime import UTC, datetime

from app.models import GatewayStatus
from app.service_processes import (
    SERVICE_PROCESS_BY_KEY,
    ServiceProcessStartRequest,
    _resistance_row,
    automatic_cycle_step_labels,
    build_measurement_payload,
)


def test_build_resistance_measurement_payload_from_status() -> None:
    status = GatewayStatus(
        pack_voltage_v=360.0,
        current_a=12.3,
        power_w=4428.0,
        cell_voltages_mv=[3700, 3710, 3690],
        cell_resistances_mohm=[2.1, 2.4, 2.2],
        cell_delta_mv=20,
    )
    request = ServiceProcessStartRequest(
        process_key="incoming_resistance",
        repair_job="AKKU-2026-00001",
        cell_count=3,
        module_no=3,
        module_count=4,
    )

    payload = build_measurement_payload(
        status,
        request,
        SERVICE_PROCESS_BY_KEY["incoming_resistance"],
        now=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
    )

    assert payload.repair_job == "AKKU-2026-00001"
    assert payload.test_type == "Ellenállásmérés"
    assert payload.measurement_stage == "Beérkezéskori mérés"
    assert payload.min_cell_voltage == 3.69
    assert payload.max_cell_voltage == 3.71
    assert payload.max_cell_delta_mv == 20
    assert payload.weakest_cell == "3"
    assert payload.module_no == 3
    assert payload.cells[0].cell_voltage == 3.7
    assert payload.cells[1].internal_resistance == 2.4
    assert len(payload.resistance_measurements) == 3
    assert payload.resistance_measurements[0].module_no == 3
    assert payload.resistance_measurements[0].cell_no == 1
    assert payload.resistance_measurements[0].rest_voltage == 3.7
    assert payload.resistance_measurements[0].load_voltage == 3.674
    assert payload.resistance_measurements[0].load_current == 12.3
    assert payload.resistance_measurements[0].voltage_drop_mv == 26.0
    assert payload.resistance_measurements[0].internal_resistance_mohm == 2.114
    assert payload.resistance_measurements[0].resistance_status == "OK"


def test_build_cell_voltage_measurement_payload_with_module_and_limits() -> None:
    status = GatewayStatus(
        pack_voltage_v=66.8,
        current_a=0.0,
        power_w=0.0,
        cell_voltages_mv=[3690, 3705, 3710],
        cell_resistances_mohm=[],
        cell_delta_mv=20,
    )
    request = ServiceProcessStartRequest(
        process_key="cell_voltage_measurement",
        repair_job="AKKU-2026-00001",
        measurement_stage="Végső mérés",
        cell_count=3,
        module_no=2,
        module_count=2,
        voltage_warn_low=3.7,
        voltage_warn_high=4.2,
        max_delta_mv=20,
    )

    payload = build_measurement_payload(
        status,
        request,
        SERVICE_PROCESS_BY_KEY["cell_voltage_measurement"],
        now=datetime(2026, 7, 3, 12, 5, tzinfo=UTC),
    )

    assert payload.test_type == "Nyugalmi mérés"
    assert payload.measurement_stage == "Végső mérés"
    assert payload.measurement_status == "Kész"
    assert payload.cell_count == 3
    assert payload.module_no == 2
    assert payload.module_count == 2
    assert [cell.module_no for cell in payload.cells] == [2, 2, 2]
    assert payload.cells[0].cell_status == "Alacsony feszültség"
    assert payload.cells[1].cell_status == "OK"
    assert payload.resistance_measurements == []


def test_resistance_row_handles_zero_load_current() -> None:
    row = _resistance_row(
        module_no=1,
        cell_no=1,
        rest_voltage=3.7,
        load_voltage=3.65,
        load_current=0,
    )

    assert row.resistance_status == "Nem mért"
    assert row.internal_resistance_mohm is None
    assert row.voltage_drop_mv is None
    assert row.note == "Terhelőáram mérési hiba"


def test_resistance_row_rejects_load_voltage_above_rest_voltage() -> None:
    row = _resistance_row(
        module_no=1,
        cell_no=1,
        rest_voltage=3.7,
        load_voltage=3.71,
        load_current=10,
    )

    assert row.resistance_status == "Nem mért"
    assert row.internal_resistance_mohm is None
    assert row.voltage_drop_mv is None
    assert row.note == "Terhelt feszültség nagyobb mint a nyugalmi"


def test_build_discharge_measurement_payload_from_status() -> None:
    status = GatewayStatus(
        pack_voltage_v=66.8,
        current_a=-10.5,
        power_w=-701.4,
        cell_voltages_mv=[3200, 2990],
        cell_resistances_mohm=[],
        cell_delta_mv=210,
    )
    request = ServiceProcessStartRequest(
        process_key="short_discharge_test",
        repair_job="AKKU-2026-00001",
        cell_count=2,
        module_no=4,
        module_count=9,
        target_cell_voltage=3.0,
    )

    payload = build_measurement_payload(
        status,
        request,
        SERVICE_PROCESS_BY_KEY["short_discharge_test"],
        now=datetime(2026, 7, 3, 12, 10, tzinfo=UTC),
    )

    assert payload.test_type == "Merítés"
    assert payload.measurement_stage == "Javítás utáni mérés"
    assert payload.module_no == 4
    assert len(payload.discharge_measurements) == 1
    assert payload.discharge_measurements[0].module_no == 4
    assert payload.discharge_measurements[0].start_voltage == 66.8
    assert payload.discharge_measurements[0].end_voltage == 66.8
    assert payload.discharge_measurements[0].start_min_cell_voltage == 2.99
    assert payload.discharge_measurements[0].end_min_cell_voltage == 2.99
    assert payload.discharge_measurements[0].start_max_cell_voltage == 3.2
    assert payload.discharge_measurements[0].end_max_cell_voltage == 3.2
    assert payload.discharge_measurements[0].start_delta_mv == 210
    assert payload.discharge_measurements[0].end_delta_mv == 210
    assert payload.discharge_measurements[0].discharge_current == 10.5
    assert payload.discharge_measurements[0].discharged_wh == 0.195
    assert payload.discharge_measurements[0].min_cell_no == 2
    assert payload.discharge_measurements[0].max_cell_no == 1
    assert payload.discharge_measurements[0].cutoff_reason == "Elérte az alsó cellafeszültséget"
    assert payload.discharge_measurements[0].discharge_status == "Cél alatt"


def test_build_balance_measurement_payload_from_status() -> None:
    status = GatewayStatus(
        pack_voltage_v=66.8,
        current_a=0.0,
        power_w=0.0,
        cell_voltages_mv=[3665, 3640],
        cell_resistances_mohm=[],
        cell_delta_mv=25,
    )
    request = ServiceProcessStartRequest(
        process_key="final_balancing",
        repair_job="AKKU-2026-00001",
        cell_count=2,
        module_no=1,
        module_count=9,
        target_cell_voltage=3.7,
        charge_current_a=0.5,
    )

    payload = build_measurement_payload(
        status,
        request,
        SERVICE_PROCESS_BY_KEY["final_balancing"],
        now=datetime(2026, 7, 3, 12, 20, tzinfo=UTC),
    )

    assert payload.test_type == "Balanszírozás"
    assert payload.measurement_stage == "Végső mérés"
    assert payload.module_no == 1
    assert len(payload.balance_measurements) == 2
    assert payload.balance_measurements[0].module_no == 1
    assert payload.balance_measurements[0].cell_no == 1
    assert payload.balance_measurements[0].start_voltage == 3.665
    assert payload.balance_measurements[0].end_voltage == 3.7
    assert payload.balance_measurements[0].target_voltage == 3.7
    assert payload.balance_measurements[0].voltage_change_mv == 35.0
    assert payload.balance_measurements[0].balance_current == 0.5
    assert payload.balance_measurements[0].balance_duration_minutes == 7.0
    assert payload.balance_measurements[0].charged_ah == 0.0583
    assert payload.balance_measurements[0].charged_wh == 0.215
    assert payload.balance_measurements[0].balance_status == "OK"
    assert payload.balance_measurements[0].balance_direction == "Töltés"
    assert payload.balance_measurements[0].cutoff_reason == "Elérte a célfeszültséget"


def test_build_charge_measurement_payload_from_status() -> None:
    status = GatewayStatus(
        pack_voltage_v=66.35,
        current_a=10.0,
        power_w=663.5,
        cell_voltages_mv=[3675, 3705, 3690],
        cell_resistances_mohm=[],
        cell_delta_mv=30,
    )
    request = ServiceProcessStartRequest(
        process_key="pack_charge",
        repair_job="AKKU-2026-00001",
        cell_count=3,
        module_no=1,
        module_count=9,
        target_cell_voltage=3.7,
        charge_current_a=10.0,
    )

    payload = build_measurement_payload(
        status,
        request,
        SERVICE_PROCESS_BY_KEY["pack_charge"],
        now=datetime(2026, 7, 3, 12, 30, tzinfo=UTC),
    )

    assert payload.test_type == "Töltés"
    assert payload.measurement_stage == "Javítás utáni mérés"
    assert payload.module_no == 1
    assert len(payload.charge_measurements) == 1
    charge = payload.charge_measurements[0]
    assert charge.module_no == 1
    assert charge.start_voltage == 66.35
    assert charge.end_voltage == 66.35
    assert charge.start_min_cell_voltage == 3.675
    assert charge.end_min_cell_voltage == 3.675
    assert charge.start_max_cell_voltage == 3.705
    assert charge.end_max_cell_voltage == 3.705
    assert charge.start_delta_mv == 30.0
    assert charge.end_delta_mv == 30.0
    assert charge.charge_current == 10.0
    assert charge.charge_duration_minutes == 0.0
    assert charge.charged_wh == 0.184
    assert charge.charged_ah == 0.003
    assert charge.min_cell_no == 1
    assert charge.max_cell_no == 2
    assert charge.cutoff_reason == "Elérte a felső cellafeszültséget"
    assert charge.charge_status == "OK"
    assert charge.note == "Töltés végén a cellaeltérés elfogadható."


def test_automatic_cycle_step_order() -> None:
    assert automatic_cycle_step_labels() == [
        "Beérkezéskori ellenállásmérés",
        "Balanszírozás legnagyobb cellafeszültségre",
        "Rövid merítési teszt",
        "Merítés utáni ellenállásmérés",
        "Pakk töltés",
        "Végső automatikus balanszírozás",
    ]
