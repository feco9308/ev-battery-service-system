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
    measurement_valid: bool = False
    last_can_rx_ms: int | None = None


class CommandRequest(BaseModel):
    command: str = Field(..., examples=["emergency_stop", "measurement_start", "measurement_stop"])
    value: int | None = None
