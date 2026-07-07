from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class RepairJob(BaseModel):
    name: str
    customer: str | None = None
    license_plate: str | None = None
    vehicle_make: str | None = None
    vehicle_model: str | None = None
    vehicle_year: int | str | None = None
    vin: str | None = None
    job_status: str | None = None
    pre_measurement_done: bool | None = None
    post_measurement_done: bool | None = None
    last_measurement_datetime: str | None = None
    cell_count: int | None = None
    module_count: int | None = None


class MeasurementStatusUpdate(BaseModel):
    measurement_type: Literal["pre", "post"]
    measurement_id: str
    measurement_datetime: datetime
    status: str = "done"


class BatteryCellMeasurement(BaseModel):
    module_no: int
    cell_no: int | None = None
    cell_group_no: int | None = None
    voltage: float | None = None
    cell_voltage: float | None = None
    open_voltage: float | None = None
    loaded_cell_voltage: float | None = None
    loaded_voltage: float | None = None
    internal_resistance: float | None = None
    temperature: float | None = None
    charged_energy_wh: float | None = None
    discharged_energy_wh: float | None = None
    status: str | None = None
    cell_status: str | None = None
    note: str | None = None


class BatteryMeasurementValue(BaseModel):
    key: str
    value: str | int | float | bool | None = None
    unit: str | None = None
    note: str | None = None


class BatteryResistanceMeasurement(BaseModel):
    module_no: int
    cell_no: int
    rest_voltage: float | None = None
    load_voltage: float | None = None
    load_current: float | None = None
    voltage_drop_mv: float | None = None
    internal_resistance_mohm: float | None = None
    resistance_status: str
    note: str | None = None


class BatteryDischargeMeasurement(BaseModel):
    module_no: int
    start_voltage: float | None = None
    end_voltage: float | None = None
    start_min_cell_voltage: float | None = None
    end_min_cell_voltage: float | None = None
    start_max_cell_voltage: float | None = None
    end_max_cell_voltage: float | None = None
    start_delta_mv: float | None = None
    end_delta_mv: float | None = None
    discharge_current: float | None = None
    discharge_duration_minutes: float | None = None
    discharged_ah: float | None = None
    discharged_wh: float | None = None
    min_cell_no: int | None = None
    max_cell_no: int | None = None
    cutoff_reason: str | None = None
    discharge_status: str
    note: str | None = None


class BatteryChargeMeasurement(BaseModel):
    module_no: int
    start_voltage: float | None = None
    end_voltage: float | None = None
    start_min_cell_voltage: float | None = None
    end_min_cell_voltage: float | None = None
    start_max_cell_voltage: float | None = None
    end_max_cell_voltage: float | None = None
    start_delta_mv: float | None = None
    end_delta_mv: float | None = None
    charge_current: float | None = None
    charge_duration_minutes: float | None = None
    charged_ah: float | None = None
    charged_wh: float | None = None
    min_cell_no: int | None = None
    max_cell_no: int | None = None
    cutoff_reason: str | None = None
    charge_status: str
    note: str | None = None


class BatteryBalanceMeasurement(BaseModel):
    module_no: int
    cell_no: int
    start_voltage: float | None = None
    end_voltage: float | None = None
    target_voltage: float | None = None
    voltage_change_mv: float | None = None
    balance_current: float | None = None
    balance_duration_minutes: float | None = None
    charged_ah: float | None = None
    charged_wh: float | None = None
    balance_status: str
    balance_direction: str
    cutoff_reason: str | None = None
    note: str | None = None


class BatteryMeasurementPayload(BaseModel):
    repair_job: str
    measurement_stage: str
    test_type: str
    api_measurement_id: str
    measurement_start: datetime
    measurement_name: str | None = None
    measurement_no: int | None = None
    measurement_end: datetime | None = None
    measurement_status: str = "Kész"
    min_cell_voltage: float | None = None
    max_cell_voltage: float | None = None
    max_cell_delta_mv: float | None = None
    weakest_module: str | None = None
    weakest_cell: str | None = None
    worst_moment_time: datetime | None = None
    worst_moment_current: float | None = None
    worst_moment_energy_wh: float | None = None
    discharged_energy_wh: float | None = None
    charged_energy_wh: float | None = None
    discharged_capacity_ah: float | None = None
    charged_capacity_ah: float | None = None
    module_no: int | None = None
    cell_count: int | None = None
    module_count: int | None = None
    cells: list[BatteryCellMeasurement]
    balance_measurements: list[BatteryBalanceMeasurement] = Field(default_factory=list)
    charge_measurements: list[BatteryChargeMeasurement] = Field(default_factory=list)
    resistance_measurements: list[BatteryResistanceMeasurement] = Field(default_factory=list)
    discharge_measurements: list[BatteryDischargeMeasurement] = Field(default_factory=list)
    measurement_values: list[BatteryMeasurementValue] = Field(default_factory=list)
    summary: str | None = None
    recommendation: str | None = None
    process_key: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
