from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse

from .can_protocol import CommandId
from .can_service import CanService
from .models import CommandRequest, GatewayStatus

app = FastAPI(title="EV Battery Service Gateway")
can_service = CanService(channel="vcan0")
websockets: set[WebSocket] = set()


@app.on_event("startup")
async def on_startup() -> None:
    can_service.add_status_callback(broadcast_status)
    await can_service.start()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await can_service.stop()


@app.get("/api/status", response_model=GatewayStatus)
async def get_status() -> GatewayStatus:
    return can_service.status


@app.post("/api/command")
async def send_command(request: CommandRequest) -> dict:
    command_map = {
        "ping": CommandId.PING,
        "clear_fault": CommandId.CLEAR_FAULT,
        "measurement_start": CommandId.MEASUREMENT_START,
        "measurement_stop": CommandId.MEASUREMENT_STOP,
        "relay_all_off": CommandId.RELAY_ALL_OFF,
        "supply_output_off": CommandId.SUPPLY_OUTPUT_OFF,
        "balancer_all_off": CommandId.BALANCER_ALL_OFF,
        "emergency_stop": CommandId.EMERGENCY_STOP,
    }
    command = command_map.get(request.command)
    if command is None:
        raise HTTPException(status_code=400, detail="Unknown command")
    await can_service.send_command(command, request.value or 0)
    return {"ok": True, "command": request.command}


@app.websocket("/ws/status")
async def websocket_status(websocket: WebSocket) -> None:
    await websocket.accept()
    websockets.add(websocket)
    try:
        await websocket.send_json(can_service.status.model_dump())
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websockets.discard(websocket)


async def broadcast_status(status: GatewayStatus) -> None:
    dead: list[WebSocket] = []
    for websocket in websockets:
        try:
            await websocket.send_json(status.model_dump())
        except Exception:
            dead.append(websocket)
    for websocket in dead:
        websockets.discard(websocket)


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return """
<!doctype html>
<html lang="hu">
<head>
  <meta charset="utf-8" />
  <title>EV Battery Service Gateway</title>
  <style>
    body { font-family: sans-serif; margin: 2rem; }
    pre { background: #f4f4f4; padding: 1rem; }
    button { margin: 0.25rem; padding: 0.5rem 1rem; }
    .danger { font-weight: bold; }
  </style>
</head>
<body>
  <h1>EV Battery Service Gateway</h1>
  <p>Első fejlesztői dashboard vcan0 / SocketCAN teszthez.</p>

  <h2>Státusz</h2>
  <pre id="status">Kapcsolódás...</pre>

  <h2>Parancsok</h2>
  <button onclick="cmd('ping')">PING</button>
  <button onclick="cmd('measurement_start')">Measurement start</button>
  <button onclick="cmd('measurement_stop')">Measurement stop</button>
  <button onclick="cmd('relay_all_off')">Relay all OFF</button>
  <button onclick="cmd('supply_output_off')">Supply OFF</button>
  <button onclick="cmd('balancer_all_off')">Balancer OFF</button>
  <button class="danger" onclick="cmd('emergency_stop')">EMERGENCY STOP</button>

  <script>
    const statusEl = document.getElementById('status');
    const ws = new WebSocket(`ws://${location.host}/ws/status`);
    ws.onmessage = (event) => {
      statusEl.textContent = JSON.stringify(JSON.parse(event.data), null, 2);
    };
    async function cmd(command) {
      await fetch('/api/command', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({command})
      });
    }
  </script>
</body>
</html>
"""
