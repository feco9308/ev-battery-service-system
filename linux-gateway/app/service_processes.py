from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from .integrations.models import BatteryBalanceMeasurement, BatteryCellMeasurement, BatteryChargeMeasurement, BatteryDischargeMeasurement, BatteryMeasurementPayload, BatteryResistanceMeasurement
from .models import GatewayStatus


@dataclass(frozen=True)
class ServiceProcessDefinition:
    key: str
    label: str
    tab: str
    test_type: str
    measurement_stage: str
    description: str


SERVICE_PROCESSES = [
    ServiceProcessDefinition(
        key="cell_voltage_measurement",
        label="Cella feszültség mérés",
        tab="cells",
        test_type="Nyugalmi mérés",
        measurement_stage="Beérkezéskori mérés",
        description="Cellánkénti feszültségmérés min/max/delta kiértékeléssel.",
    ),
    ServiceProcessDefinition(
        key="incoming_resistance",
        label="Beérkezéskori ellenállásmérés",
        tab="resistance",
        test_type="Ellenállásmérés",
        measurement_stage="Beérkezéskori mérés",
        description="Terhelt cella/cellacsoport ellenállásmérés a hibás cellák azonosításához.",
    ),
    ServiceProcessDefinition(
        key="module_cell_resistance",
        label="Modul / cella ellenállásmérés",
        tab="resistance",
        test_type="Ellenállásmérés",
        measurement_stage="Javítás utáni mérés",
        description="Célzott modul vagy cellacsoport belső ellenállás mérése.",
    ),
    ServiceProcessDefinition(
        key="balance_to_highest_cell",
        label="Balanszírozás legnagyobb cellafeszültségre",
        tab="balancing",
        test_type="Balanszírozás",
        measurement_stage="Javítás utáni mérés",
        description="Cellaszintek közelítése a legmagasabb cellafeszültséghez.",
    ),
    ServiceProcessDefinition(
        key="short_discharge_test",
        label="Rövid merítési teszt",
        tab="discharge",
        test_type="Merítés",
        measurement_stage="Javítás utáni mérés",
        description="Rövid terheléses teszt a leggyengébb cella és legrosszabb pillanat keresésére.",
    ),
    ServiceProcessDefinition(
        key="post_discharge_resistance",
        label="Merítés utáni ellenállásmérés",
        tab="resistance",
        test_type="Ellenállásmérés",
        measurement_stage="Merítés utáni mérés",
        description="Merítés után ismételt ellenállásmérés összehasonlításhoz.",
    ),
    ServiceProcessDefinition(
        key="pack_charge",
        label="Pakk töltés",
        tab="charge",
        test_type="Töltés",
        measurement_stage="Javítás utáni mérés",
        description="Pakk töltési összefoglaló végső min/max/delta cellaadatokkal.",
    ),
    ServiceProcessDefinition(
        key="final_balancing",
        label="Végső automatikus balanszírozás",
        tab="balancing",
        test_type="Balanszírozás",
        measurement_stage="Végső mérés",
        description="Záró balanszírozás és cellánkénti eredmény rögzítése.",
    ),
    ServiceProcessDefinition(
        key="full_post_repair_cycle",
        label="Teljes javítás utáni tesztciklus",
        tab="cycle",
        test_type="Teljes ciklus",
        measurement_stage="Végső mérés",
        description="Teljes javítás utáni tesztsor vezetett előkészítése és záró összesítése.",
    ),
]

SERVICE_PROCESS_BY_KEY = {process.key: process for process in SERVICE_PROCESSES}
AUTOMATIC_PROCESS_STEPS = [
    "incoming_resistance",
    "balance_to_highest_cell",
    "short_discharge_test",
    "post_discharge_resistance",
    "pack_charge",
    "final_balancing",
]


class ServiceProcessStartRequest(BaseModel):
    process_key: str
    repair_job: str | None = None
    measurement_name: str | None = None
    overwrite_existing: bool = False
    measurement_stage: str | None = None
    load_level: int = 2
    cell_count: int | None = None
    module_no: int | None = None
    module_count: int | None = None
    voltage_warn_low: float | None = None
    voltage_warn_high: float | None = None
    max_delta_mv: float | None = None
    target_cell_voltage: float | None = None
    target_pack_voltage: float | None = None
    discharge_current_a: float | None = None
    charge_current_a: float | None = None
    balance_delta_mv: float | None = None
    auto_upload: bool = True


