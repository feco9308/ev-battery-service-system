from datetime import datetime, timezone

from app.models import GatewayStatus
from app.reporting.models import ReportCreateRequest
from app.reporting.service import build_report_from_status, export_report_csv


def test_build_report_from_live_status_snapshot() -> None:
    status = GatewayStatus(
        connected=True,
        measurement_valid=True,
        pack_voltage_v=360.0,
        current_a=12.34,
        cell_voltages_mv=[3700, 3710, 3720],
        cell_resistances_mohm=[1.8, 2.0, 2.4],
        min_cell_mv=3700,
        max_cell_mv=3720,
        cell_delta_mv=20,
        max_cell_resistance_mohm=2.4,
    )
    request = ReportCreateRequest(
        operator_name="ERP",
        customer_name="Workshop",
        vehicle_type="Test vehicle",
        battery_id="BAT-001",
        measurement_type="quick_test_internal_resistance",
        erp_reference="NEXT-ERP-123",
        invoice_number="SZ-2026-0001",
        work_order_id="ML-2026-0001",
    )

    report = build_report_from_status(
        status,
        request,
        now=datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc),
    )

    assert report.report_id == "RPT-20260630120000"
    assert report.measurement_id == "MEAS-20260630120000"
    assert report.battery.cell_count == 3
    assert report.erp_reference == "NEXT-ERP-123"
    assert report.invoice_number == "SZ-2026-0001"
    assert report.work_order_id == "ML-2026-0001"
    assert report.summary.result == "OK"
    assert report.summary.pack_voltage_start_v == 360.0
    assert report.summary.min_cell_v == 3.7
    assert report.summary.max_cell_v == 3.72
    assert report.summary.delta_cell_v == 0.02
    assert report.quick_test.cell_voltage_rest_v == [3.7, 3.71, 3.72]
    assert report.quick_test.cell_resistance_mohm == [1.8, 2.0, 2.4]
    assert report.quick_test.max_cell_resistance_mohm == 2.4
    assert "cell_voltage_bar" in report.charts.planned


def test_report_marks_fault_as_fail() -> None:
    status = GatewayStatus(
        connected=True,
        measurement_valid=True,
        fault_code=4,
        fault_detail=2,
        fault_source=1,
        fault_severity=3,
    )

    report = build_report_from_status(status, ReportCreateRequest())

    assert report.summary.result == "FAIL"
    assert report.quick_test.result == "FAIL"
    assert report.quick_test.faults == ["fault_code=4, detail=2, source=1, severity=3"]


def test_export_report_csv_contains_summary_and_cells() -> None:
    status = GatewayStatus(
        connected=True,
        measurement_valid=True,
        pack_voltage_v=360.0,
        current_a=12.34,
        cell_voltages_mv=[3700, 3710],
        min_cell_mv=3700,
        max_cell_mv=3710,
        cell_delta_mv=10,
    )
    report = build_report_from_status(
        status,
        ReportCreateRequest(
            battery_id="BAT-001",
            erp_reference="NEXT-ERP-123",
            invoice_number="SZ-2026-0001",
        ),
    )

    csv_text = export_report_csv(report)

    assert "report,report_id," in csv_text
    assert "battery,battery_id,BAT-001" in csv_text
    assert "report,erp_reference,NEXT-ERP-123" in csv_text
    assert "report,invoice_number,SZ-2026-0001" in csv_text
    assert "summary,result,OK" in csv_text
    assert "cell_index,rest_voltage_v,load_voltage_v,drop_mv,resistance_mohm" in csv_text
    assert "1,3.7,,," in csv_text
