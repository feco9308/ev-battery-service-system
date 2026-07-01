import asyncio
import logging
import time
from typing import Callable, Awaitable

import can

from .can_protocol import decode_frame, encode_command, encode_heartbeat, CommandId
from .models import GatewayStatus


StatusCallback = Callable[[GatewayStatus], Awaitable[None]]
logger = logging.getLogger(__name__)


class CanService:
    def __init__(self, channel: str = "vcan0", bustype: str = "socketcan", rx_timeout_s: float = 2.0) -> None:
        self.channel = channel
        self.bustype = bustype
        self.rx_timeout_s = rx_timeout_s
        self.bus: can.BusABC | None = None
        self.status = GatewayStatus()
        self._running = False
        self._sequence = 0
        self._callbacks: list[StatusCallback] = []
        self._tasks: list[asyncio.Task] = []

    def add_status_callback(self, callback: StatusCallback) -> None:
        self._callbacks.append(callback)

    async def start(self) -> None:
        try:
            self.bus = can.Bus(interface=self.bustype, channel=self.channel)
            self.status.can_error = None
        except (can.CanError, OSError) as exc:
            self.status.can_error = f"CAN bus start failed on {self.channel}: {exc}"
            logger.warning(self.status.can_error)
            self.bus = None
        self._running = True
        self._tasks = [
            asyncio.create_task(self._rx_loop()),
            asyncio.create_task(self._heartbeat_loop()),
            asyncio.create_task(self._timeout_loop()),
        ]

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks = []
        if self.bus is not None:
            self.bus.shutdown()
            self.bus = None

    async def send_command(self, command: CommandId, parameter: int = 0) -> None:
        if self.bus is None:
            raise RuntimeError("CAN bus is not started")
        arbitration_id, data = encode_command(command, self._next_sequence(), parameter)
        msg = can.Message(arbitration_id=arbitration_id, data=data, is_extended_id=False)
        self.bus.send(msg)

    async def _heartbeat_loop(self) -> None:
        while self._running:
            if self.bus is not None:
                arbitration_id, data = encode_heartbeat(self._next_sequence())
                msg = can.Message(arbitration_id=arbitration_id, data=data, is_extended_id=False)
                try:
                    self.bus.send(msg)
                except can.CanError:
                    pass
            await asyncio.sleep(0.5)

    async def _rx_loop(self) -> None:
        while self._running:
            if self.bus is None:
                await asyncio.sleep(0.1)
                continue
            msg = await asyncio.to_thread(self.bus.recv, 0.1)
            if msg is None:
                continue
            decoded = decode_frame(msg.arbitration_id, bytes(msg.data))
            if decoded is None:
                continue
            self._apply_decoded_frame(decoded.name, decoded.payload)
            await self._notify_status()

    def _apply_decoded_frame(self, name: str, payload: dict) -> None:
        self.status.connected = True
        self.status.last_can_rx_ms = int(time.time() * 1000)
        if name == "cell_voltages":
            self._apply_cell_voltages(payload)
            return
        if name == "cell_resistances":
            self._apply_cell_resistances(payload)
            return
        if name == "fault":
            self.status.fault_code = payload["fault_code"]
            self.status.fault_detail = payload["fault_detail"]
            self.status.fault_source = payload["source"]
            self.status.fault_severity = payload["severity"]
            self.status.fault_related_index = payload["related_index"]
            self.status.uptime_s = payload["uptime_s"]
            return
        if name == "command_ack":
            self.status.last_command_id = payload["command_id"]
            self.status.last_command_seq = payload["command_seq"]
            self.status.last_command_result = payload["result_code"]
            self.status.last_command_reject_reason = payload["reject_reason"]
            return
        for key, value in payload.items():
            if hasattr(self.status, key):
                setattr(self.status, key, value)

    def _apply_cell_voltages(self, payload: dict) -> None:
        first_cell_index = int(payload["first_cell_index"])
        values = list(payload["cell_voltages_mv"])
        required_len = first_cell_index + len(values)
        if len(self.status.cell_voltages_mv) < required_len:
            self.status.cell_voltages_mv.extend([None] * (required_len - len(self.status.cell_voltages_mv)))
        for offset, value in enumerate(values):
            self.status.cell_voltages_mv[first_cell_index + offset] = value
        valid_values = [value for value in self.status.cell_voltages_mv if value is not None and value > 0]
        if valid_values:
            self.status.min_cell_mv = min(valid_values)
            self.status.max_cell_mv = max(valid_values)
            self.status.cell_delta_mv = self.status.max_cell_mv - self.status.min_cell_mv

    def _apply_cell_resistances(self, payload: dict) -> None:
        if not self.status.resistance_measurement_running:
            return
        first_cell_index = int(payload["first_cell_index"])
        values = list(payload["cell_resistances_mohm"])
        required_len = first_cell_index + len(values)
        if len(self.status.cell_resistances_mohm) < required_len:
            self.status.cell_resistances_mohm.extend([None] * (required_len - len(self.status.cell_resistances_mohm)))
        for offset, value in enumerate(values):
            self.status.cell_resistances_mohm[first_cell_index + offset] = value
        valid_values = [value for value in self.status.cell_resistances_mohm if value is not None and value > 0]
        if valid_values:
            self.status.max_cell_resistance_mohm = max(valid_values)

    async def _timeout_loop(self) -> None:
        while self._running:
            await asyncio.sleep(0.25)
            if self.status.last_can_rx_ms is None:
                continue
            age_s = (int(time.time() * 1000) - self.status.last_can_rx_ms) / 1000
            if self.status.connected and age_s > self.rx_timeout_s:
                self.status.connected = False
                await self._notify_status()

    async def _notify_status(self) -> None:
        for callback in self._callbacks:
            await callback(self.status)

    def _next_sequence(self) -> int:
        self._sequence = (self._sequence + 1) & 0xFF
        return self._sequence