class ServiceProcessResult(BaseModel):
    ok: bool = True
    process_key: str
    label: str
    api_measurement_id: str
    repair_job: str | None = None
    local_path: str | None = None
    erpnext_measurement: dict[str, Any] | None = None
    erpnext_error: dict[str, Any] | None = None
    next_steps: list[str] = Field(default_factory=list)


def get_process_definitions() -> list[ServiceProcessDefinition]:
    return SERVICE_PROCESSES


def build_measurement_payload(
    status: GatewayStatus,
    request: ServiceProcessStartRequest,
    process: ServiceProcessDefinition,
    *,
    now: datetime | None = None,
) -> BatteryMeasurementPayload:
    timestamp = now or datetime.now(UTC)
    measurement_id = f"MEAS-{timestamp.strftime('%Y%m%d%H%M%S')}-{process.key.upper()}"
    cell_voltages_mv = _trim_cells(status.cell_voltages_mv, request.cell_count)
    cell_resistances_mohm = _trim_cells(status.cell_resistances_mohm, request.cell_count)
    cells = _build_cells(
        cell_voltages_mv,
        cell_resistances_mohm,
        module_no=request.module_no,
        module_count=request.module_count,
        voltage_warn_low=request.voltage_warn_low,
        voltage_warn_high=request.voltage_warn_high,
    )
    resistance_measurements = _build_resistance_measurements(
        cell_voltages_mv,
        cell_resistances_mohm,
        load_current=status.current_a,
        module_no=request.module_no,
        module_count=request.module_count,
    ) if process.test_type == "Ellenállásmérés" else []
    discharge_measurements = _build_discharge_measurements(
        cell_voltages_mv,
        status=status,
        discharged_energy_wh=_estimate_discharge_wh(status.power_w, process.key),
        module_no=request.module_no,
        module_count=request.module_count,
        target_cell_voltage=request.target_cell_voltage,
    ) if process.test_type == "Merítés" else []
    balance_measurements = _build_balance_measurements(
        cell_voltages_mv,
        module_no=request.module_no,
        module_count=request.module_count,
        target_voltage=request.target_cell_voltage,
        balance_current=request.charge_current_a,
    ) if process.test_type == "Balanszírozás" else []
    charge_measurements = _build_charge_measurements(
        cell_voltages_mv,
        status=status,
        charged_energy_wh=_estimate_energy_wh(status.power_w, process.key),
        module_no=request.module_no,
        target_cell_voltage=request.target_cell_voltage,
        charge_current=request.charge_current_a,
    ) if process.test_type == "Töltés" else []
    min_mv = _min_value(cell_voltages_mv)
    max_mv = _max_value(cell_voltages_mv)
    weakest_index = _index_of(cell_voltages_mv, min_mv)
    charged_energy_wh = _estimate_energy_wh(status.power_w, process.key)
    discharged_energy_wh = _estimate_discharge_wh(status.power_w, process.key)
    return BatteryMeasurementPayload(
        repair_job=request.repair_job or "",
        measurement_stage=request.measurement_stage or process.measurement_stage,
        test_type=process.test_type,
        api_measurement_id=measurement_id,
        measurement_start=timestamp,
        measurement_name=request.measurement_name,
        measurement_end=timestamp,
        measurement_status="Kész",
        cell_count=len(cells) if cells else request.cell_count,
        module_count=request.module_count,
        min_cell_voltage=_mv_to_v(min_mv),
        max_cell_voltage=_mv_to_v(max_mv),
        max_cell_delta_mv=(max_mv - min_mv) if min_mv is not None and max_mv is not None else None,
        weakest_module="1" if weakest_index is not None else None,
        weakest_cell=str(weakest_index + 1) if weakest_index is not None else None,
        worst_moment_time=timestamp if process.key == "short_discharge_test" else None,
        worst_moment_current=status.current_a if process.key == "short_discharge_test" else None,
        worst_moment_energy_wh=discharged_energy_wh if process.key == "short_discharge_test" else None,
        discharged_energy_wh=discharged_energy_wh,
        charged_energy_wh=charged_energy_wh,
        module_no=request.module_no,
        cells=cells,
        balance_measurements=balance_measurements,
        charge_measurements=charge_measurements,
        resistance_measurements=resistance_measurements,
        discharge_measurements=discharge_measurements,
        summary=_summary_text(process, status, len(cells)),
        recommendation=_recommendation_text(status),
        process_key=process.key,
        parameters=request.model_dump(exclude_none=True),
    )


