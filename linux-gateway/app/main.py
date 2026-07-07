import os
import secrets

from fastapi import Depends, FastAPI, Header, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, Response

from .can_protocol import CommandId, LoadLevel, MeasurementType, encode_measurement_start_parameter
from .can_service import CanService
from .integrations import (
    BatteryMeasurementPayload,
    ErpNextClient,
    ErpNextError,
    MeasurementStatusUpdate,
    RepairJob,
)
from .integrations.measurement_store import LocalMeasurementStore
from .models import CommandRequest, GatewayStatus
from .reporting import ReportStore, build_report_from_status, export_report_csv
from .reporting.models import MeasurementReport, ReportCreateRequest
from .service_processes import (
    SERVICE_PROCESS_BY_KEY,
    ServiceProcessResult,
    ServiceProcessStartRequest,
    automatic_cycle_step_labels,
    build_measurement_payload,
    get_process_definitions,
)

app = FastAPI(title="EV Battery Service Gateway")
can_service = CanService(channel="vcan0")
report_store = ReportStore()
measurement_store = LocalMeasurementStore()
websockets: set[WebSocket] = set()


def verify_report_api_token(authorization: str | None = None, x_api_key: str | None = None) -> None:
    expected_token = os.getenv("GATEWAY_API_TOKEN")
    if not expected_token:
        return
    bearer_prefix = "Bearer "
    supplied_token = x_api_key or ""
    if authorization and authorization.startswith(bearer_prefix):
        supplied_token = authorization[len(bearer_prefix):]
    if not secrets.compare_digest(supplied_token, expected_token):
        raise HTTPException(status_code=401, detail="Invalid or missing report API token")


def require_report_api_token(authorization: str | None = Header(default=None), x_api_key: str | None = Header(default=None)) -> None:
    verify_report_api_token(authorization=authorization, x_api_key=x_api_key)


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


def erpnext_client() -> ErpNextClient:
    return ErpNextClient()


def erpnext_error_response(exc: ErpNextError) -> HTTPException:
    detail: dict = {"message": str(exc)}
    if exc.detail is not None:
        detail["erpnext_detail"] = exc.detail
    return HTTPException(status_code=exc.status_code, detail=detail)


@app.get("/api/erpnext/health", dependencies=[Depends(require_report_api_token)])
async def erpnext_health() -> dict:
    try:
        checked_doctype = erpnext_client().get_logged_user()
    except ErpNextError as exc:
        raise erpnext_error_response(exc) from exc
    return {"ok": True, "checked_doctype": checked_doctype}


@app.get("/api/erpnext/repair-jobs", response_model=list[RepairJob], dependencies=[Depends(require_report_api_token)])
async def list_erpnext_repair_jobs() -> list[RepairJob]:
    try:
        return erpnext_client().list_open_repair_jobs()
    except ErpNextError as exc:
        raise erpnext_error_response(exc) from exc


@app.get("/api/erpnext/repair-jobs/{job_id}", dependencies=[Depends(require_report_api_token)])
async def get_erpnext_repair_job(job_id: str) -> dict:
    try:
        return erpnext_client().get_repair_job(job_id)
    except ErpNextError as exc:
        raise erpnext_error_response(exc) from exc


@app.put("/api/erpnext/repair-jobs/{job_id}/measurement-status", dependencies=[Depends(require_report_api_token)])
async def update_erpnext_measurement_status(job_id: str, update: MeasurementStatusUpdate) -> dict:
    try:
        document = erpnext_client().update_measurement_status(job_id, update)
    except ErpNextError as exc:
        raise erpnext_error_response(exc) from exc
    return {"ok": True, "repair_job": job_id, "data": document}


@app.post("/api/measurements/local", dependencies=[Depends(require_report_api_token)])
async def save_measurement_locally(payload: BatteryMeasurementPayload) -> dict:
    path = measurement_store.save(payload)
    return {"ok": True, "path": str(path)}


@app.get("/api/service-processes", dependencies=[Depends(require_report_api_token)])
async def list_service_processes() -> dict:
    return {
        "processes": [process.__dict__ for process in get_process_definitions()],
        "automatic_steps": automatic_cycle_step_labels(),
    }


@app.post("/api/service-processes/start", response_model=ServiceProcessResult, dependencies=[Depends(require_report_api_token)])
async def start_service_process(request: ServiceProcessStartRequest) -> ServiceProcessResult:
    process = SERVICE_PROCESS_BY_KEY.get(request.process_key)
    if process is None:
        raise HTTPException(status_code=400, detail="Unknown service process")
    payload = build_measurement_payload(can_service.status, request, process)
    local_path = measurement_store.save(payload)
    erpnext_measurement = None
    erpnext_error = None
    if request.auto_upload and request.repair_job:
        try:
            erpnext_measurement = erpnext_client().create_battery_measurement(payload, overwrite_existing=request.overwrite_existing)
        except ErpNextError as exc:
            erpnext_error = {"message": str(exc), "status_code": exc.status_code, "detail": exc.detail}
    return ServiceProcessResult(
        process_key=process.key,
        label=process.label,
        api_measurement_id=payload.api_measurement_id,
        repair_job=request.repair_job,
        local_path=str(local_path),
        erpnext_measurement=erpnext_measurement,
        erpnext_error=erpnext_error,
        next_steps=automatic_cycle_step_labels() if request.process_key == "full_post_repair_cycle" else [],
    )


@app.get("/api/reports", response_model=list[MeasurementReport], dependencies=[Depends(require_report_api_token)])
async def list_reports() -> list[MeasurementReport]:
    return report_store.list()


@app.post("/api/reports", response_model=MeasurementReport, dependencies=[Depends(require_report_api_token)])
async def create_report(request: ReportCreateRequest) -> MeasurementReport:
    report = build_report_from_status(can_service.status, request)
    return report_store.add(report)


