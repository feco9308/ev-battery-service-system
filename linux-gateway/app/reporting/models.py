from pydantic import BaseModel, Field


class ReportCreateRequest(BaseModel):
    operator_name: str = ""
    customer_name: str = ""
    vehicle_type: str = ""
    battery_id: str = ""
    battery_type: str = ""
    measurement_type: str = "quick_test_internal_resistance"
    erp_reference: str = ""
    invoice_number: str = ""
    work_order_id: str = ""
    note: str = ""


class BatteryInfo(BaseModel):
    battery_id: str = ""
    battery_type: str = ""
    cell_count: int = 0
    nominal_voltage_v: float | None = None
    note: str = ""


class ReportSummary(BaseModel):
    pack_voltage_start_v: float | None = None
    pack_voltage_end_v: float | None = None
    min_cell_v: float | None = None
    max_cell_v: float | None = None
    delta_cell_v: float | None = None
    current_a: float | None = None
    state_of_test: str = "snapshot"
    result: str = "UNKNOWN"
    result_summary: str = ""


class QuickTestResult(BaseModel):
    test_type: str = "quick_test_internal_resistance"
    load_current_a: float | None = None
    load_duration_ms: int | None = None
    pack_voltage_rest_v: float | None = None
    pack_voltage_load_v: float | None = None
    pack_voltage_recovery_v: float | None = None
    pack_resistance_mohm: float | None = None
    min_cell_voltage_rest_v: float | None = None
    max_cell_voltage_rest_v: float | None = None
    min_cell_voltage_load_v: float | None = None
    max_cell_voltage_load_v: float | None = None
    max_cell_delta_v: float | None = None
    max_cell_resistance_mohm: float | None = None
    cell_voltage_rest_v: list[float | None] = Field(default_factory=list)
    cell_voltage_load_v: list[float | None] = Field(default_factory=list)
    cell_voltage_drop_mv: list[float | None] = Field(default_factory=list)
    cell_resistance_mohm: list[float | None] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    faults: list[str] = Field(default_factory=list)
    result: str = "UNKNOWN"


class ReportCharts(BaseModel):
    cell_voltage_chart: str | None = None
    cell_delta_chart: str | None = None
    pack_time_chart: str | None = None
    cell_resistance_chart: str | None = None
    load_compare_chart: str | None = None
    planned: list[str] = Field(default_factory=list)


class MeasurementReport(BaseModel):
    report_id: str
    measurement_id: str
    device_id: str = "evsys-001"
    created_at: str
    operator_name: str = ""
    customer_name: str = ""
    vehicle_type: str = ""
    erp_reference: str = ""
    invoice_number: str = ""
    work_order_id: str = ""
    software_version: str = "0.0.0"
    protocol_version: str = "can-gateway-protocol-v0.1"
    measurement_type: str = "quick_test_internal_resistance"
    battery: BatteryInfo
    summary: ReportSummary
    quick_test: QuickTestResult
    charts: ReportCharts
    raw_status: dict