def automatic_cycle_step_labels() -> list[str]:
    return [SERVICE_PROCESS_BY_KEY[key].label for key in AUTOMATIC_PROCESS_STEPS]


def _build_cells(
    cell_voltages_mv: list[float | int | None],
    cell_resistances_mohm: list[float | int | None],
    *,
    module_no: int | None = None,
    module_count: int | None = None,
    voltage_warn_low: float | None = None,
    voltage_warn_high: float | None = None,
) -> list[BatteryCellMeasurement]:
    cell_count = max(len(cell_voltages_mv), len(cell_resistances_mohm))
    cells = []
    for index in range(cell_count):
        voltage_mv = _list_get(cell_voltages_mv, index)
        resistance = _list_get(cell_resistances_mohm, index)
        voltage_v = _mv_to_v(voltage_mv)
        cells.append(
            BatteryCellMeasurement(
                module_no=module_no if module_no is not None and module_no > 0 else _module_no(index, cell_count, module_count),
                cell_no=index + 1,
                cell_voltage=voltage_v,
                voltage=voltage_v,
                internal_resistance=float(resistance) if resistance is not None else None,
                cell_status=_cell_status(voltage_v, voltage_warn_low, voltage_warn_high),
            )
        )
    return cells


def _module_no(cell_index: int, cell_count: int, module_count: int | None) -> int:
    if module_count is None or module_count <= 1 or cell_count <= 0:
        return 1
    cells_per_module = max(1, -(-cell_count // module_count))
    return min(module_count, (cell_index // cells_per_module) + 1)


def _cell_status(voltage_v: float | None, warn_low: float | None, warn_high: float | None) -> str:
    if voltage_v is None:
        return "Nincs adat"
    if warn_low is not None and voltage_v < warn_low:
        return "Alacsony feszültség"
    if warn_high is not None and voltage_v > warn_high:
        return "Magas feszültség"
    return "OK"


def _build_resistance_measurements(
    cell_voltages_mv: list[float | int | None],
    cell_resistances_mohm: list[float | int | None],
    *,
    load_current: float | None,
    module_no: int | None = None,
    module_count: int | None = None,
) -> list[BatteryResistanceMeasurement]:
    cell_count = max(len(cell_voltages_mv), len(cell_resistances_mohm))
    rows = []
    for index in range(cell_count):
        rest_voltage = _mv_to_v(_list_get(cell_voltages_mv, index))
        measured_resistance = _list_get(cell_resistances_mohm, index)
        load_voltage = _derive_load_voltage(rest_voltage, measured_resistance, load_current)
        row = _resistance_row(
            module_no=module_no if module_no is not None and module_no > 0 else _module_no(index, cell_count, module_count),
            cell_no=index + 1,
            rest_voltage=rest_voltage,
            load_voltage=load_voltage,
            load_current=abs(float(load_current)) if load_current is not None else None,
        )
        rows.append(row)
    return rows


def _derive_load_voltage(rest_voltage: float | None, resistance_mohm: float | int | None, load_current: float | None) -> float | None:
    if rest_voltage is None or resistance_mohm is None or load_current is None or abs(load_current) <= 0:
        return None
    return round(rest_voltage - ((float(resistance_mohm) / 1000.0) * abs(float(load_current))), 3)


def _resistance_row(
    *,
    module_no: int,
    cell_no: int,
    rest_voltage: float | None,
    load_voltage: float | None,
    load_current: float | None,
) -> BatteryResistanceMeasurement:
    note = ""
    if rest_voltage is None:
        note = "Nyugalmi feszültség hiányzik"
        return BatteryResistanceMeasurement(module_no=module_no, cell_no=cell_no, resistance_status="Nem mért", note=note)
    if load_voltage is None:
        note = "Terhelt feszültség hiányzik"
        return BatteryResistanceMeasurement(
            module_no=module_no,
            cell_no=cell_no,
            rest_voltage=round(rest_voltage, 3),
            load_current=round(load_current, 3) if load_current is not None else None,
            resistance_status="Nem mért",
            note=note,
        )
    if load_current is None or load_current <= 0:
        note = "Terhelőáram mérési hiba"
        return BatteryResistanceMeasurement(
            module_no=module_no,
            cell_no=cell_no,
            rest_voltage=round(rest_voltage, 3),
            load_voltage=round(load_voltage, 3),
            resistance_status="Nem mért",
            note=note,
        )
    if load_voltage > rest_voltage:
        note = "Terhelt feszültség nagyobb mint a nyugalmi"
        return BatteryResistanceMeasurement(
            module_no=module_no,
            cell_no=cell_no,
            rest_voltage=round(rest_voltage, 3),
            load_voltage=round(load_voltage, 3),
            load_current=round(load_current, 3),
            resistance_status="Nem mért",
            note=note,
        )
    voltage_drop_mv = round((rest_voltage - load_voltage) * 1000.0, 1)
    internal_resistance_mohm = round(((rest_voltage - load_voltage) / load_current) * 1000.0, 3)
    return BatteryResistanceMeasurement(
        module_no=module_no,
        cell_no=cell_no,
        rest_voltage=round(rest_voltage, 3),
        load_voltage=round(load_voltage, 3),
        load_current=round(load_current, 3),
        voltage_drop_mv=voltage_drop_mv,
        internal_resistance_mohm=internal_resistance_mohm,
        resistance_status=_resistance_status(internal_resistance_mohm),
        note=note,
    )


def _resistance_status(internal_resistance_mohm: float | None) -> str:
    if internal_resistance_mohm is None:
        return "Nem mért"
    if internal_resistance_mohm <= 3.0:
        return "OK"
    if internal_resistance_mohm <= 5.0:
        return "Figyelendő"
    return "Magas ellenállás"


def _build_discharge_measurements(
    cell_voltages_mv: list[float | int | None],
    *,
    status: GatewayStatus,
    discharged_energy_wh: float | None,
    module_no: int | None = None,
    module_count: int | None = None,
    target_cell_voltage: float | None = None,
) -> list[BatteryDischargeMeasurement]:
    min_mv = _min_value(cell_voltages_mv)
    max_mv = _max_value(cell_voltages_mv)
    min_cell_index = _index_of(cell_voltages_mv, min_mv)
    max_cell_index = _index_of(cell_voltages_mv, max_mv)
    pack_voltage = round(float(status.pack_voltage_v), 3) if status.pack_voltage_v is not None else None
    discharged_ah = round(discharged_energy_wh / pack_voltage, 3) if discharged_energy_wh is not None and pack_voltage else None
    min_cell_voltage = _mv_to_v(min_mv)
    max_cell_voltage = _mv_to_v(max_mv)
    delta_mv = (max_mv - min_mv) if min_mv is not None and max_mv is not None else None
    selected_module_no = module_no if module_no is not None and module_no > 0 else 0
    return [
        BatteryDischargeMeasurement(
            module_no=selected_module_no,
            start_voltage=pack_voltage,
            end_voltage=pack_voltage,
            start_min_cell_voltage=min_cell_voltage,
            end_min_cell_voltage=min_cell_voltage,
            start_max_cell_voltage=max_cell_voltage,
            end_max_cell_voltage=max_cell_voltage,
            start_delta_mv=float(delta_mv) if delta_mv is not None else None,
            end_delta_mv=float(delta_mv) if delta_mv is not None else None,
            discharge_current=round(abs(float(status.current_a)), 3) if status.current_a is not None else None,
            discharge_duration_minutes=0.0,
            discharged_ah=discharged_ah,
            discharged_wh=discharged_energy_wh,
            min_cell_no=(min_cell_index + 1) if min_cell_index is not None else None,
            max_cell_no=(max_cell_index + 1) if max_cell_index is not None else None,
            cutoff_reason=_discharge_cutoff_reason(min_cell_voltage, pack_voltage, target_cell_voltage),
            discharge_status=_discharge_status(min_cell_voltage, target_cell_voltage),
            note=None,
        )
    ]


def _discharge_status(cell_voltage: float | None, target_cell_voltage: float | None) -> str:
    if cell_voltage is None:
        return "Nem mért"
    if target_cell_voltage is not None and cell_voltage <= target_cell_voltage:
        return "Cél alatt"
    return "OK"


def _discharge_cutoff_reason(cell_voltage: float | None, pack_voltage: float | None, target_cell_voltage: float | None) -> str:
    if cell_voltage is None or pack_voltage is None:
        return "Nincs teljes mérési adat"
    if target_cell_voltage is not None and cell_voltage <= target_cell_voltage:
        return "Elérte az alsó cellafeszültséget"
    return "Felhasználó megszakította"


def _build_charge_measurements(
    cell_voltages_mv: list[float | int | None],
    *,
    status: GatewayStatus,
    charged_energy_wh: float | None,
    module_no: int | None = None,
    target_cell_voltage: float | None = None,
    charge_current: float | None = None,
) -> list[BatteryChargeMeasurement]:
    min_mv = _min_value(cell_voltages_mv)
    max_mv = _max_value(cell_voltages_mv)
    min_cell_index = _index_of(cell_voltages_mv, min_mv)
    max_cell_index = _index_of(cell_voltages_mv, max_mv)
    pack_voltage = round(float(status.pack_voltage_v), 3) if status.pack_voltage_v is not None else None
    measured_current = round(abs(float(status.current_a)), 3) if status.current_a is not None else None
    requested_current = round(abs(float(charge_current)), 3) if charge_current is not None and charge_current > 0 else None
    current = measured_current if measured_current not in (None, 0) else requested_current
    charged_ah = round(charged_energy_wh / pack_voltage, 3) if charged_energy_wh is not None and pack_voltage else None
    min_cell_voltage = _mv_to_v(min_mv)
    max_cell_voltage = _mv_to_v(max_mv)
    delta_mv = (max_mv - min_mv) if min_mv is not None and max_mv is not None else None
    selected_module_no = module_no if module_no is not None and module_no > 0 else 0
    return [
        BatteryChargeMeasurement(
            module_no=selected_module_no,
            start_voltage=pack_voltage,
            end_voltage=pack_voltage,
            start_min_cell_voltage=min_cell_voltage,
            end_min_cell_voltage=min_cell_voltage,
            start_max_cell_voltage=max_cell_voltage,
            end_max_cell_voltage=max_cell_voltage,
            start_delta_mv=float(delta_mv) if delta_mv is not None else None,
            end_delta_mv=float(delta_mv) if delta_mv is not None else None,
            charge_current=current,
            charge_duration_minutes=0.0,
            charged_ah=charged_ah,
            charged_wh=charged_energy_wh,
            min_cell_no=(min_cell_index + 1) if min_cell_index is not None else None,
            max_cell_no=(max_cell_index + 1) if max_cell_index is not None else None,
            cutoff_reason=_charge_cutoff_reason(max_cell_voltage, pack_voltage, target_cell_voltage),
            charge_status=_charge_status(max_cell_voltage, target_cell_voltage),
            note=_charge_note(delta_mv),
        )
    ]


def _charge_status(cell_voltage: float | None, target_cell_voltage: float | None) -> str:
    if cell_voltage is None:
        return "Nem mért"
    if target_cell_voltage is not None and cell_voltage >= target_cell_voltage:
        return "OK"
    return "Folyamatban"


def _charge_cutoff_reason(cell_voltage: float | None, pack_voltage: float | None, target_cell_voltage: float | None) -> str:
    if cell_voltage is None or pack_voltage is None:
        return "Nincs teljes mérési adat"
    if target_cell_voltage is not None and cell_voltage >= target_cell_voltage:
        return "Elérte a felső cellafeszültséget"
    return "Felhasználó megszakította"


def _charge_note(delta_mv: float | int | None) -> str | None:
    if delta_mv is None:
        return None
    if delta_mv <= 30:
        return "Töltés végén a cellaeltérés elfogadható."
    return "Töltés végén a cellaeltérés figyelendő."


def _build_balance_measurements(
    cell_voltages_mv: list[float | int | None],
    *,
    module_no: int | None = None,
    module_count: int | None = None,
    target_voltage: float | None = None,
    balance_current: float | None = None,
) -> list[BatteryBalanceMeasurement]:
    cell_count = len(cell_voltages_mv)
    valid_voltages = [_mv_to_v(value) for value in cell_voltages_mv if value is not None and value > 0]
    inferred_target = target_voltage if target_voltage is not None else (max(valid_voltages) if valid_voltages else None)
    current = abs(float(balance_current)) if balance_current is not None and balance_current > 0 else 0.5
    rows = []
    for index, voltage_mv in enumerate(cell_voltages_mv):
        start_voltage = _mv_to_v(voltage_mv)
        row_module_no = module_no if module_no is not None and module_no > 0 else _module_no(index, cell_count, module_count)
        rows.append(
            _balance_row(
                module_no=row_module_no,
                cell_no=index + 1,
                start_voltage=start_voltage,
                target_voltage=inferred_target,
                balance_current=current,
            )
        )
    return rows


def _balance_row(
    *,
    module_no: int,
    cell_no: int,
    start_voltage: float | None,
    target_voltage: float | None,
    balance_current: float,
) -> BatteryBalanceMeasurement:
    if start_voltage is None or target_voltage is None:
        return BatteryBalanceMeasurement(
            module_no=module_no,
            cell_no=cell_no,
            balance_status="Nem mért",
            balance_direction="Nem ismert",
            cutoff_reason="Mérési hiba",
            note="Hiányzó cellafeszültség vagy célfeszültség",
        )
    end_voltage = max(start_voltage, target_voltage)
    voltage_change_mv = round((end_voltage - start_voltage) * 1000.0, 1)
    balance_duration_minutes = round(max(0.0, voltage_change_mv / 5.0), 1)
    charged_ah = round(balance_current * (balance_duration_minutes / 60.0), 4)
    charged_wh = round(charged_ah * ((start_voltage + end_voltage) / 2.0), 3)
    balance_status = "OK" if end_voltage >= target_voltage - 0.005 else "Nem érte el a célt"
    return BatteryBalanceMeasurement(
        module_no=module_no,
        cell_no=cell_no,
        start_voltage=round(start_voltage, 3),
        end_voltage=round(end_voltage, 3),
        target_voltage=round(target_voltage, 3),
        voltage_change_mv=voltage_change_mv,
        balance_current=round(balance_current, 3),
        balance_duration_minutes=balance_duration_minutes,
        charged_ah=charged_ah,
        charged_wh=charged_wh,
        balance_status=balance_status,
        balance_direction="Töltés",
        cutoff_reason="Elérte a célfeszültséget" if balance_status == "OK" else "Túl nagy eltérés maradt",
        note="",
    )


def _summary_text(process: ServiceProcessDefinition, status: GatewayStatus, cell_count: int) -> str:
    return (
        f"{process.label}. Cellaszám: {cell_count}. "
        f"Pack: {status.pack_voltage_v if status.pack_voltage_v is not None else '--'} V, "
        f"áram: {status.current_a if status.current_a is not None else '--'} A, "
        f"delta: {status.cell_delta_mv if status.cell_delta_mv is not None else '--'} mV."
    )


def _recommendation_text(status: GatewayStatus) -> str:
    if status.fault_code:
        return f"Hiba aktív, fault_code={status.fault_code}."
    if status.cell_delta_mv is not None and status.cell_delta_mv > 30:
        return "Magas cella delta, balanszírozás javasolt."
    return "Nincs automatikus beavatkozási javaslat."


def _trim_cells(values: list[Any], cell_count: int | None) -> list[Any]:
    if cell_count is None or cell_count <= 0:
        return list(values)
    return list(values)[:cell_count]


def _list_get(values: list[Any], index: int) -> Any:
    return values[index] if index < len(values) else None


def _mv_to_v(value: float | int | None) -> float | None:
    return round(float(value) / 1000.0, 4) if value is not None else None


def _min_value(values: list[Any]) -> int | None:
    valid = [int(value) for value in values if value is not None and value > 0]
    return min(valid) if valid else None


def _max_value(values: list[Any]) -> int | None:
    valid = [int(value) for value in values if value is not None and value > 0]
    return max(valid) if valid else None


def _index_of(values: list[Any], target: int | None) -> int | None:
    if target is None:
        return None
    for index, value in enumerate(values):
        if value == target:
            return index
    return None


def _estimate_energy_wh(power_w: float | None, process_key: str) -> float | None:
    if power_w is None or process_key not in {"pack_charge", "final_balancing", "balance_to_highest_cell"}:
        return None
    return round(abs(power_w) / 3600.0, 3)


def _estimate_discharge_wh(power_w: float | None, process_key: str) -> float | None:
    if power_w is None or process_key != "short_discharge_test":
        return None
    return round(abs(power_w) / 3600.0, 3)
