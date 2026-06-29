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
    try:
        await can_service.send_command(command, request.value or 0)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
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
      <button class="tab-button" data-tab="discharge" onclick="showTab('discharge')">Kisütés</button>
      <button class="tab-button" data-tab="cell-charge" onclick="showTab('cell-charge')">Cellánkénti töltés</button>
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
              <div class="field"><label>Megjelenített cellák</label><input id="cellTargetCount" type="number" min="1" max="255" value="120"></div>
              <div class="field"><label>Alsó figyelmeztetés</label><input id="cellWarnLow" type="number" step="0.001" value="3.000"></div>
              <div class="field"><label>Felső figyelmeztetés</label><input id="cellWarnHigh" type="number" step="0.001" value="4.200"></div>
              <div class="field"><label>Max delta</label><input id="cellMaxDelta" type="number" step="1" value="20"></div>
            </div>
            <div id="cellsMirror" class="cells" style="margin-top: 14px;"></div>
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
              <div class="field"><label>Cél pack feszültség</label><input id="dischargePackTarget" type="number" step="0.1" value="300.0"></div>
              <div class="field"><label>Cél cellafeszültség</label><input id="dischargeCellTarget" type="number" step="0.001" value="3.000"></div>
              <div class="field"><label>Áramlimit</label><input id="dischargeCurrentLimit" type="number" step="0.1" value="10.0"></div>
              <div class="field"><label>Leállási feltétel</label><select id="dischargeStopMode"><option>Első cella cél alatt</option><option>Pack célfeszültség alatt</option><option>Időlimit</option></select></div>
            </div>
            <div class="commands" style="margin-top: 14px;">
              <button class="primary" onclick="cmd('measurement_start', true)">Kisütés előmérés indítása</button>
              <button class="stop" onclick="cmd('measurement_stop')">Mérés leállítása</button>
              <button class="danger" onclick="cmd('emergency_stop', true)">EMERGENCY STOP</button>
            </div>
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
            <span class="badge">Modulvezérlés később</span>
          </div>
          <div class="panel-body">
            <div class="form-grid">
              <div class="field"><label>Cella választás</label><select id="singleCellSelect"></select></div>
              <div class="field"><label>Célfeszültség</label><input id="singleCellTarget" type="number" step="0.001" value="4.100"></div>
              <div class="field"><label>Áramlimit</label><input id="singleCellCurrent" type="number" step="0.01" value="0.50"></div>
              <div class="field"><label>Balansz delta cél</label><input id="balanceDeltaTarget" type="number" step="1" value="10"></div>
            </div>
            <div class="commands" style="margin-top: 14px;">
              <button disabled>Cella töltés indítása</button>
              <button disabled>Balansz indítása</button>
              <button class="stop" onclick="cmd('balancer_all_off')">Balancer OFF</button>
              <button class="danger" onclick="cmd('emergency_stop', true)">EMERGENCY STOP</button>
            </div>
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
              <div class="field"><label>Cél pack feszültség</label><input id="chargePackTarget" type="number" step="0.1" value="360.0"></div>
              <div class="field"><label>Cél cellafeszültség</label><input id="chargeCellTarget" type="number" step="0.001" value="4.100"></div>
              <div class="field"><label>CC áramlimit</label><input id="chargeCurrentLimit" type="number" step="0.1" value="5.0"></div>
              <div class="field"><label>CV lezáró áram</label><input id="chargeEndCurrent" type="number" step="0.1" value="0.5"></div>
            </div>
            <div class="commands" style="margin-top: 14px;">
              <button disabled>Teljes töltés indítása</button>
              <button class="stop" onclick="cmd('supply_output_off')">Supply OFF</button>
              <button class="danger" onclick="cmd('emergency_stop', true)">EMERGENCY STOP</button>
            </div>
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
              <div class="step"><span>1</span><strong>Előmérés</strong><small>Cella, pack, fault és kapcsolat ellenőrzés.</small></div>
              <div class="step"><span>2</span><strong>Kisütés</strong><small>Célfeszültségig vagy biztonsági leállásig.</small></div>
              <div class="step"><span>3</span><strong>Töltés</strong><small>CC/CV töltés megadott célértékig.</small></div>
              <div class="step"><span>4</span><strong>Balansz + riport</strong><small>Delta csökkentés, majd jegyzőkönyv generálás.</small></div>
            </div>
            <div class="commands" style="margin-top: 14px;">
              <button disabled>Teljes ciklus indítása</button>
              <button class="stop" onclick="cmd('measurement_stop')">Ciklus szünet / stop</button>
              <button class="danger" onclick="cmd('emergency_stop', true)">EMERGENCY STOP</button>
            </div>
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
            </div>
            <div class="commands" style="margin-top: 14px;">
              <button class="primary" onclick="buildReport()">Jegyzőkönyv előnézet</button>
              <button onclick="downloadReport()">TXT letöltés</button>
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

    let latestStatus = null;
    let latestReport = '';

    const el = (id) => document.getElementById(id);
    const fmt = (value, digits = 1) => value === null || value === undefined ? '--' : Number(value).toFixed(digits);
    const text = (id, value) => {
      const target = el(id);
      if (target) {
        target.textContent = value;
      }
    };

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
      renderWorkflowMirrors(status);
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
      const markup = visibleCells.map((value, index) => {
        const state = value === stats.min ? 'low' : value === stats.max ? 'high' : '';
        return `<div class="cell ${state}"><small>C${index + 1}</small><strong>${value ?? '--'} mV</strong></div>`;
      }).join('');
      el('cells').innerHTML = markup;
      el('cellsMirror').innerHTML = markup;
      renderCellSelect(visibleCells.length);
    }

    function renderCellSelect(count) {
      const select = el('singleCellSelect');
      const currentCount = select.options.length;
      if (currentCount === count) {
        return;
      }
      select.innerHTML = Array.from({length: count || 1}, (_, index) => `<option value="${index}">C${index + 1}</option>`).join('');
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

    function buildReport() {
      const status = latestStatus ?? {};
      const lines = [
        'EV Battery Service jegyzőkönyv',
        `Dátum: ${new Date().toLocaleString()}`,
        `Akkumulátor azonosító: ${el('reportBatteryId').value}`,
        `Ügyfél / jármű: ${el('reportVehicle').value}`,
        `Technikus: ${el('reportTechnician').value}`,
        `Mérés típusa: ${el('reportMode').value}`,
        '',
        'Összegzés',
        `CAN kapcsolat: ${status.connected ? 'aktív' : 'nincs kapcsolat'}`,
        `Rendszerállapot: ${systemStates[status.system_state] ?? status.system_state ?? '--'}`,
        `Pack feszültség: ${fmt(status.pack_voltage_v, 1)} V`,
        `Áram: ${fmt(status.current_a, 2)} A`,
        `Teljesítmény: ${fmt(status.power_w, 0)} W`,
        `Min cella: ${status.min_cell_mv ?? '--'} mV`,
        `Max cella: ${status.max_cell_mv ?? '--'} mV`,
        `Cella delta: ${status.cell_delta_mv ?? '--'} mV`,
        `Fault: ${status.fault_code ?? 'nincs'}`,
        '',
        'Cellafeszültségek',
        ...(status.cell_voltages_mv ?? []).map((value, index) => `C${index + 1}: ${value ?? '--'} mV`)
      ];
      latestReport = lines.join('\\n');
      text('reportPreview', latestReport);
    }

    function downloadReport() {
      if (!latestReport) {
        buildReport();
      }
      const blob = new Blob([latestReport], {type: 'text/plain;charset=utf-8'});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `ev-battery-report-${new Date().toISOString().slice(0, 10)}.txt`;
      link.click();
      URL.revokeObjectURL(url);
    }

    fetch('/api/status')
      .then((response) => response.json())
      .then(render)
      .catch((error) => text('commandLog', error.message));

    el('cellTargetCount').addEventListener('input', () => {
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
        min_cell_mv: null,
        max_cell_mv: null,
        cell_delta_mv: null,
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
