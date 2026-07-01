import csv
import io
from datetime import datetime, timezone
from pathlib import Path

from ..models import GatewayStatus
from .models import (
    BatteryInfo,
    MeasurementReport,
    QuickTestResult,
    ReportCharts,
    ReportCreateRequest,
    ReportSummary,
)


def _read_software_version() -> str:
    version_path = Path(__file__).resolve().parents[3] / "VERSION"
    try:
        return version_path.read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"


def _volts_from_mv(value: int | None) -> float | None:
    if value is None:
        return None
    return round(value / 1000, 4)


def _cell_volts(cells_mv: list[int | None]) -> list[float | None]:
    return [_volts_from_mv(value) for value in cells_mv]


def _result_from_status(status: GatewayStatus, warnings: list[str], faults: list[str]) -> str:
    if faults or status.fault_state or status.fault_code is not None:
        return "FAIL"
    if warnings:
        return "WARNING"
    if status.connected and status.measurement_valid:
        return "OK"
    return "UNKNOWN"


def _warnings_from_status(status: GatewayStatus) -> list[str]:
    warnings: list[str] = []
    if not status.connected:
        warnings.append("CAN connection is not active.")
    if not status.measurement_valid:
        warnings.append("Measurement validity flag is false.")
    if status.cell_delta_mv is not None and status.cell_delta_mv > 50:
        warnings.append("Cell voltage delta is above 50 mV.")
    return warnings


def _faults_from_status(status: GatewayStatus) -> list[str]:
    if status.fault_code is None and not status.fault_state:
        return []
    return [
        (
            f"fault_code={status.fault_code}, detail={status.fault_detail}, "
            f"source={status.fault_source}, severity={status.fault_severity}"
        )
    ]


def build_report_from_status(
    status: GatewayStatus,
    request: ReportCreateRequest,
    *,
    now: datetime | None = None,
) -> MeasurementReport:
    created_at = (now or datetime.now(timezone.utc)).isoformat()
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d%H%M%S")
    cells_v = _cell_volts(status.cell_voltages_mv)
    min_cell_v = _volts_from_mv(status.min_cell_mv)
    max_cell_v = _volts_from_mv(status.max_cell_mv)
    delta_cell_v = _volts_from_mv(status.cell_delta_mv)
    warnings = _warnings_from_status(status)
    faults = _faults_from_status(status)
    result = _result_from_status(status, warnings, faults)

    summary = ReportSummary(
        pack_voltage_start_v=status.pack_voltage_v,
        pack_voltage_end_v=status.pack_voltage_v,
        min_cell_v=min_cell_v,
        max_cell_v=max_cell_v,
        delta_cell_v=delta_cell_v,
        current_a=status.current_a,
        state_of_test="snapshot",
        result=result,
        result_summary=f"{len(cells_v)} cells captured from live gateway status.",
    )

    quick_test = QuickTestResult(
        load_current_a=status.current_a,
        pack_voltage_rest_v=status.pack_voltage_v,
        min_cell_voltage_rest_v=min_cell_v,
        max_cell_voltage_rest_v=max_cell_v,
        max_cell_delta_v=delta_cell_v,
        max_cell_resistance_mohm=status.max_cell_resistance_mohm,
        cell_voltage_rest_v=cells_v,
        cell_resistance_mohm=status.cell_resistances_mohm,
        warnings=warnings,
        faults=faults,
        result=result,
    )

    charts = ReportCharts(
        planned=[
            "cell_voltage_bar",
            "cell_delta",
            "pack_voltage_current_time",
            "cell_internal_resistance",
            "rest_load_recovery_compare",
        ]
    )

    return MeasurementReport(
        report_id=f"RPT-{stamp}",
        measurement_id=f"MEAS-{stamp}",
        created_at=created_at,
        operator_name=request.operator_name,
        customer_name=request.customer_name,
        vehicle_type=request.vehicle_type,
        erp_reference=request.erp_reference,
        invoice_number=request.invoice_number,
        work_order_id=request.work_order_id,
        software_version=_read_software_version(),
        measurement_type=request.measurement_type,
        battery=BatteryInfo(
            battery_id=request.battery_id,
            battery_type=request.battery_type,
            cell_count=len(cells_v),
            note=request.note,
        ),
        summary=summary,
        quick_test=quick_test,
        charts=charts,
        raw_status=status.model_dump(),
    )


def export_report_csv(report: MeasurementReport) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["section", "field", "value"])
    writer.writerow(["report", "report_id", report.report_id])
    writer.writerow(["report", "measurement_id", report.measurement_id])
    writer.writerow(["report", "created_at", report.created_at])
    writer.writerow(["report", "operator_name", report.operator_name])
    writer.writerow(["report", "customer_name", report.customer_name])
    writer.writerow(["report", "erp_reference", report.erp_reference])
    writer.writerow(["report", "invoice_number", report.invoice_number])
    writer.writerow(["report", "work_order_id", report.work_order_id])
    writer.writerow(["battery", "battery_id", report.battery.battery_id])
    writer.writerow(["battery", "cell_count", report.battery.cell_count])
    writer.writerow(["summary", "pack_voltage_start_v", report.summary.pack_voltage_start_v])
    writer.writerow(["summary", "current_a", report.summary.current_a])
    writer.writerow(["summary", "min_cell_v", report.summary.min_cell_v])
    writer.writerow(["summary", "max_cell_v", report.summary.max_cell_v])
    writer.writerow(["summary", "delta_cell_v", report.summary.delta_cell_v])
    writer.writerow(["summary", "result", report.summary.result])
    writer.writerow([])
    writer.writerow(["cell_index", "rest_voltage_v", "load_voltage_v", "drop_mv", "resistance_mohm"])
    for index, rest_v in enumerate(report.quick_test.cell_voltage_rest_v, start=1):
        load_v = _list_get(report.quick_test.cell_voltage_load_v, index - 1)
        drop_mv = _list_get(report.quick_test.cell_voltage_drop_mv, index - 1)
        resistance = _list_get(report.quick_test.cell_resistance_mohm, index - 1)
        writer.writerow([index, rest_v, load_v, drop_mv, resistance])
    return output.getvalue()


def _list_get(values: list, index: int):
    if index >= len(values):
        return None
    return values[index]


class ReportStore:
    def __init__(self) -> None:
        self._reports: dict[str, MeasurementReport] = {}

    def add(self, report: MeasurementReport) -> MeasurementReport:
        self._reports[report.measurement_id] = report
        return report

    def list(self) -> list[MeasurementReport]:
        return sorted(self._reports.values(), key=lambda report: report.created_at, reverse=True)

    def get(self, measurement_id: str) -> MeasurementReport | None:
        return self._reports.get(measurement_id)