@app.get("/api/reports/{measurement_id}", response_model=MeasurementReport, dependencies=[Depends(require_report_api_token)])
async def get_report(measurement_id: str) -> MeasurementReport:
    report = report_store.get(measurement_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@app.get("/api/reports/{measurement_id}/json", response_model=MeasurementReport, dependencies=[Depends(require_report_api_token)])
async def export_report_json(measurement_id: str) -> MeasurementReport:
    return await get_report(measurement_id)


@app.get("/api/reports/{measurement_id}/csv", dependencies=[Depends(require_report_api_token)])
async def export_report_csv_endpoint(measurement_id: str) -> Response:
    report = await get_report(measurement_id)
    return Response(
        content=export_report_csv(report),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{measurement_id}.csv"'},
    )


@app.get("/api/reports/{measurement_id}/pdf", dependencies=[Depends(require_report_api_token)])
async def export_report_pdf(measurement_id: str) -> None:
    await get_report(measurement_id)
    raise HTTPException(status_code=501, detail="PDF export is planned but not implemented yet")


@app.get("/api/reports/{measurement_id}/docx", dependencies=[Depends(require_report_api_token)])
async def export_report_docx(measurement_id: str) -> None:
    await get_report(measurement_id)
    raise HTTPException(status_code=501, detail="DOCX export is planned but not implemented yet")


@app.post("/api/command")
async def send_command(request: CommandRequest) -> dict:
    command_map = {
        "ping": CommandId.PING,
        "clear_fault": CommandId.CLEAR_FAULT,
        "measurement_start": CommandId.MEASUREMENT_START,
        "internal_resistance_start": CommandId.MEASUREMENT_START,
        "measurement_stop": CommandId.MEASUREMENT_STOP,
        "relay_all_off": CommandId.RELAY_ALL_OFF,
        "supply_output_off": CommandId.SUPPLY_OUTPUT_OFF,
        "balancer_all_off": CommandId.BALANCER_ALL_OFF,
        "emergency_stop": CommandId.EMERGENCY_STOP,
    }
    command = command_map.get(request.command)
    if command is None:
        raise HTTPException(status_code=400, detail="Unknown command")
    parameter = request.value or 0
    if request.command == "internal_resistance_start":
        try:
            load_level = LoadLevel(parameter)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid load level") from exc
        parameter = encode_measurement_start_parameter(MeasurementType.QUICK_TEST_INTERNAL_RESISTANCE, load_level)
    try:
        await can_service.send_command(command, parameter)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if request.command == "internal_resistance_start":
        can_service.status.resistance_measurement_running = True
    elif request.command == "measurement_stop":
        can_service.status.resistance_measurement_running = False
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
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>EV Battery Service Gateway</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f7f8;
      --panel: #ffffff;
      --panel-soft: #eef3f2;
      --ink: #17201d;
      --muted: #66736e;
      --line: #d8e0dd;
      --ok: #15803d;
      --warn: #b45309;
      --bad: #b42318;
      --accent: #0f766e;
      --accent-2: #2563eb;
      --shadow: 0 12px 30px rgba(23, 32, 29, 0.08);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    .shell {
      width: min(1440px, calc(100% - 32px));
      margin: 0 auto;
      padding: 24px 0 40px;
    }

    header {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 20px;
    }

    h1, h2, h3, p { margin: 0; }

    h1 {
      font-size: clamp(28px, 3vw, 42px);
      line-height: 1;
      font-weight: 800;
    }

    .subtitle {
      margin-top: 8px;
      color: var(--muted);
      font-size: 14px;
    }

    .connection {
      min-width: 210px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 12px 14px;
      box-shadow: var(--shadow);
    }

    .state-line {
      display: flex;
      align-items: center;
      gap: 9px;
      font-size: 14px;
      font-weight: 700;
    }

    .dot {
      width: 11px;
      height: 11px;
      border-radius: 999px;
      background: var(--warn);
    }

    .dot.ok { background: var(--ok); }
    .dot.bad { background: var(--bad); }

    .timestamp {
      margin-top: 6px;
      color: var(--muted);
      font-size: 12px;
      font-variant-numeric: tabular-nums;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(12, 1fr);
      gap: 14px;
    }

    .tabbar {
      display: flex;
      gap: 8px;
      margin: 0 0 16px;
      overflow-x: auto;
      padding-bottom: 2px;
    }

    .tab-button {
      flex: 0 0 auto;
      min-height: 40px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      color: var(--muted);
      padding: 0 14px;
      font-weight: 800;
    }

    .tab-button.active {
      border-color: var(--accent);
      background: var(--accent);
      color: #ffffff;
    }

    .tab-panel { display: none; }
    .tab-panel.active { display: block; }

    section {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: var(--shadow);
    }

    .span-3 { grid-column: span 3; }
    .span-4 { grid-column: span 4; }
    .span-5 { grid-column: span 5; }
    .span-7 { grid-column: span 7; }
    .span-12 { grid-column: span 12; }

    .metric {
      min-height: 122px;
      padding: 16px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      overflow: hidden;
    }

    .label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0;
      text-transform: uppercase;
    }

    .value {
      margin-top: 12px;
      font-size: 34px;
      line-height: 1;
      font-weight: 800;
      font-variant-numeric: tabular-nums;
      overflow-wrap: anywhere;
    }

    .unit {
      color: var(--muted);
      font-size: 16px;
      font-weight: 700;
    }

    .hint {
      margin-top: 10px;
      color: var(--muted);
      font-size: 13px;
      font-variant-numeric: tabular-nums;
    }

    .panel-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      border-bottom: 1px solid var(--line);
      padding: 14px 16px;
    }

    .panel-head h2 {
      font-size: 16px;
      line-height: 1.2;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      border-radius: 999px;
      background: var(--panel-soft);
      color: var(--muted);
      padding: 0 10px;
      font-size: 12px;
      font-weight: 800;
      white-space: nowrap;
    }

    .badge.ok {
      background: #dcfce7;
      color: #166534;
    }

    .badge.bad {
      background: #fee2e2;
      color: #991b1b;
    }

    .panel-body { padding: 16px; }

    .kv {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }

    .kv div {
      min-height: 58px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfc;
      padding: 10px;
    }

    .kv span {
      display: block;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }

    .kv strong {
      display: block;
      margin-top: 6px;
      font-size: 20px;
      font-variant-numeric: tabular-nums;
      overflow-wrap: anywhere;
    }

    .cells {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(86px, 1fr));
      gap: 8px;
    }

    .cell {
      min-height: 66px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfc;
      padding: 10px;
    }

    .cell small {
      display: block;
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
    }

    .cell strong {
      display: block;
      margin-top: 8px;
      font-size: 18px;
      font-variant-numeric: tabular-nums;
    }

    .cell.low { border-color: #60a5fa; background: #eff6ff; }
    .cell.high { border-color: #f59e0b; background: #fffbeb; }
    .cell.bad { border-color: var(--bad); background: #fff1f0; }

    .balance-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
      gap: 8px;
    }

    .balance-cell {
      min-height: 118px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfc;
      padding: 10px;
    }

    .balance-cell.active {
      border-color: #14b8a6;
      background: #f0fdfa;
    }

    .balance-cell small {
      display: block;
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
    }

    .balance-cell strong {
      display: block;
      margin-top: 6px;
      font-size: 18px;
      font-variant-numeric: tabular-nums;
    }

    .balance-cell span {
      display: block;
      margin-top: 4px;
      color: var(--muted);
      font-size: 12px;
      font-variant-numeric: tabular-nums;
    }

    .charge-bar {
      height: 8px;
      margin-top: 8px;
      border-radius: 999px;
      background: #e5e7eb;
      overflow: hidden;
    }

    .charge-bar i {
      display: block;
      height: 100%;
      border-radius: inherit;
      background: #14b8a6;
    }

    .commands {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 10px;
    }

    .form-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 12px;
    }

    .field {
      display: flex;
      flex-direction: column;
      gap: 7px;
    }

    .field label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }

    input, select {
      min-height: 42px;
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfc;
      color: var(--ink);
      padding: 0 10px;
      font: inherit;
      font-variant-numeric: tabular-nums;
    }

    .workflow {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-top: 12px;
    }

    .step {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfc;
      padding: 12px;
      min-height: 86px;
    }

    .step span {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 24px;
      height: 24px;
      border-radius: 999px;
      background: var(--accent-2);
      color: #ffffff;
      font-size: 12px;
      font-weight: 900;
    }

    .step strong {
      display: block;
      margin-top: 9px;
      font-size: 14px;
    }

    .step small {
      display: block;
      margin-top: 5px;
      color: var(--muted);
      line-height: 1.35;
    }

    button {
      min-height: 46px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      color: var(--ink);
      cursor: pointer;
      font-weight: 800;
      font-size: 13px;
    }

    button:hover { border-color: var(--accent); }
    button:active { transform: translateY(1px); }
    button:disabled { cursor: not-allowed; opacity: 0.5; }
    button.primary { background: var(--accent); border-color: var(--accent); color: white; }
    button.stop { background: #fff7ed; border-color: #fed7aa; color: #9a3412; }
    button.danger { background: var(--bad); border-color: var(--bad); color: white; }

    .log {
      min-height: 42px;
      margin-top: 12px;
      color: var(--muted);
      font-size: 13px;
    }

    details {
      border-top: 1px solid var(--line);
      padding: 12px 16px 16px;
    }

    summary {
      cursor: pointer;
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
    }

    pre {
      max-height: 260px;
      overflow: auto;
      margin: 12px 0 0;
      border-radius: 8px;
      background: #101817;
      color: #d8f3ed;
      padding: 14px;
      font-size: 12px;
      line-height: 1.45;
    }

    .error-text {
      color: var(--bad);
      font-size: 13px;
      overflow-wrap: anywhere;
    }

    @media (max-width: 980px) {
      .span-3, .span-4, .span-5, .span-7 { grid-column: span 6; }
      header { align-items: stretch; flex-direction: column; }
      .connection { min-width: 0; }
      .workflow { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }

    @media (max-width: 680px) {
      .shell { width: min(100% - 20px, 1440px); padding-top: 14px; }
      .span-3, .span-4, .span-5, .span-7 { grid-column: span 12; }
      .kv { grid-template-columns: 1fr; }
      .workflow { grid-template-columns: 1fr; }
      .value { font-size: 30px; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <div>
        <h1>EV Battery Service Gateway</h1>
        <p class="subtitle">Linux gateway kontrollpanel</p>
      </div>
      <aside class="connection">
        <div class="state-line"><span id="connDot" class="dot"></span><span id="connText">Kapcsolódás...</span></div>
        <div id="lastRx" class="timestamp">CAN RX: nincs adat</div>
      </aside>
    </header>

    <nav class="tabbar" aria-label="Gateway funkciók">
      <button class="tab-button active" data-tab="overview" onclick="showTab('overview')">Áttekintés</button>
      <button class="tab-button" data-tab="cells" onclick="showTab('cells')">Cella fesz mérés</button>
      <button class="tab-button" data-tab="resistance" onclick="showTab('resistance')">Ellenállás mérés</button>
      <button class="tab-button" data-tab="discharge" onclick="showTab('discharge')">Kisütés</button>
      <button class="tab-button" data-tab="cell-charge" onclick="showTab('cell-charge')">Balanszírozás</button>
      <button class="tab-button" data-tab="charge" onclick="showTab('charge')">Teljes töltés</button>
      <button class="tab-button" data-tab="cycle" onclick="showTab('cycle')">Teljes ciklus</button>
      <button class="tab-button" data-tab="report" onclick="showTab('report')">Jegyzőkönyv</button>
    </nav>

    <div id="tab-overview" class="tab-panel active">
      <div class="grid">
      <section class="metric span-3">
        <div class="label">Pack feszültség</div>
        <div class="value"><span id="packVoltage">--</span> <span class="unit">V</span></div>
        <div id="validText" class="hint">Mérés: --</div>
      </section>

      <section class="metric span-3">
        <div class="label">Áram</div>
        <div class="value"><span id="current">--</span> <span class="unit">A</span></div>
        <div class="hint">Teljesítmény: <span id="power">--</span> W</div>
      </section>

      <section class="metric span-3">
        <div class="label">Cella delta</div>
        <div class="value"><span id="cellDelta">--</span> <span class="unit">mV</span></div>
        <div class="hint">Min/Max: <span id="cellMinMax">--</span></div>
      </section>

      <section class="metric span-3">
        <div class="label">Rendszerállapot</div>
        <div class="value"><span id="systemState">--</span></div>
        <div class="hint">Uptime: <span id="uptime">--</span> s</div>
      </section>

      <section class="span-5">
        <div class="panel-head">
          <h2>ERPNext munkalap</h2>
          <span id="erpnextStatus" class="badge">Nincs ellenőrizve</span>
        </div>
        <div class="panel-body">
          <div class="commands">
            <button onclick="checkErpNextHealth()">Kapcsolat teszt</button>
            <button class="primary" onclick="loadErpNextJobs()">Munkalapok betöltése</button>
          </div>
          <div class="form-grid" style="margin-top: 14px;">
            <div class="field"><label>Munkalap</label><select id="erpnextJobSelect" onchange="selectErpNextJob()"></select></div>
            <div class="field"><label>Visszaírás típusa</label><select id="erpnextMeasurementType"><option value="pre">Javítás előtti</option><option value="post">Javítás utáni</option></select></div>
          </div>
          <div class="commands" style="margin-top: 14px;">
            <button onclick="writeErpNextMeasurementStatus()">Mérés kész visszaírása</button>
          </div>
          <div id="erpnextLog" class="log"></div>
        </div>
      </section>

      <section class="span-7">
        <div class="panel-head">
          <h2>Kiválasztott munkalap</h2>
          <span id="erpnextJobStatus" class="badge">Nincs kiválasztva</span>
        </div>
        <div class="panel-body">
          <div class="kv">
            <div><span>Név</span><strong id="erpnextJobName">--</strong></div>
            <div><span>Rendszám</span><strong id="erpnextLicensePlate">--</strong></div>
            <div><span>Jármű</span><strong id="erpnextVehicle">--</strong></div>
            <div><span>Ügyfél</span><strong id="erpnextCustomer">--</strong></div>
            <div><span>Javítás előtti mérés</span><strong id="erpnextPreDone">--</strong></div>
            <div><span>Javítás utáni mérés</span><strong id="erpnextPostDone">--</strong></div>
          </div>
        </div>
      </section>

      <section class="span-7">
        <div class="panel-head">
          <h2>Cellafeszültségek</h2>
          <span id="cellCount" class="badge">0 cella</span>
        </div>
        <div class="panel-body">
          <div id="cells" class="cells"></div>
        </div>
      </section>

      <section class="span-5">
        <div class="panel-head">
          <h2>Állapot részletek</h2>
          <span id="faultBadge" class="badge ok">Nincs fault</span>
        </div>
        <div class="panel-body">
          <div class="kv">
            <div><span>Relay flags</span><strong id="relayFlags">--</strong></div>
            <div><span>Supply flags</span><strong id="supplyFlags">--</strong></div>
            <div><span>Balancer flags</span><strong id="balancerFlags">--</strong></div>
            <div><span>Aktív profil</span><strong id="activeProfile">--</strong></div>
            <div><span>Fault code</span><strong id="faultCode">--</strong></div>
            <div><span>Fault severity</span><strong id="faultSeverity">--</strong></div>
          </div>
          <p id="canError" class="error-text"></p>
        </div>
      </section>

      <section class="span-12">
        <div class="panel-head">
          <h2>Parancsok</h2>
          <span id="commandState" class="badge">Készenlét</span>
        </div>
        <div class="panel-body">
          <div class="commands">
            <button onclick="cmd('ping')">PING</button>
            <button class="primary" onclick="cmd('measurement_start', true)">Measurement start</button>
            <button class="stop" onclick="cmd('measurement_stop')">Measurement stop</button>
            <button class="stop" onclick="cmd('relay_all_off')">Relay all OFF</button>
            <button class="stop" onclick="cmd('supply_output_off')">Supply OFF</button>
            <button class="stop" onclick="cmd('balancer_all_off')">Balancer OFF</button>
            <button class="danger" onclick="cmd('emergency_stop', true)">EMERGENCY STOP</button>
          </div>
          <div id="commandLog" class="log"></div>
        </div>
        <details>
          <summary>Nyers státusz JSON</summary>
          <pre id="rawStatus">{}</pre>
        </details>
      </section>
      </div>
    </div>

    <div id="tab-cells" class="tab-panel">
      <div class="grid">
        <section class="span-12">
          <div class="panel-head">
            <h2>Cella feszültség mérés</h2>
            <span id="cellCountMirror" class="badge">0 cella</span>
          </div>
          <div class="panel-body">
            <div class="form-grid">
              <div class="field">
                <label>Mérés típusa</label>
                <select id="cellMeasurementStage">
                  <option value="Beérkezéskori mérés">Beérkezéskori mérés</option>
                  <option value="Javítás utáni mérés">Javítás utáni mérés</option>
                  <option value="Merítés utáni mérés">Merítés utáni mérés</option>
                  <option value="Végső mérés">Végső mérés</option>
                  <option value="Köztes ellenőrző mérés">Köztes ellenőrző mérés</option>
                </select>
              </div>
              <div class="field"><label>Teljes cellaszám</label><input id="cellTargetCount" type="number" min="1" max="240" value="18"></div>
              <div class="field"><label>Mért modul</label><select id="cellModuleNo"></select></div>
              <div class="field"><label>Összes modul</label><input id="cellModuleCount" type="number" min="1" max="40" value="1"></div>
              <div class="field"><label>Alsó figyelmeztetés</label><input id="cellWarnLow" type="number" step="0.001" value="3.000"></div>
              <div class="field"><label>Felső figyelmeztetés</label><input id="cellWarnHigh" type="number" step="0.001" value="4.200"></div>
              <div class="field"><label>Max delta mV</label><input id="cellMaxDelta" type="number" step="1" value="20"></div>
            </div>
            <div class="commands" style="margin-top: 14px;">
              <button onclick="suggestCellConfigFromCan()">CAN alapján javasol</button>
              <button class="primary" onclick="startServiceProcess('cell_voltage_measurement')">Mérés mentése ERPNext-be</button>
            </div>
            <div id="cellModuleQuickSelect" class="commands" style="margin-top: 10px;"></div>
            <div id="cellMeasurementNamePreview" class="log"></div>
            <div id="cellVoltageWarningLog" class="log">Kék: legalacsonyabb cella, sárga: legmagasabb cella, piros: figyelmeztetési határon kívül.</div>
            <div id="cellVoltageLog" class="log"></div>
            <div id="cellsMirror" class="cells" style="margin-top: 14px;"></div>
          </div>
        </section>
      </div>
    </div>

    <div id="tab-resistance" class="tab-panel">
      <div class="grid">
        <section class="span-5">
          <div class="panel-head">
            <h2>Belső ellenállás mérés</h2>
            <span id="resistanceStatus" class="badge">Készenlét</span>
          </div>
          <div class="panel-body">
            <div class="form-grid">
              <div class="field">
                <label>Mérés típusa</label>
                <select id="resistanceMeasurementStage">
                  <option value="Beérkezéskori mérés">Beérkezéskori mérés</option>
                  <option value="Javítás utáni mérés">Javítás utáni mérés</option>
                  <option value="Merítés utáni mérés">Merítés utáni mérés</option>
                  <option value="Végső mérés">Végső mérés</option>
                  <option value="Köztes ellenőrző mérés">Köztes ellenőrző mérés</option>
                </select>
              </div>
              <div class="field">
                <label>Terhelés</label>
                <select id="resistanceLoadLevel">
                  <option value="1">LOW - kis terhelés</option>
                  <option value="2" selected>MEDIUM - közepes terhelés</option>
                  <option value="3">HIGH - nagy terhelés</option>
                  <option value="4">MAX - maximális tesztterhelés</option>
                </select>
              </div>
              <div class="field"><label>Megjelenített cellák</label><input id="resistanceCellCount" type="number" min="1" max="48" value="18"></div>
              <div class="field"><label>Mért modul</label><select id="resistanceModuleNo"></select></div>
              <div class="field"><label>Összes modul</label><input id="resistanceModuleCount" type="number" min="1" max="40" value="1"></div>
            </div>
            <div id="resistanceModuleQuickSelect" class="commands" style="margin-top: 10px;"></div>
            <div id="resistanceMeasurementNamePreview" class="log"></div>
            <div class="commands" style="margin-top: 14px;">
              <button class="primary" onclick="startResistanceMeasurement()">Mérés indítása</button>
              <button class="stop" onclick="cmd('measurement_stop')">Mérés leállítása</button>
              <button class="danger" onclick="cmd('emergency_stop', true)">EMERGENCY STOP</button>
            </div>
            <div class="commands" style="margin-top: 14px;">
              <button onclick="startServiceProcess('incoming_resistance')">Beérkezéskori eredmény mentése</button>
              <button onclick="startServiceProcess('module_cell_resistance')">Modul / cella eredmény mentése</button>
              <button onclick="startServiceProcess('post_discharge_resistance')">Merítés utáni eredmény mentése</button>
            </div>
            <div id="resistanceLog" class="log"></div>
          </div>
        </section>
        <section class="span-7">
          <div class="panel-head">
            <h2>Cellánkénti ellenállás</h2>
            <span id="resistanceCount" class="badge">0 cella</span>
          </div>
          <div class="panel-body">
            <div class="kv" style="margin-bottom: 14px;">
              <div><span>Max ellenállás</span><strong><span id="maxResistance">--</span> mOhm</strong></div>
              <div><span>Terhelőáram</span><strong><span id="resistanceCurrent">--</span> A</strong></div>
            </div>
            <div id="resistanceCells" class="cells"></div>
          </div>
        </section>
      </div>
    </div>

    <div id="tab-discharge" class="tab-panel">
      <div class="grid">
        <section class="span-7">
          <div class="panel-head">
            <h2>Kisütés beállítás</h2>
            <span class="badge">Előkészítve</span>
          </div>
          <div class="panel-body">
            <div class="form-grid">
              <div class="field">
                <label>Mérés típusa</label>
                <select id="dischargeMeasurementStage">
                  <option value="Beérkezéskori mérés">Beérkezéskori mérés</option>
                  <option value="Javítás utáni mérés" selected>Javítás utáni mérés</option>
                  <option value="Merítés utáni mérés">Merítés utáni mérés</option>
                  <option value="Végső mérés">Végső mérés</option>
                  <option value="Köztes ellenőrző mérés">Köztes ellenőrző mérés</option>
                </select>
              </div>
              <div class="field"><label>Mért modul</label><select id="dischargeModuleNo"></select><input id="dischargeModuleCount" type="hidden" value="1"></div>
              <div class="field"><label>Cél pack feszültség</label><input id="dischargePackTarget" type="number" step="0.1" value="300.0"></div>
              <div class="field"><label>Cél cellafeszültség</label><input id="dischargeCellTarget" type="number" step="0.001" value="3.000"></div>
              <div class="field"><label>Áramlimit</label><input id="dischargeCurrentLimit" type="number" step="0.1" value="10.0"></div>
              <div class="field"><label>Leállási feltétel</label><select id="dischargeStopMode"><option>Első cella cél alatt</option><option>Pack célfeszültség alatt</option><option>Időlimit</option></select></div>
            </div>
            <div id="dischargeModuleQuickSelect" class="commands" style="margin-top: 10px;"></div>
            <div id="dischargeMeasurementNamePreview" class="log"></div>
            <div class="commands" style="margin-top: 14px;">
              <button class="primary" onclick="cmd('measurement_start', true)">Kisütés előmérés indítása</button>
              <button onclick="startServiceProcess('short_discharge_test')">Kisütési eredmény mentése</button>
              <button class="stop" onclick="cmd('measurement_stop')">Mérés leállítása</button>
              <button class="danger" onclick="cmd('emergency_stop', true)">EMERGENCY STOP</button>
            </div>
            <div id="dischargeLog" class="log"></div>
          </div>
        </section>
        <section class="span-5">
          <div class="panel-head"><h2>Kisütés élő állapot</h2><span class="badge">CAN live</span></div>
          <div class="panel-body">
            <div class="kv">
              <div><span>Pack</span><strong><span id="dischargePack">--</span> V</strong></div>
              <div><span>Áram</span><strong><span id="dischargeCurrent">--</span> A</strong></div>
              <div><span>Min cella</span><strong><span id="dischargeMinCell">--</span> mV</strong></div>
              <div><span>Delta</span><strong><span id="dischargeDelta">--</span> mV</strong></div>
            </div>
          </div>
        </section>
      </div>
    </div>

    <div id="tab-cell-charge" class="tab-panel">
      <div class="grid">
        <section class="span-12">
          <div class="panel-head">
            <h2>Cellánkénti töltés és balansz</h2>
            <span class="badge">Panel balansz</span>
          </div>
          <div class="panel-body">
            <div class="form-grid">
              <div class="field">
                <label>Mérés típusa</label>
                <select id="balancingMeasurementStage">
                  <option value="Beérkezéskori mérés">Beérkezéskori mérés</option>
                  <option value="Javítás utáni mérés" selected>Javítás utáni mérés</option>
                  <option value="Merítés utáni mérés">Merítés utáni mérés</option>
                  <option value="Végső mérés">Végső mérés</option>
                  <option value="Köztes ellenőrző mérés">Köztes ellenőrző mérés</option>
                </select>
              </div>
              <div class="field"><label>Mért modul</label><select id="balancingModuleNo"></select><input id="balancingModuleCount" type="hidden" value="1"></div>
              <div class="field"><label>Balansz tartomány</label><input id="balanceScope" type="text" value="Kiválasztott modul teljes cellakészlete" readonly></div>
              <div class="field"><label>Modul célfeszültség</label><input id="singleCellTarget" type="number" step="0.001" value="4.100" oninput="renderBalancingChargePreview(latestStatus)"></div>
              <div class="field"><label>Panel áramlimit</label><input id="singleCellCurrent" type="number" step="0.01" value="0.50" oninput="renderBalancingChargePreview(latestStatus)"></div>
              <div class="field"><label>Balansz delta cél</label><input id="balanceDeltaTarget" type="number" step="1" value="10"></div>
            </div>
            <div id="balancingModuleQuickSelect" class="commands" style="margin-top: 10px;"></div>
            <div id="balancingMeasurementNamePreview" class="log"></div>
            <div class="kv" style="margin-top: 14px;">
              <div><span>Összes becsült töltés</span><strong><span id="balanceTotalAh">--</span> Ah</strong></div>
              <div><span>Összes becsült energia</span><strong><span id="balanceTotalWh">--</span> Wh</strong></div>
              <div><span>Legtöbbet kapó cella</span><strong id="balanceMaxCell">--</strong></div>
              <div><span>Becsült leghosszabb idő</span><strong><span id="balanceMaxMinutes">--</span> perc</strong></div>
            </div>
            <div id="balanceChargeCells" class="balance-grid" style="margin-top: 14px;"></div>
            <div class="commands" style="margin-top: 14px;">
              <button class="primary" onclick="startBalancing()">Balansz indítása</button>
              <button onclick="startServiceProcess('balance_to_highest_cell')">Balansz eredmény mentése</button>
              <button onclick="startServiceProcess('final_balancing')">Végső balansz mentése</button>
              <button class="stop" onclick="cmd('measurement_stop')">Mérés leállítása</button>
              <button class="stop" onclick="cmd('balancer_all_off')">Balancer OFF</button>
              <button class="danger" onclick="cmd('emergency_stop', true)">EMERGENCY STOP</button>
            </div>
            <div id="balancingLog" class="log"></div>
          </div>
        </section>
      </div>
    </div>

    <div id="tab-charge" class="tab-panel">
      <div class="grid">
        <section class="span-12">
          <div class="panel-head">
            <h2>Teljes töltés</h2>
            <span class="badge">PSU API később</span>
          </div>
          <div class="panel-body">
            <div class="form-grid">
              <div class="field">
                <label>Mérés típusa</label>
                <select id="chargeMeasurementStage">
                  <option value="Beérkezéskori mérés">Beérkezéskori mérés</option>
                  <option value="Javítás utáni mérés" selected>Javítás utáni mérés</option>
                  <option value="Merítés utáni mérés">Merítés utáni mérés</option>
                  <option value="Végső mérés">Végső mérés</option>
                  <option value="Köztes ellenőrző mérés">Köztes ellenőrző mérés</option>
                </select>
              </div>
              <div class="field"><label>Mért modul</label><select id="chargeModuleNo"></select><input id="chargeModuleCount" type="hidden" value="1"></div>
              <div class="field"><label>Cél pack feszültség</label><input id="chargePackTarget" type="number" step="0.1" value="360.0"></div>
              <div class="field"><label>Cél cellafeszültség</label><input id="chargeCellTarget" type="number" step="0.001" value="4.100"></div>
              <div class="field"><label>CC áramlimit</label><input id="chargeCurrentLimit" type="number" step="0.1" value="5.0"></div>
              <div class="field"><label>CV lezáró áram</label><input id="chargeEndCurrent" type="number" step="0.1" value="0.5"></div>
            </div>
            <div id="chargeModuleQuickSelect" class="commands" style="margin-top: 10px;"></div>
            <div id="chargeMeasurementNamePreview" class="log"></div>
            <div class="commands" style="margin-top: 14px;">
              <button class="primary" onclick="startCharging()">Töltés indítása</button>
              <button onclick="startServiceProcess('pack_charge')">Töltési eredmény mentése</button>
              <button class="stop" onclick="cmd('measurement_stop')">Mérés leállítása</button>
              <button class="stop" onclick="cmd('supply_output_off')">Supply OFF</button>
              <button class="danger" onclick="cmd('emergency_stop', true)">EMERGENCY STOP</button>
            </div>
            <div id="chargeLog" class="log"></div>
          </div>
        </section>
      </div>
    </div>

    <div id="tab-cycle" class="tab-panel">
      <div class="grid">
        <section class="span-12">
          <div class="panel-head">
            <h2>Teljes automata ciklus</h2>
            <span class="badge">MVP terv</span>
          </div>
          <div class="panel-body">
            <div class="form-grid">
              <div class="field"><label>Kisütés cella cél</label><input id="cycleDischargeCell" type="number" step="0.001" value="3.000"></div>
              <div class="field"><label>Töltés cella cél</label><input id="cycleChargeCell" type="number" step="0.001" value="4.100"></div>
              <div class="field"><label>Balansz delta cél</label><input id="cycleBalanceDelta" type="number" step="1" value="10"></div>
              <div class="field"><label>Jegyzőkönyv típus</label><select id="cycleReportType"><option>Szerviz jegyzőkönyv</option><option>Kapacitás mérés</option><option>Gyors állapotfelmérés</option></select></div>
            </div>
            <div class="workflow">
              <div class="step"><span>1</span><strong>Kiinduló ellenállás</strong><small>Cellánkénti belső ellenállás mentése.</small></div>
              <div class="step"><span>2</span><strong>Balansz célra</strong><small>Célfeszültségre vagy legmagasabb cellára.</small></div>
              <div class="step"><span>3</span><strong>Rövid merítés</strong><small>Leggyengébb cella és delta keresése.</small></div>
              <div class="step"><span>4</span><strong>Merítés utáni ellenállás</strong><small>Összehasonlítható ismételt mérés.</small></div>
              <div class="step"><span>5</span><strong>Pakk töltés</strong><small>Töltési energia és végállapot mentése.</small></div>
              <div class="step"><span>6</span><strong>Végső balansz</strong><small>Záró cellaszint és eredmény.</small></div>
              <div class="step"><span>7</span><strong>ERP összesítés</strong><small>Battery Measurement rekordok.</small></div>
              <div class="step"><span>8</span><strong>Diagramok</strong><small>PNG feltöltés későbbi bővítésben.</small></div>
            </div>
            <div class="commands" style="margin-top: 14px;">
              <button class="primary" onclick="startServiceProcess('full_post_repair_cycle')">Vezetett ciklus előkészítése</button>
              <button class="stop" onclick="cmd('measurement_stop')">Ciklus szünet / stop</button>
              <button class="danger" onclick="cmd('emergency_stop', true)">EMERGENCY STOP</button>
            </div>
            <div id="cycleLog" class="log"></div>
          </div>
        </section>
      </div>
    </div>

    <div id="tab-report" class="tab-panel">
      <div class="grid">
        <section class="span-12">
          <div class="panel-head">
            <h2>Jegyzőkönyv</h2>
            <span class="badge">Aktuális mérésből</span>
          </div>
          <div class="panel-body">
            <div class="form-grid">
              <div class="field"><label>Akkumulátor azonosító</label><input id="reportBatteryId" value="EV-BATT-001"></div>
              <div class="field"><label>Ügyfél / jármű</label><input id="reportVehicle" value="Teszt jármű"></div>
              <div class="field"><label>Technikus</label><input id="reportTechnician" value="ERP"></div>
              <div class="field"><label>Mérés típusa</label><select id="reportMode"><option>Teljes ciklus</option><option>Cella fesz mérés</option><option>Kisütés</option><option>Töltés</option></select></div>
              <div class="field"><label>ERP referencia</label><input id="reportErpReference" value=""></div>
              <div class="field"><label>Számlaszám</label><input id="reportInvoiceNumber" value=""></div>
              <div class="field"><label>Munkalap azonosító</label><input id="reportWorkOrderId" value=""></div>
            </div>
            <div class="commands" style="margin-top: 14px;">
              <button class="primary" onclick="createReport()">Jegyzőkönyv mentése / előnézet</button>
              <button onclick="downloadReportExport('json')">JSON letöltés</button>
              <button onclick="downloadReportExport('csv')">CSV letöltés</button>
              <button onclick="downloadReportExport('pdf')">PDF</button>
              <button onclick="downloadReportExport('docx')">DOCX</button>
            </div>
            <pre id="reportPreview">Nincs generált jegyzőkönyv.</pre>
          </div>
        </section>
      </div>
    </div>
  </main>

  <script>
    const systemStates = {
      0: 'BOOT',
      1: 'SELF TEST',
      2: 'IDLE',
      3: 'MEASURE',
      4: 'CHARGE',
      5: 'BALANCE',
      100: 'FAULT',
      101: 'EMERGENCY OFF'
    };

    const testTypeCodes = {
      'Nyugalmi mérés': 1,
      'Ellenállásmérés': 2,
      'Merítés': 3,
      'Töltés': 4,
      'Balanszírozás': 5,
      'Terheléses mérés': 6,
      'Teljes ciklus': 9
    };

    const measurementStageCodes = {
      'Beérkezéskori mérés': 1,
      'Javítás utáni mérés': 2,
      'Merítés utáni mérés': 3,
      'Végső mérés': 4,
      'Köztes ellenőrző mérés': 5
    };

    let latestStatus = null;
    let latestReport = null;
    let erpnextJobs = [];
    let selectedErpNextJob = null;

    const el = (id) => document.getElementById(id);
    const fmt = (value, digits = 1) => value === null || value === undefined ? '--' : Number(value).toFixed(digits);
    const text = (id, value) => {
      const target = el(id);
      if (target) {
        target.textContent = value;
      }
    };

    async function apiFetch(url, options = {}) {
      const headers = new Headers(options.headers ?? {});
      const token = localStorage.getItem('gatewayApiToken');
      if (token && !headers.has('Authorization')) {
        headers.set('Authorization', `Bearer ${token}`);
      }
      let response = await fetch(url, {...options, headers});
      if (response.status !== 401) {
        return response;
      }
      const newToken = prompt('Gateway API token');
      if (!newToken) {
        return response;
      }
      localStorage.setItem('gatewayApiToken', newToken);
      headers.set('Authorization', `Bearer ${newToken}`);
      return fetch(url, {...options, headers});
    }

    function apiErrorText(data, fallback) {
      const detail = data?.detail;
      const message = detail?.message ?? (typeof detail === 'string' ? detail : fallback);
      const erpMessage = detail?.erpnext_detail?._error_message;
      return erpMessage ? `${message}: ${erpMessage}` : message;
    }

    function erpNextErrorText(error) {
      if (!error) {
        return '';
      }
      const detail = error.detail ?? {};
      const erpDetail = detail.erpnext_detail ?? detail;
      const message = erpDetail._error_message ?? erpDetail.exception ?? error.message ?? 'ERPNext hiba';
      return `ERP hiba: ${message}`;
    }

    function showTab(name) {
      document.querySelectorAll('.tab-panel').forEach((panel) => panel.classList.remove('active'));
      document.querySelectorAll('.tab-button').forEach((button) => button.classList.remove('active'));
      el(`tab-${name}`).classList.add('active');
      document.querySelector(`[data-tab="${name}"]`).classList.add('active');
    }

    const ws = new WebSocket(`ws://${location.host}/ws/status`);

    ws.onmessage = (event) => {
      latestStatus = JSON.parse(event.data);
      render(latestStatus);
    };

    ws.onopen = () => {
      text('commandLog', '');
    };

    ws.onclose = () => {
      const dot = el('connDot');
      dot.className = 'dot bad';
      text('connText', 'WebSocket bontva');
    };

    function render(status) {
      const connected = Boolean(status.connected);
      const dot = el('connDot');
      dot.className = `dot ${connected ? 'ok' : 'bad'}`;
      text('connText', connected ? 'CAN kapcsolat aktív' : 'CAN kapcsolat nincs');
      text('lastRx', status.last_can_rx_ms ? `CAN RX: ${new Date(status.last_can_rx_ms).toLocaleTimeString()}` : 'CAN RX: nincs adat');

      text('packVoltage', fmt(status.pack_voltage_v, 1));
      text('current', fmt(status.current_a, 2));
      text('power', fmt(status.power_w, 0));
      text('validText', `Mérés: ${status.measurement_valid ? 'érvényes' : 'nem érvényes'}`);
      const visibleCells = getVisibleCells(status.cell_voltages_mv ?? []);
      const visibleStats = getCellStats(visibleCells);
      text('cellDelta', visibleStats.delta ?? '--');
      text('cellMinMax', visibleStats.min && visibleStats.max ? `${visibleStats.min} / ${visibleStats.max} mV` : '--');
      text('systemState', systemStates[status.system_state] ?? status.system_state ?? '--');
      text('uptime', status.uptime_s ?? '--');

      text('relayFlags', status.relay_flags ?? '--');
      text('supplyFlags', status.supply_flags ?? '--');
      text('balancerFlags', status.balancer_flags ?? '--');
      text('activeProfile', status.active_profile ?? '--');
      text('faultCode', status.fault_code ?? '--');
      text('faultSeverity', status.fault_severity ?? '--');
      text('canError', status.can_error ?? '');
      el('rawStatus').textContent = JSON.stringify(status, null, 2);

      const faultActive = status.fault_state || status.fault_code !== null;
      const faultBadge = el('faultBadge');
      faultBadge.className = `badge ${faultActive ? 'bad' : 'ok'}`;
      faultBadge.textContent = faultActive ? 'Fault aktív' : 'Nincs fault';

      renderCells(status.cell_voltages_mv ?? []);
      renderResistances(status.cell_resistances_mohm ?? []);
      renderResistanceRunState(status);
      renderWorkflowMirrors(status);
      renderModuleSelect('cell');
      renderModuleSelect('resistance');
      renderModuleSelect('discharge');
      renderModuleSelect('balancing');
      renderModuleSelect('charge');
      renderCellMeasurementNamePreview();
      renderResistanceMeasurementNamePreview();
      renderDischargeMeasurementNamePreview();
      renderBalancingMeasurementNamePreview();
      renderChargeMeasurementNamePreview();
      renderBalancingScope(status);
      renderBalancingChargePreview(status);
      renderDischargeMeasurementNamePreview();
    }

    function getDisplayCellCount(total) {
      const input = el('cellTargetCount');
      const requested = Number(input?.value ?? total);
      if (!Number.isFinite(requested) || requested < 1) {
        return total;
      }
      return Math.min(Math.floor(requested), total);
    }

    function getVisibleCells(cells) {
      return cells.slice(0, getDisplayCellCount(cells.length));
    }

    function getCellStats(cells) {
      const valid = cells.filter((value) => value !== null && value !== undefined && value > 0);
      if (!valid.length) {
        return {min: null, max: null, delta: null};
      }
      const min = Math.min(...valid);
      const max = Math.max(...valid);
      return {min, max, delta: max - min};
    }

    function renderCells(cells) {
      const visibleCells = getVisibleCells(cells);
      const stats = getCellStats(visibleCells);
      const label = `${visibleCells.length} / ${cells.length} cella`;
      text('cellCount', label);
      text('cellCountMirror', label);
      const warnLowMv = Number(el('cellWarnLow')?.value ?? 0) * 1000;
      const warnHighMv = Number(el('cellWarnHigh')?.value ?? 999) * 1000;
      const maxDeltaMv = Number(el('cellMaxDelta')?.value ?? 0);
      const outOfRange = visibleCells.filter((value) => value !== null && value !== undefined && value > 0 && (value < warnLowMv || value > warnHighMv)).length;
      const markup = visibleCells.map((value, index) => {
        const isBad = value !== null && value !== undefined && value > 0 && (value < warnLowMv || value > warnHighMv);
        const state = isBad ? 'bad' : (value === stats.min ? 'low' : value === stats.max ? 'high' : '');
        return `<div class="cell ${state}"><small>C${index + 1}</small><strong>${value ?? '--'} mV</strong></div>`;
      }).join('');
      el('cells').innerHTML = markup;
      el('cellsMirror').innerHTML = markup;
      const warnings = [];
      if (outOfRange) {
        warnings.push(`${outOfRange} cella figyelmeztetési határon kívül`);
      }
      if (stats.delta !== null && maxDeltaMv > 0 && stats.delta > maxDeltaMv) {
        warnings.push(`Delta figyelmeztetés: ${stats.delta} mV > ${maxDeltaMv} mV`);
      }
      text('cellVoltageWarningLog', warnings.length ? warnings.join('. ') : 'Kék: legalacsonyabb cella, sárga: legmagasabb cella, piros: figyelmeztetési határon kívül.');
      renderCellSelect(visibleCells.length);
    }

    function renderCellSelect(count) {
      const select = el('singleCellSelect');
      if (!select) {
        return;
      }
      const currentCount = select.options.length;
      if (currentCount === count) {
        return;
      }
      select.innerHTML = Array.from({length: count || 1}, (_, index) => `<option value="${index}">C${index + 1}</option>`).join('');
    }

    function renderBalancingScope(status) {
      const scope = el('balanceScope');
      if (!scope) {
        return;
      }
      const cellCount = status?.cell_voltages_mv?.length || Number(el('cellTargetCount')?.value ?? 18) || 18;
      scope.value = `Kiválasztott modul teljes cellakészlete (${cellCount} cella)`;
    }

    function renderBalancingChargePreview(status) {
      const target = el('balanceChargeCells');
      if (!target) {
        return;
      }
      const cells = status?.cell_voltages_mv ?? [];
      const targetVoltage = Number(el('singleCellTarget')?.value ?? 0);
      const currentLimit = Math.abs(Number(el('singleCellCurrent')?.value ?? 0.5)) || 0.5;
      if (!cells.length || !Number.isFinite(targetVoltage) || targetVoltage <= 0) {
        target.innerHTML = '';
        text('balanceTotalAh', '--');
        text('balanceTotalWh', '--');
        text('balanceMaxCell', '--');
        text('balanceMaxMinutes', '--');
        return;
      }
      const rows = cells.map((mv, index) => {
        const startVoltage = mv === null || mv === undefined ? null : Number(mv) / 1000;
        if (!startVoltage || startVoltage <= 0) {
          return {
            cellNo: index + 1,
            startVoltage: null,
            voltageChangeMv: 0,
            minutes: 0,
            chargedAh: 0,
            chargedWh: 0
          };
        }
        const endVoltage = Math.max(startVoltage, targetVoltage);
        const voltageChangeMv = Math.max(0, (endVoltage - startVoltage) * 1000);
        const minutes = Math.max(0, voltageChangeMv / 5);
        const chargedAh = currentLimit * (minutes / 60);
        const chargedWh = chargedAh * ((startVoltage + endVoltage) / 2);
        return {
          cellNo: index + 1,
          startVoltage,
          voltageChangeMv,
          minutes,
          chargedAh,
          chargedWh
        };
      });
      const totalAh = rows.reduce((sum, row) => sum + row.chargedAh, 0);
      const totalWh = rows.reduce((sum, row) => sum + row.chargedWh, 0);
      const maxRow = rows.reduce((best, row) => row.chargedAh > best.chargedAh ? row : best, rows[0]);
      const maxAh = Math.max(...rows.map((row) => row.chargedAh), 0);
      text('balanceTotalAh', totalAh.toFixed(4));
      text('balanceTotalWh', totalWh.toFixed(3));
      text('balanceMaxCell', maxRow && maxRow.chargedAh > 0 ? `C${maxRow.cellNo} - ${maxRow.chargedAh.toFixed(4)} Ah` : 'nincs töltési igény');
      text('balanceMaxMinutes', maxRow ? maxRow.minutes.toFixed(1) : '--');
      target.innerHTML = rows.map((row) => {
        const width = maxAh > 0 ? Math.round((row.chargedAh / maxAh) * 100) : 0;
        const active = row.chargedAh > 0 ? 'active' : '';
        const voltage = row.startVoltage === null ? '--' : `${row.startVoltage.toFixed(3)} V`;
        return `<div class="balance-cell ${active}">
          <small>C${row.cellNo} - ${voltage}</small>
          <strong>${row.chargedAh.toFixed(4)} Ah</strong>
          <span>${row.chargedWh.toFixed(3)} Wh</span>
          <span>${row.voltageChangeMv.toFixed(0)} mV / ${row.minutes.toFixed(1)} perc</span>
          <div class="charge-bar"><i style="width: ${width}%"></i></div>
        </div>`;
      }).join('');
    }

    function renderModuleSelect(prefix = 'cell') {
      const select = el(`${prefix}ModuleNo`);
      if (!select) {
        return;
      }
      const currentValue = select.value || '1';
      const requested = Number(el(`${prefix}ModuleCount`)?.value ?? 1);
      const count = Number.isFinite(requested) && requested > 0 ? Math.min(Math.floor(requested), 40) : 1;
      if (select.options.length !== count) {
        select.innerHTML = Array.from({length: count}, (_, index) => {
          const moduleNo = index + 1;
          return `<option value="${moduleNo}">MOD${String(moduleNo).padStart(2, '0')} - ${moduleNo}. modul</option>`;
        }).join('');
        select.value = Number(currentValue) <= count ? currentValue : '1';
      }
      renderModuleQuickSelect(prefix, count);
      renderMeasurementNamePreview(prefix);
    }

    function renderModuleQuickSelect(prefix, count) {
      const container = el(`${prefix}ModuleQuickSelect`);
      if (!container) {
        return;
      }
      container.innerHTML = Array.from({length: count}, (_, index) => {
        const moduleNo = index + 1;
        return `<button type="button" onclick="selectMeasuredModule('${prefix}', ${moduleNo})">MOD${String(moduleNo).padStart(2, '0')}</button>`;
      }).join('');
    }

    function selectMeasuredModule(prefix, moduleNo) {
      const select = el(`${prefix}ModuleNo`);
      if (!select) {
        return;
      }
      select.value = String(moduleNo);
      renderMeasurementNamePreview(prefix);
      if (latestStatus) {
        render(latestStatus);
      }
    }

    function selectedMeasurementStage(prefix = 'cell') {
      return el(`${prefix}MeasurementStage`)?.value ?? null;
    }

    function measurementStageForProcess(processKey, prefix = null) {
      const selectedStage = prefix ? selectedMeasurementStage(prefix) : null;
      if (selectedStage) {
        return selectedStage;
      }
      const stages = {
        incoming_resistance: 'Beérkezéskori mérés',
        module_cell_resistance: 'Javítás utáni mérés',
        post_discharge_resistance: 'Merítés utáni mérés',
        short_discharge_test: 'Javítás utáni mérés',
        balance_to_highest_cell: 'Javítás utáni mérés',
        final_balancing: 'Végső mérés',
        pack_charge: 'Javítás utáni mérés',
        cell_voltage_measurement: el('cellMeasurementStage')?.value ?? 'Beérkezéskori mérés'
      };
      return stages[processKey] ?? (el('cellMeasurementStage')?.value ?? 'Beérkezéskori mérés');
    }

    function measurementNamePreview(prefix = 'cell', processKey = null) {
      const repairJob = selectedErpNextJob?.name || el('reportWorkOrderId')?.value || 'MUNKALAP';
      const moduleNo = Number(el(`${prefix}ModuleNo`)?.value ?? 1);
      const defaultStage = prefix === 'resistance' ? 'Beérkezéskori mérés' : (prefix === 'balancing' ? 'Javítás utáni mérés' : (prefix === 'charge' ? 'Javítás utáni mérés' : (el('cellMeasurementStage')?.value ?? 'Beérkezéskori mérés')));
      const stage = processKey ? measurementStageForProcess(processKey, prefix) : (selectedMeasurementStage(prefix) ?? defaultStage);
      const testType = prefix === 'resistance' ? 'Ellenállásmérés' : (prefix === 'discharge' ? 'Merítés' : (prefix === 'balancing' ? 'Balanszírozás' : (prefix === 'charge' ? 'Töltés' : 'Nyugalmi mérés')));
      const testCode = testTypeCodes[testType] ?? 99;
      const stageCode = measurementStageCodes[stage] ?? 99;
      return `${repairJob}-MOD${String(moduleNo || 1).padStart(2, '0')}-M${String(testCode).padStart(2, '0')}-${String(stageCode).padStart(2, '0')}`;
    }

    function renderMeasurementNamePreview(prefix = 'cell') {
      const target = prefix === 'resistance' ? 'resistanceMeasurementNamePreview' : (prefix === 'discharge' ? 'dischargeMeasurementNamePreview' : (prefix === 'balancing' ? 'balancingMeasurementNamePreview' : (prefix === 'charge' ? 'chargeMeasurementNamePreview' : 'cellMeasurementNamePreview')));
      text(target, `ERP mérés neve: ${measurementNamePreview(prefix)}`);
    }

    function renderCellMeasurementNamePreview() {
      renderMeasurementNamePreview('cell');
    }

    function renderResistanceMeasurementNamePreview() {
      renderMeasurementNamePreview('resistance');
    }

    function renderDischargeMeasurementNamePreview() {
      renderMeasurementNamePreview('discharge');
    }

    function renderBalancingMeasurementNamePreview() {
      renderMeasurementNamePreview('balancing');
    }

    function renderChargeMeasurementNamePreview() {
      renderMeasurementNamePreview('charge');
    }

    function getResistanceDisplayCount(total) {
      const input = el('resistanceCellCount');
      const requested = Number(input?.value ?? total);
      if (!Number.isFinite(requested) || requested < 1) {
        return total;
      }
      return Math.min(Math.floor(requested), total);
    }

    function renderResistances(values) {
      const visible = values.slice(0, getResistanceDisplayCount(values.length));
      const valid = visible.filter((value) => value !== null && value !== undefined && value > 0);
      const maxValue = valid.length ? Math.max(...valid) : null;
      text('resistanceCount', `${visible.length} / ${values.length} cella`);
      text('maxResistance', maxValue === null ? '--' : maxValue.toFixed(2));
      text('resistanceCurrent', latestStatus ? fmt(latestStatus.current_a, 2) : '--');
      el('resistanceCells').innerHTML = visible.map((value, index) => {
        const state = value === maxValue ? 'high' : '';
        const shown = value === null || value === undefined ? '--' : Number(value).toFixed(2);
        return `<div class="cell ${state}"><small>C${index + 1}</small><strong>${shown} mOhm</strong></div>`;
      }).join('');
    }

    function renderResistanceRunState(status) {
      const badge = el('resistanceStatus');
      if (!badge) {
        return;
      }
      if (status.resistance_measurement_running) {
        badge.className = 'badge ok';
        badge.textContent = 'Mérés fut';
      } else if ((status.cell_resistances_mohm ?? []).length) {
        badge.className = 'badge';
        badge.textContent = 'Utolsó eredmény';
      } else {
        badge.className = 'badge';
        badge.textContent = 'Készenlét';
      }
    }

    function renderWorkflowMirrors(status) {
      const stats = getCellStats(getVisibleCells(status.cell_voltages_mv ?? []));
      text('dischargePack', fmt(status.pack_voltage_v, 1));
      text('dischargeCurrent', fmt(status.current_a, 2));
      text('dischargeMinCell', stats.min ?? '--');
      text('dischargeDelta', stats.delta ?? '--');
    }

    async function cmd(command, requireConfirm = false) {
      if (requireConfirm && !confirm(`${command} parancs küldése?`)) {
        return;
      }
      const state = el('commandState');
      state.className = 'badge';
      state.textContent = 'Küldés...';
      try {
        const response = await fetch('/api/command', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({command})
        });
        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail ?? response.statusText);
        }
        state.className = 'badge ok';
        state.textContent = 'Elküldve';
        text('commandLog', `${new Date().toLocaleTimeString()} - ${command}`);
      } catch (error) {
        state.className = 'badge bad';
        state.textContent = 'Hiba';
        text('commandLog', error.message);
      }
    };

    async function startResistanceMeasurement() {
      const loadLevel = Number(el('resistanceLoadLevel').value);
      if (!confirm('Belső ellenállás mérés indítása a kiválasztott terheléssel?')) {
        return;
      }
      const badge = el('resistanceStatus');
      badge.className = 'badge';
      badge.textContent = 'Indítás...';
      try {
        const response = await fetch('/api/command', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({command: 'internal_resistance_start', value: loadLevel})
        });
        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail ?? response.statusText);
        }
        badge.className = 'badge ok';
        badge.textContent = 'Mérés indítva';
        text('resistanceLog', `${new Date().toLocaleTimeString()} - terhelési szint: ${loadLevel}`);
      } catch (error) {
        badge.className = 'badge bad';
        badge.textContent = 'Hiba';
        text('resistanceLog', error.message);
      }
    }

    async function startBalancing() {
      const moduleNo = Number(el('balancingModuleNo')?.value ?? 1);
      const cellCount = latestStatus?.cell_voltages_mv?.length || Number(el('cellTargetCount')?.value ?? 18) || 18;
      const targetVoltage = Number(el('singleCellTarget')?.value ?? 4.1);
      const currentLimit = Number(el('singleCellCurrent')?.value ?? 0.5);
      const moduleLabel = `MOD${String(moduleNo).padStart(2, '0')}`;
      if (!confirm(`Balansz indítása: ${moduleLabel} teljes modul, ${cellCount} cella, cél ${targetVoltage.toFixed(3)} V?`)) {
        return;
      }
      text('balancingLog', `Balansz indítása...\\n${moduleLabel} teljes modul\\nTartomány: ${cellCount} cella\\nCélfeszültség: ${targetVoltage.toFixed(3)} V\\nPanel áramlimit: ${currentLimit.toFixed(2)} A`);
      try {
        const response = await fetch('/api/command', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({command: 'measurement_start'})
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail ?? response.statusText);
        }
        text('balancingLog', `Balansz indítva.\\n${moduleLabel} teljes modul\\nTartomány: ${cellCount} cella\\nCélfeszültség: ${targetVoltage.toFixed(3)} V\\nPanel áramlimit: ${currentLimit.toFixed(2)} A\\nMegjegyzés: jelenleg általános measurement_start CAN parancs megy ki; a balansz panel kezeli a 9 csatornát és a reléváltást.`);
      } catch (error) {
        text('balancingLog', error.message);
      }
    }

    async function startCharging() {
      const moduleNo = Number(el('chargeModuleNo')?.value ?? 1);
      const targetPackVoltage = Number(el('chargePackTarget')?.value ?? 360);
      const targetCellVoltage = Number(el('chargeCellTarget')?.value ?? 4.1);
      const currentLimit = Number(el('chargeCurrentLimit')?.value ?? 5);
      const moduleLabel = `MOD${String(moduleNo).padStart(2, '0')}`;
      if (!confirm(`Töltés indítása: ${moduleLabel}, pack cél ${targetPackVoltage.toFixed(1)} V, cella cél ${targetCellVoltage.toFixed(3)} V?`)) {
        return;
      }
      text('chargeLog', `Töltés indítása...\\n${moduleLabel}\\nPack cél: ${targetPackVoltage.toFixed(1)} V\\nCella cél: ${targetCellVoltage.toFixed(3)} V\\nCC áramlimit: ${currentLimit.toFixed(1)} A`);
      try {
        const response = await fetch('/api/command', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({command: 'measurement_start'})
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail ?? response.statusText);
        }
        text('chargeLog', `Töltés indítva.\\n${moduleLabel}\\nPack cél: ${targetPackVoltage.toFixed(1)} V\\nCella cél: ${targetCellVoltage.toFixed(3)} V\\nCC áramlimit: ${currentLimit.toFixed(1)} A\\nMegjegyzés: jelenleg általános measurement_start CAN parancs megy ki; a külön PSU/töltő parancs később köthető be.`);
      } catch (error) {
        text('chargeLog', error.message);
      }
    }

    async function checkErpNextHealth() {
      const badge = el('erpnextStatus');
      badge.className = 'badge';
      badge.textContent = 'Ellenőrzés...';
      const response = await apiFetch('/api/erpnext/health');
      const data = await response.json();
      if (!response.ok) {
        badge.className = 'badge bad';
        badge.textContent = 'ERP hiba';
        text('erpnextLog', apiErrorText(data, response.statusText));
        return;
      }
      badge.className = 'badge ok';
      badge.textContent = 'ERP kapcsolat OK';
      text('erpnextLog', `Elérhető ERP DocType: ${data.checked_doctype}`);
    }

    async function loadErpNextJobs() {
      text('cellVoltageLog', 'ERPNext munkalapok betöltése...');
      text('resistanceLog', 'ERPNext munkalapok betöltése...');
      text('balancingLog', 'ERPNext munkalapok betöltése...');
      const response = await apiFetch('/api/erpnext/repair-jobs');
      const data = await response.json();
      if (!response.ok) {
        el('erpnextStatus').className = 'badge bad';
        text('erpnextLog', apiErrorText(data, response.statusText));
        text('cellVoltageLog', apiErrorText(data, response.statusText));
        text('resistanceLog', apiErrorText(data, response.statusText));
        text('dischargeLog', apiErrorText(data, response.statusText));
        text('balancingLog', apiErrorText(data, response.statusText));
        text('chargeLog', apiErrorText(data, response.statusText));
        return;
      }
      erpnextJobs = data;
      const select = el('erpnextJobSelect');
      select.innerHTML = erpnextJobs.map((job, index) => {
        const vehicle = [job.license_plate, job.vehicle_make, job.vehicle_model].filter(Boolean).join(' ');
        return `<option value="${index}">${job.name} - ${vehicle || job.job_status || 'munkalap'}</option>`;
      }).join('');
      syncCellJobSelect();
      syncResistanceJobSelect();
      syncDischargeJobSelect();
      syncBalancingJobSelect();
      syncChargeJobSelect();
      text('erpnextLog', `${erpnextJobs.length} nyitott munkalap betöltve`);
      text('cellVoltageLog', `${erpnextJobs.length} nyitott munkalap betöltve. ERP modul szám: ${erpnextJobs[0]?.module_count ?? '--'}`);
      text('resistanceLog', `${erpnextJobs.length} nyitott munkalap betöltve. ERP modul szám: ${erpnextJobs[0]?.module_count ?? '--'}`);
      text('dischargeLog', `${erpnextJobs.length} nyitott munkalap betöltve. ERP modul szám: ${erpnextJobs[0]?.module_count ?? '--'}`);
      text('balancingLog', `${erpnextJobs.length} nyitott munkalap betöltve. ERP modul szám: ${erpnextJobs[0]?.module_count ?? '--'}`);
      text('chargeLog', `${erpnextJobs.length} nyitott munkalap betöltve. ERP modul szám: ${erpnextJobs[0]?.module_count ?? '--'}`);
      selectErpNextJob();
    }

    function selectErpNextJob() {
      const index = Number(el('erpnextJobSelect').value);
      selectedErpNextJob = erpnextJobs[index] ?? null;
      const job = selectedErpNextJob;
      text('erpnextJobName', job?.name ?? '--');
      text('erpnextLicensePlate', job?.license_plate ?? '--');
      text('erpnextVehicle', job ? [job.vehicle_make, job.vehicle_model, job.vehicle_year].filter(Boolean).join(' ') || '--' : '--');
      text('erpnextCustomer', job?.customer ?? '--');
      text('erpnextPreDone', job?.pre_measurement_done ? 'kész' : 'nincs');
      text('erpnextPostDone', job?.post_measurement_done ? 'kész' : 'nincs');
      text('erpnextJobStatus', job?.job_status ?? 'Nincs kiválasztva');
      const cellSelect = el('cellErpJobSelect');
      if (cellSelect && cellSelect.value !== String(index) && erpnextJobs[index]) {
        cellSelect.value = String(index);
      }
      const resistanceSelect = el('resistanceErpJobSelect');
      if (resistanceSelect && resistanceSelect.value !== String(index) && erpnextJobs[index]) {
        resistanceSelect.value = String(index);
      }
      const dischargeSelect = el('dischargeErpJobSelect');
      if (dischargeSelect && dischargeSelect.value !== String(index) && erpnextJobs[index]) {
        dischargeSelect.value = String(index);
      }
      const balancingSelect = el('balancingErpJobSelect');
      if (balancingSelect && balancingSelect.value !== String(index) && erpnextJobs[index]) {
        balancingSelect.value = String(index);
      }
      const chargeSelect = el('chargeErpJobSelect');
      if (chargeSelect && chargeSelect.value !== String(index) && erpnextJobs[index]) {
        chargeSelect.value = String(index);
      }
      if (job) {
        el('reportWorkOrderId').value = job.name;
        el('reportErpReference').value = job.name;
        el('reportVehicle').value = [job.license_plate, job.vehicle_make, job.vehicle_model].filter(Boolean).join(' ');
        if (job.cell_count) {
          el('cellTargetCount').value = job.cell_count;
          el('resistanceCellCount').value = job.cell_count;
        }
        if (job.module_count) {
          el('cellModuleCount').value = job.module_count;
          el('resistanceModuleCount').value = job.module_count;
          el('dischargeModuleCount').value = job.module_count;
          el('balancingModuleCount').value = job.module_count;
          el('chargeModuleCount').value = job.module_count;
        }
        applyErpModuleCountLock(job);
        renderModuleSelect('cell');
        renderModuleSelect('resistance');
        renderModuleSelect('discharge');
        renderModuleSelect('balancing');
        renderModuleSelect('charge');
        if (latestStatus) {
          render(latestStatus);
        }
      } else {
        applyErpModuleCountLock(null);
      }
      renderCellMeasurementNamePreview();
      renderResistanceMeasurementNamePreview();
      renderDischargeMeasurementNamePreview();
      renderBalancingMeasurementNamePreview();
      renderChargeMeasurementNamePreview();
    }

    function applyErpModuleCountLock(job) {
      const hasErpModuleCount = Boolean(job?.module_count);
      ['cellModuleCount', 'resistanceModuleCount', 'dischargeModuleCount', 'balancingModuleCount', 'chargeModuleCount'].forEach((id) => {
        const input = el(id);
        if (!input) {
          return;
        }
        input.readOnly = hasErpModuleCount;
        input.classList.toggle('readonly', hasErpModuleCount);
        input.title = hasErpModuleCount ? 'ERPNext munkalapból jön, itt nem módosítható.' : '';
      });
    }

    function syncCellJobSelect() {
      const select = el('cellErpJobSelect');
      if (!select) {
        return;
      }
      select.innerHTML = erpnextJobs.map((job, index) => {
        const vehicle = [job.license_plate, job.vehicle_make, job.vehicle_model].filter(Boolean).join(' ');
        return `<option value="${index}">${job.name} - ${vehicle || job.job_status || 'munkalap'}</option>`;
      }).join('');
    }

    function syncResistanceJobSelect() {
      const select = el('resistanceErpJobSelect');
      if (!select) {
        return;
      }
      select.innerHTML = erpnextJobs.map((job, index) => {
        const vehicle = [job.license_plate, job.vehicle_make, job.vehicle_model].filter(Boolean).join(' ');
        return `<option value="${index}">${job.name} - ${vehicle || job.job_status || 'munkalap'}</option>`;
      }).join('');
    }

    function syncDischargeJobSelect() {
      const select = el('dischargeErpJobSelect');
      if (!select) {
        return;
      }
      select.innerHTML = erpnextJobs.map((job, index) => {
        const vehicle = [job.license_plate, job.vehicle_make, job.vehicle_model].filter(Boolean).join(' ');
        return `<option value="${index}">${job.name} - ${vehicle || job.job_status || 'munkalap'}</option>`;
      }).join('');
    }

    function syncBalancingJobSelect() {
      const select = el('balancingErpJobSelect');
      if (!select) {
        return;
      }
      select.innerHTML = erpnextJobs.map((job, index) => {
        const vehicle = [job.license_plate, job.vehicle_make, job.vehicle_model].filter(Boolean).join(' ');
        return `<option value="${index}">${job.name} - ${vehicle || job.job_status || 'munkalap'}</option>`;
      }).join('');
    }

    function syncChargeJobSelect() {
      const select = el('chargeErpJobSelect');
      if (!select) {
        return;
      }
      select.innerHTML = erpnextJobs.map((job, index) => {
        const vehicle = [job.license_plate, job.vehicle_make, job.vehicle_model].filter(Boolean).join(' ');
        return `<option value="${index}">${job.name} - ${vehicle || job.job_status || 'munkalap'}</option>`;
      }).join('');
    }

    function selectCellErpJob() {
      const cellSelect = el('cellErpJobSelect');
      const mainSelect = el('erpnextJobSelect');
      if (!cellSelect || !mainSelect) {
        return;
      }
      mainSelect.value = cellSelect.value;
      selectErpNextJob();
    }

    function selectResistanceErpJob() {
      const resistanceSelect = el('resistanceErpJobSelect');
      const mainSelect = el('erpnextJobSelect');
      if (!resistanceSelect || !mainSelect) {
        return;
      }
      mainSelect.value = resistanceSelect.value;
      selectErpNextJob();
    }

    function selectDischargeErpJob() {
      const dischargeSelect = el('dischargeErpJobSelect');
      const mainSelect = el('erpnextJobSelect');
      if (!dischargeSelect || !mainSelect) {
        return;
      }
      mainSelect.value = dischargeSelect.value;
      selectErpNextJob();
    }

    function selectBalancingErpJob() {
      const balancingSelect = el('balancingErpJobSelect');
      const mainSelect = el('erpnextJobSelect');
      if (!balancingSelect || !mainSelect) {
        return;
      }
      mainSelect.value = balancingSelect.value;
      selectErpNextJob();
    }

    function selectChargeErpJob() {
      const chargeSelect = el('chargeErpJobSelect');
      const mainSelect = el('erpnextJobSelect');
      if (!chargeSelect || !mainSelect) {
        return;
      }
      mainSelect.value = chargeSelect.value;
      selectErpNextJob();
    }

    function suggestCellConfigFromCan() {
      const count = latestStatus?.cell_voltages_mv?.length ?? 0;
      if (!count) {
        text('cellVoltageLog', 'Nincs CAN cellafeszültség adat, nem tudok javaslatot adni.');
        return;
      }
      el('cellTargetCount').value = count;
      if (!Number(el('cellModuleCount')?.value)) {
        el('cellModuleCount').value = 1;
      }
      renderModuleSelect('cell');
      renderModuleSelect('resistance');
      renderModuleSelect('discharge');
      renderModuleSelect('balancing');
      render(latestStatus);
      text('cellVoltageLog', `CAN alapján javasolt teljes cellaszám: ${count}.`);
    }

    async function writeErpNextMeasurementStatus() {
      if (!selectedErpNextJob) {
        text('erpnextLog', 'Nincs kiválasztott munkalap.');
        return;
      }
      const measurementType = el('erpnextMeasurementType').value;
      const measurementId = latestReport?.measurement_id ?? `MEAS-${new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 14)}`;
      const response = await apiFetch(`/api/erpnext/repair-jobs/${encodeURIComponent(selectedErpNextJob.name)}/measurement-status`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          measurement_type: measurementType,
          measurement_id: measurementId,
          measurement_datetime: new Date().toISOString(),
          status: 'done'
        })
      });
      const data = await response.json();
      if (!response.ok) {
        text('erpnextLog', apiErrorText(data, response.statusText));
        return;
      }
      text('erpnextLog', `${selectedErpNextJob.name}: ${measurementType === 'pre' ? 'javítás előtti' : 'javítás utáni'} mérés kész visszaírva`);
      await loadErpNextJobs();
    }

    async function startServiceProcess(processKey, overwriteExisting = false) {
      const repairJob = selectedErpNextJob?.name || el('reportWorkOrderId')?.value || '';
      if (!repairJob && !confirm('Nincs ERPNext munkalap kiválasztva. Csak lokális mérésmentés készüljön?')) {
        return;
      }
      const logTargets = {
        cell_voltage_measurement: 'cellVoltageLog',
        incoming_resistance: 'resistanceLog',
        module_cell_resistance: 'resistanceLog',
        post_discharge_resistance: 'resistanceLog',
        short_discharge_test: 'dischargeLog',
        balance_to_highest_cell: 'balancingLog',
        final_balancing: 'balancingLog',
        pack_charge: 'chargeLog',
        full_post_repair_cycle: 'cycleLog'
      };
      const logId = logTargets[processKey] ?? 'commandLog';
      const isResistanceProcess = ['incoming_resistance', 'module_cell_resistance', 'post_discharge_resistance'].includes(processKey);
      const isDischargeProcess = processKey === 'short_discharge_test';
      const isBalancingProcess = ['balance_to_highest_cell', 'final_balancing'].includes(processKey);
      const isChargeProcess = processKey === 'pack_charge';
      const modulePrefix = isResistanceProcess ? 'resistance' : (isDischargeProcess ? 'discharge' : (isBalancingProcess ? 'balancing' : (isChargeProcess ? 'charge' : 'cell')));
      const processCellCount = processKey === 'cell_voltage_measurement'
        ? el('cellTargetCount')?.value
        : (isResistanceProcess ? (el('resistanceCellCount')?.value ?? el('cellTargetCount')?.value ?? 18) : (latestStatus?.cell_voltages_mv?.length ?? el('cellTargetCount')?.value ?? 18));
      const payload = {
        process_key: processKey,
        repair_job: repairJob || null,
        measurement_stage: measurementStageForProcess(processKey, modulePrefix),
        load_level: Number(el('resistanceLoadLevel')?.value ?? 2),
        cell_count: Number(processCellCount),
        module_no: Number(el(`${modulePrefix}ModuleNo`)?.value ?? 1),
        module_count: Number(el(`${modulePrefix}ModuleCount`)?.value ?? 1),
        voltage_warn_low: Number(el('cellWarnLow')?.value ?? 3),
        voltage_warn_high: Number(el('cellWarnHigh')?.value ?? 4.2),
        max_delta_mv: Number(el('cellMaxDelta')?.value ?? 20),
        target_cell_voltage: Number(isDischargeProcess ? (el('dischargeCellTarget')?.value ?? 3.0) : (isBalancingProcess ? (el('singleCellTarget')?.value ?? 4.1) : (el('cycleChargeCell')?.value ?? el('chargeCellTarget')?.value ?? el('singleCellTarget')?.value ?? 4.1))),
        target_pack_voltage: Number(isDischargeProcess ? (el('dischargePackTarget')?.value ?? 300) : (el('chargePackTarget')?.value ?? 360)),
        discharge_current_a: Number(el('dischargeCurrentLimit')?.value ?? 10),
        charge_current_a: Number(el('chargeCurrentLimit')?.value ?? 5),
        balance_delta_mv: Number(el('cycleBalanceDelta')?.value ?? el('balanceDeltaTarget')?.value ?? 10),
        overwrite_existing: overwriteExisting,
        auto_upload: Boolean(repairJob)
      };
      text(logId, `Folyamat indítása...\\nMért modul: MOD${String(payload.module_no || 1).padStart(2, '0')}\\nÖsszes modul: ${payload.module_count}\\nVárt ERP név: ${measurementNamePreview(modulePrefix, processKey)}`);
      const response = await apiFetch('/api/service-processes/start', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) {
        text(logId, apiErrorText(data, response.statusText));
        return;
      }
      if (data.erpnext_error?.status_code === 409) {
        const measurementName = data.erpnext_error?.detail?.measurement_name ?? 'a mérési rekord';
        text(logId, `${measurementName} már létezik ERPNext-ben.`);
        if (confirm(`${measurementName} már létezik. Valóban felül akarod írni?`)) {
          await startServiceProcess(processKey, true);
        }
        return;
      }
      const erpText = data.erpnext_measurement ? `ERPNext Battery Measurement létrehozva: ${data.erpnext_measurement.name ?? ''}` : (data.erpnext_error ? erpNextErrorText(data.erpnext_error) : 'Lokálisan mentve');
      const stepsText = (data.next_steps ?? []).length ? `\\nVezetett lépések:\\n- ${data.next_steps.join('\\n- ')}` : '';
      text(logId, `${data.label}\\n${data.api_measurement_id}\\nMért modul: MOD${String(payload.module_no || 1).padStart(2, '0')}\\n${erpText}\\n${data.local_path || ''}${stepsText}`);
      if (repairJob) {
        await loadErpNextJobs();
      }
    }

    async function createReport() {
      const payload = {
        battery_id: el('reportBatteryId').value,
        customer_name: el('reportVehicle').value,
        vehicle_type: el('reportVehicle').value,
        operator_name: el('reportTechnician').value,
        measurement_type: el('reportMode').value,
        erp_reference: el('reportErpReference').value,
        invoice_number: el('reportInvoiceNumber').value,
        work_order_id: el('reportWorkOrderId').value
      };
      const response = await apiFetch('/api/reports', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        const error = await response.json();
        text('reportPreview', error.detail ?? response.statusText);
        return;
      }
      latestReport = await response.json();
      renderReportPreview(latestReport);
    }

    function renderReportPreview(report) {
      const lines = [
        'EV Battery Service jegyzőkönyv',
        `Report ID: ${report.report_id}`,
        `Measurement ID: ${report.measurement_id}`,
        `Dátum: ${new Date(report.created_at).toLocaleString()}`,
        `Akkumulátor: ${report.battery.battery_id || '--'}`,
        `Ügyfél / jármű: ${report.customer_name || report.vehicle_type || '--'}`,
        `Technikus: ${report.operator_name || '--'}`,
        `Mérés típusa: ${report.measurement_type}`,
        `ERP referencia: ${report.erp_reference || '--'}`,
        `Számlaszám: ${report.invoice_number || '--'}`,
        `Munkalap: ${report.work_order_id || '--'}`,
        '',
        'Összegzés',
        `Eredmény: ${report.summary.result}`,
        `Pack feszültség: ${report.summary.pack_voltage_start_v ?? '--'} V`,
        `Áram: ${report.summary.current_a ?? '--'} A`,
        `Min cella: ${report.summary.min_cell_v ?? '--'} V`,
        `Max cella: ${report.summary.max_cell_v ?? '--'} V`,
        `Cella delta: ${report.summary.delta_cell_v ?? '--'} V`,
        `Max belső ellenállás: ${report.quick_test.max_cell_resistance_mohm ?? '--'} mOhm`,
        '',
        'Tervezett grafikonok',
        ...(report.charts.planned ?? []).map((chart) => `- ${chart}`),
        '',
        'Figyelmeztetések',
        ...((report.quick_test.warnings ?? []).length ? report.quick_test.warnings : ['nincs']),
        '',
        'Faultok',
        ...((report.quick_test.faults ?? []).length ? report.quick_test.faults : ['nincs'])
      ];
      text('reportPreview', lines.join('\\n'));
    }

    async function downloadReportExport(format) {
      if (!latestReport) {
        await createReport();
      }
      if (!latestReport) {
        return;
      }
      const url = `/api/reports/${latestReport.measurement_id}/${format}`;
      const response = await apiFetch(url);
      if (!response.ok) {
        const error = await response.json();
        text('reportPreview', error.detail ?? response.statusText);
        return;
      }
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = `${latestReport.measurement_id}.${format}`;
      link.click();
      URL.revokeObjectURL(objectUrl);
    }

    fetch('/api/status')
      .then((response) => response.json())
      .then(render)
      .catch((error) => text('commandLog', error.message));

    loadErpNextJobs().catch((error) => {
      text('cellVoltageLog', error.message);
      text('erpnextLog', error.message);
      text('chargeLog', error.message);
    });

    el('cellTargetCount').addEventListener('input', () => {
      if (latestStatus) {
        render(latestStatus);
      }
    });

    ['cellModuleNo', 'cellModuleCount', 'cellWarnLow', 'cellWarnHigh', 'cellMaxDelta'].forEach((id) => {
      el(id)?.addEventListener('input', () => {
        if (id === 'cellModuleCount') {
          renderModuleSelect('cell');
        }
        if (latestStatus) {
          render(latestStatus);
        }
      });
    });

    el('cellModuleNo')?.addEventListener('change', () => {
      renderCellMeasurementNamePreview();
      if (latestStatus) {
        render(latestStatus);
      }
    });

    el('cellMeasurementStage')?.addEventListener('change', () => {
      renderCellMeasurementNamePreview();
      if (latestStatus) {
        render(latestStatus);
      }
    });

    el('resistanceMeasurementStage')?.addEventListener('change', () => {
      renderResistanceMeasurementNamePreview();
      if (latestStatus) {
        render(latestStatus);
      }
    });

    ['resistanceModuleNo', 'resistanceModuleCount'].forEach((id) => {
      el(id)?.addEventListener('input', () => {
        if (id === 'resistanceModuleCount') {
          renderModuleSelect('resistance');
        }
        renderResistanceMeasurementNamePreview();
        if (latestStatus) {
          render(latestStatus);
        }
      });
    });

    el('resistanceModuleNo')?.addEventListener('change', () => {
      renderResistanceMeasurementNamePreview();
      if (latestStatus) {
        render(latestStatus);
      }
    });

    ['dischargeModuleNo', 'dischargeModuleCount'].forEach((id) => {
      el(id)?.addEventListener('input', () => {
        if (id === 'dischargeModuleCount') {
          renderModuleSelect('discharge');
        }
        renderDischargeMeasurementNamePreview();
        if (latestStatus) {
          render(latestStatus);
        }
      });
    });

    el('dischargeModuleNo')?.addEventListener('change', () => {
      renderDischargeMeasurementNamePreview();
      if (latestStatus) {
        render(latestStatus);
      }
    });

    el('dischargeMeasurementStage')?.addEventListener('change', () => {
      renderDischargeMeasurementNamePreview();
      if (latestStatus) {
        render(latestStatus);
      }
    });

    ['balancingModuleNo', 'balancingModuleCount'].forEach((id) => {
      el(id)?.addEventListener('input', () => {
        if (id === 'balancingModuleCount') {
          renderModuleSelect('balancing');
        }
        renderBalancingMeasurementNamePreview();
        if (latestStatus) {
          render(latestStatus);
        }
      });
    });

    el('balancingModuleNo')?.addEventListener('change', () => {
      renderBalancingMeasurementNamePreview();
      if (latestStatus) {
        render(latestStatus);
      }
    });

    el('balancingMeasurementStage')?.addEventListener('change', () => {
      renderBalancingMeasurementNamePreview();
      if (latestStatus) {
        render(latestStatus);
      }
    });

    ['chargeModuleNo', 'chargeModuleCount'].forEach((id) => {
      el(id)?.addEventListener('input', () => {
        if (id === 'chargeModuleCount') {
          renderModuleSelect('charge');
        }
        renderChargeMeasurementNamePreview();
        if (latestStatus) {
          render(latestStatus);
        }
      });
    });

    el('chargeModuleNo')?.addEventListener('change', () => {
      renderChargeMeasurementNamePreview();
      if (latestStatus) {
        render(latestStatus);
      }
    });

    el('chargeMeasurementStage')?.addEventListener('change', () => {
      renderChargeMeasurementNamePreview();
      if (latestStatus) {
        render(latestStatus);
      }
    });

    el('resistanceCellCount').addEventListener('input', () => {
      if (latestStatus) {
        render(latestStatus);
      }
    });

    if (!latestStatus) {
      render({
        connected: false,
        can_error: null,
        system_state: null,
        fault_state: 0,
        relay_flags: null,
        supply_flags: null,
        balancer_flags: null,
        active_profile: null,
        uptime_s: null,
        pack_voltage_v: null,
        current_a: null,
        power_w: null,
        cell_voltages_mv: [],
        cell_resistances_mohm: [],
        resistance_measurement_running: false,
        min_cell_mv: null,
        max_cell_mv: null,
        cell_delta_mv: null,
        max_cell_resistance_mohm: null,
        fault_code: null,
        fault_severity: null,
        measurement_valid: false,
        last_can_rx_ms: null
      });
    }
  </script>
</body>
</html>
"""
