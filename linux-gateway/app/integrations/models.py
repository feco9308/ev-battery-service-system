from datetime import datetime
from typing import Literal

from pydantic import BaseModel


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


class MeasurementStatusUpdate(BaseModel):
    measurement_type: Literal["pre", "post"]
    measurement_id: str
    measurement_datetime: datetime
    status: str = "done"


class BatteryCellMeasurement(BaseModel):
    module_no: int
    cell_group_no: int
    voltage: float
    internal_resistance: float | None = None
    temperature: float | None = None
    status: str | None = None
    note: str | None = None


class BatteryMeasurementPayload(BaseModel):
    repair_job: str
    measurement_type: Literal["pre", "post", "balancing", "load_test"]
    api_measurement_id: str
    measurement_datetime: datetime
    cells: list[BatteryCellMeasurement]
    summary: str | None = None
