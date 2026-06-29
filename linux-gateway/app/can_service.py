import asyncio
import time
from typing import Callable, Awaitable

import can

from .can_protocol import decode_frame, encode_command, encode_heartbeat, CommandId
from .models import GatewayStatus


StatusCallback = Callable[[GatewayStatus], Awaitable[None]]


class CanService:
    def __init__(self, channel: str = "vcan0", bustype: str = "socketcan") -> None:
        self.channel = channel
        self.bustype = bustype
        self.bus: can.BusABC | None = None
        self.status = GatewayStatus()
        self._running = False
        self._sequence = 0
        self._callbacks: list[StatusCallback] = []

    def add_status_callback(self, callback: StatusCallback) -> None:
        self._callbacks.append(callback)

    async def start(self) -> None:
        self.bus = can.Bus(interface=self.bustype, channel=self.channel)
        self._running = True
        asyncio.create_task(self._rx_loop())
        asyncio.create_task(self._heartbeat_loop())

    async def stop(self) -> None:
        self._running = False
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
        for key, value in payload.items():
            if hasattr(self.status, key):
                setattr(self.status, key, value)

    async def _notify_status(self) -> None:
        for callback in self._callbacks:
            await callback(self.status)

    def _next_sequence(self) -> int:
        self._sequence = (self._sequence + 1) & 0xFF
        return self._sequence
