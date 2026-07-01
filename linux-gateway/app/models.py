from enum import IntEnum
from pydantic import BaseModel, Field


class SystemState(IntEnum):
    BOOT = 0
    SELF_TEST = 1
    IDLE = 2
    MEASURE = 3
    CHARGE = 4
    BALANCE = 5
    FAULT = 100
    EMERGENCY_OFF = 101


class GatewayStatus(BaseModel):
    connected: bool = False
    can_error: str | None = None
    system_state: int = int(SystemState.BOOT)
    fault_state: int = 0
    relay_flags: int = 0
    supply_flags: int = 0
    balancer_flags: int = 0
    active_profile: int = 0
    uptime_s: int = 0
    pack_voltage_v: float | None = None
    current_a: float | None = None
    power_w: float | None = None
    cell_voltages_mv: list[int | None] = Field(default_factory=list)
    cell_resistances_mohm: list[float | None] = Field(default_factory=list)
    resistance_measurement_running: bool = False
    min_cell_mv: int | None = None
    max_cell_mv: int | None = None
    cell_delta_mv: int | None = None
    max_cell_resistance_mohm: float | None = None
    fault_code: int | None = None
    fault_detail: int | None = None
    fault_source: int | None = None
    fault_severity: int | None = None
    fault_related_index: int | None = None
    last_command_id: int | None = None
    last_command_seq: int | None = None
    last_command_result: int | None = None
    last_command_reject_reason: int | None = None
    measurement_valid: bool = False
    last_can_rx_ms: int | None = None


class CommandRequest(BaseModel):
    command: str = Field(..., examples=["emergency_stop", "measurement_start", "measurement_stop"])
    value: int | None = None
