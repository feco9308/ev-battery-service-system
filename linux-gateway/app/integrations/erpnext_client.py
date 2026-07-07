import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .models import BatteryBalanceMeasurement, BatteryCellMeasurement, BatteryChargeMeasurement, BatteryDischargeMeasurement, BatteryMeasurementPayload, BatteryResistanceMeasurement, MeasurementStatusUpdate, RepairJob


OPEN_REPAIR_JOB_STATUSES = [
    "Diagnosztika alatt",
    "Akkumulátor szétszedve",
    "Akkumulátor újrateszt alatt",
    "Balanszírozás alatt",
]

TEST_TYPE_CODES = {
    "Nyugalmi mérés": 1,
    "Ellenállásmérés": 2,
    "Merítés": 3,
    "Töltés": 4,
    "Balanszírozás": 5,
    "Terheléses mérés": 6,
    "Teljes ciklus": 9,
}

MEASUREMENT_STAGE_CODES = {
    "Beérkezéskori mérés": 1,
    "Javítás utáni mérés": 2,
    "Merítés utáni mérés": 3,
    "Végső mérés": 4,
    "Köztes ellenőrző mérés": 5,
}


@dataclass(frozen=True)
class ErpNextConfig:
    base_url: str
    api_key: str
    api_secret: str
    repair_job_doctype: str = "Battery Repair Job"
    battery_measurement_doctype: str = "Battery Measurement"
    timeout_s: float = 10.0

    @classmethod
    def from_env(cls) -> "ErpNextConfig":
        return cls(
            base_url=os.getenv("ERPNEXT_BASE_URL", "").rstrip("/"),
            api_key=os.getenv("ERPNEXT_API_KEY", ""),
            api_secret=os.getenv("ERPNEXT_API_SECRET", ""),
            repair_job_doctype=os.getenv("ERPNEXT_REPAIR_JOB_DOCTYPE", "Battery Repair Job"),
            battery_measurement_doctype=os.getenv("ERPNEXT_BATTERY_MEASUREMENT_DOCTYPE", "Battery Measurement"),
        )

    def validate(self) -> None:
        missing = [
            name
            for name, value in [
                ("ERPNEXT_BASE_URL", self.base_url),
                ("ERPNEXT_API_KEY", self.api_key),
                ("ERPNEXT_API_SECRET", self.api_secret),
                ("ERPNEXT_REPAIR_JOB_DOCTYPE", self.repair_job_doctype),
                ("ERPNEXT_BATTERY_MEASUREMENT_DOCTYPE", self.battery_measurement_doctype),
            ]
            if not value
        ]
        if missing:
            raise ErpNextError(f"Missing ERPNext configuration: {', '.join(missing)}", status_code=503)


class ErpNextError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502, detail: Any | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class ErpNextClient:
    def __init__(self, config: ErpNextConfig | None = None) -> None:
        self.config = config or ErpNextConfig.from_env()

    def get_logged_user(self) -> str:
        params = {
            "fields": json.dumps(["name"]),
            "limit_page_length": "1",
        }
        data = self._request("GET", self._resource_path(), params=params)
        documents = data.get("data")
        if not isinstance(documents, list):
            raise ErpNextError("ERPNext health check returned an invalid response")
        return self.config.repair_job_doctype

    def list_open_repair_jobs(self) -> list[RepairJob]:
        fields = [
            "name",
            "customer",
            "license_plate",
            "vehicle_make",
            "vehicle_model",
            "vehicle_year",
            "vin",
            "job_status",
            "pre_measurement_done",
            "post_measurement_done",
            "last_measurement_datetime",
        ]
        params = {
            "fields": json.dumps(fields),
            "filters": json.dumps([["job_status", "in", OPEN_REPAIR_JOB_STATUSES]]),
            "limit_page_length": "100",
            "order_by": "modified desc",
        }
        data = self._request("GET", self._resource_path(), params=params)
        jobs = []
        for item in data.get("data", []):
            enriched = dict(item)
            try:
                detail = self.get_repair_job(str(item.get("name", "")))
            except ErpNextError:
                detail = {}
            module_count = _module_count_from_repair_job(detail)
            if module_count is not None:
                enriched["module_count"] = module_count
            if detail.get("cell_count") not in (None, ""):
                enriched["cell_count"] = detail.get("cell_count")
            jobs.append(RepairJob(**enriched))
        return jobs

    def get_repair_job(self, job_id: str) -> dict[str, Any]:
        data = self._request("GET", self._resource_path(job_id))
        document = data.get("data")
        if not isinstance(document, dict):
            raise ErpNextError("Repair job not found", status_code=404)
        return document

    def update_measurement_status(self, job_id: str, update: MeasurementStatusUpdate) -> dict[str, Any]:
        current_document = self.get_repair_job(job_id)
        payload = self._measurement_status_payload(update, current_document)
        # TODO: create Battery Measurement DocType, upload cell data as child table,
        # generate charts, and attach PDF report through ERPNext File.
        try:
            data = self._request("PUT", self._resource_path(job_id), payload=payload)
        except ErpNextError as exc:
            if exc.status_code == 403 and current_document.get("docstatus") == 1:
                raise ErpNextError(
                    "ERPNext permission denied for submitted repair job",
                    status_code=403,
                    detail=exc.detail,
                ) from exc
            raise
        document = data.get("data")
        return document if isinstance(document, dict) else data

    def create_battery_measurement(self, payload: BatteryMeasurementPayload, *, overwrite_existing: bool = False) -> dict[str, Any]:
        measurement_no, measurement_name = self._resolve_measurement_identity(payload)
        request_payload = self._battery_measurement_payload(payload, measurement_no=measurement_no, measurement_name=measurement_name)
        existing = self._get_battery_measurement(measurement_name)
        if existing is not None and not overwrite_existing:
            raise ErpNextError(
                f"Battery Measurement already exists: {measurement_name}",
                status_code=409,
                detail={"measurement_name": measurement_name, "existing": existing},
            )
        if existing is not None:
            data = self._request("PUT", self._measurement_resource_path(measurement_name), payload=request_payload)
        else:
            data = self._request("POST", self._measurement_resource_path(), payload=request_payload)
        document = data.get("data")
        return document if isinstance(document, dict) else data

    def _resolve_measurement_identity(self, payload: BatteryMeasurementPayload) -> tuple[int, str]:
        if payload.measurement_name:
            measurement_no = payload.measurement_no or _measurement_no_from_name(payload.measurement_name) or 1
            return measurement_no, payload.measurement_name
        test_code = TEST_TYPE_CODES.get(payload.test_type, 99)
        stage_code = MEASUREMENT_STAGE_CODES.get(payload.measurement_stage, 99)
        module_no = payload.module_no if payload.module_no is not None and payload.module_no > 0 else 1
        measurement_no = (module_no * 10000) + (test_code * 100) + stage_code
        measurement_name = f"{payload.repair_job}-MOD{module_no:02d}-M{test_code:02d}-{stage_code:02d}"
        return measurement_no, measurement_name

    def _get_battery_measurement(self, measurement_name: str) -> dict[str, Any] | None:
        try:
            data = self._request("GET", self._measurement_resource_path(measurement_name))
        except ErpNextError as exc:
            if exc.status_code == 404:
                return None
            raise
        document = data.get("data")
        return document if isinstance(document, dict) else data

    def _next_battery_measurement_no(self, repair_job: str) -> int:
        params = {
            "fields": json.dumps(["name"]),
            "filters": json.dumps([["repair_job", "=", repair_job]]),
            "limit_page_length": "1000",
            "order_by": "modified desc",
        }
        data = self._request("GET", self._measurement_resource_path(), params=params)
        numbers = [_measurement_no_from_document(document) for document in data.get("data", [])]
        valid_numbers = [number for number in numbers if number is not None]
        return (max(valid_numbers) + 1) if valid_numbers else 1

    def _measurement_status_payload(self, update: MeasurementStatusUpdate, current_document: dict[str, Any]) -> dict[str, Any]:
        measurement_datetime = update.measurement_datetime.strftime("%Y-%m-%d %H:%M:%S")
        payload: dict[str, Any] = {}
        if "last_measurement_datetime" in current_document:
            payload["last_measurement_datetime"] = measurement_datetime
        if "last_measurement_id" in current_document:
            payload["last_measurement_id"] = update.measurement_id
        pre_done = bool(current_document.get("pre_measurement_done"))
        post_done = bool(current_document.get("post_measurement_done"))
        if update.measurement_type == "pre":
            pre_done = True
            payload["pre_measurement_done"] = True
            payload[self._measurement_status_field(current_document)] = "Mérés kész"
        elif update.measurement_type == "post":
            post_done = True
            payload["post_measurement_done"] = True
            payload[self._measurement_status_field(current_document)] = "Mérés kész"
        else:
            raise ErpNextError("Invalid measurement_type", status_code=400)
        if pre_done and post_done:
            payload[self._measurement_status_field(current_document)] = "Mérés kész"
        return payload

    def _measurement_status_field(self, current_document: dict[str, Any]) -> str:
        if "last_measurement_status" in current_document:
            return "last_measurement_status"
        return "measurement_status"

    def _resource_path(self, document_name: str | None = None) -> str:
        doctype = quote(self.config.repair_job_doctype, safe="")
        if document_name is None:
            return f"/api/resource/{doctype}"
        return f"/api/resource/{doctype}/{quote(document_name, safe='')}"

    def _measurement_resource_path(self, document_name: str | None = None) -> str:
        doctype = quote(self.config.battery_measurement_doctype, safe="")
        if document_name is None:
            return f"/api/resource/{doctype}"
        return f"/api/resource/{doctype}/{quote(document_name, safe='')}"

    def _battery_measurement_payload(self, payload: BatteryMeasurementPayload, *, measurement_no: int, measurement_name: str) -> dict[str, Any]:
        data: dict[str, Any] = {
            "__newname": measurement_name,
            "name": measurement_name,
            "repair_job": payload.repair_job,
            "module_no": payload.module_no if payload.module_no is not None else 0,
            "measurement_no": measurement_no,
            "measurement_code": measurement_name,
            "measurement_stage": payload.measurement_stage,
            "test_type": payload.test_type,
            "measurement_start": _format_datetime(payload.measurement_start),
            "measurement_status": payload.measurement_status,
            "api_measurement_id": payload.api_measurement_id,
        }
        if payload.test_type == "Ellenállásmérés":
            data["resistance_measurements"] = [
                _battery_resistance_payload(measurement)
                for measurement in payload.resistance_measurements
            ]
        elif payload.test_type == "Merítés":
            data["discharge_measurements"] = [
                _battery_discharge_payload(measurement)
                for measurement in payload.discharge_measurements
            ]
        elif payload.test_type == "Balanszírozás":
            data["balance_measurements"] = [
                _battery_balance_payload(measurement)
                for measurement in payload.balance_measurements
            ]
        elif payload.test_type == "Töltés":
            data["charge_measurements"] = [
                _battery_charge_payload(measurement)
                for measurement in payload.charge_measurements
            ]
        else:
            data["cell_measurements"] = [_battery_cell_payload(cell) for cell in payload.cells]
        if payload.measurement_values:
            data["measurement_values"] = [_battery_measurement_value_payload(value) for value in payload.measurement_values]
        optional_values = {
            "measurement_end": _format_datetime(payload.measurement_end) if payload.measurement_end else None,
            "duration_minutes": _duration_minutes(payload),
        }
        data.update({key: value for key, value in optional_values.items() if value is not None})
        return {key: value for key, value in data.items() if value is not None}

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.config.validate()
        url = f"{self.config.base_url}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(url, data=body, method=method)
        request.add_header("Authorization", f"token {self.config.api_key}:{self.config.api_secret}")
        request.add_header("Accept", "application/json")
        if payload is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urlopen(request, timeout=self.config.timeout_s) as response:
                return _decode_response(response.read())
        except HTTPError as exc:
            detail = _decode_response(exc.read())
            if exc.code == 401:
                raise ErpNextError("ERPNext authentication failed", status_code=401, detail=detail) from exc
            if exc.code == 403:
                raise ErpNextError("ERPNext permission denied", status_code=403, detail=detail) from exc
            if exc.code == 404:
                raise ErpNextError("ERPNext resource not found", status_code=404, detail=detail) from exc
            raise ErpNextError("ERPNext request failed", status_code=502, detail=detail) from exc
        except URLError as exc:
            raise ErpNextError(f"ERPNext is not reachable: {exc.reason}", status_code=503) from exc
        except TimeoutError as exc:
            raise ErpNextError("ERPNext request timed out", status_code=504) from exc


def _decode_response(raw: bytes) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ErpNextError("ERPNext returned invalid JSON") from exc
    return decoded if isinstance(decoded, dict) else {"data": decoded}


def _format_datetime(value) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _duration_minutes(payload: BatteryMeasurementPayload) -> float | None:
    if payload.measurement_end is None:
        return None
    return round((payload.measurement_end - payload.measurement_start).total_seconds() / 60.0, 3)


def _measurement_no_from_document(document: dict[str, Any]) -> int | None:
    measurement_no = document.get("measurement_no")
    if measurement_no not in (None, ""):
        try:
            return int(measurement_no)
        except (TypeError, ValueError):
            return None
    return _measurement_no_from_name(str(document.get("name") or ""))


def _measurement_no_from_name(name: str) -> int | None:
    suffix = name.rsplit("-M-", 1)[-1] if "-M-" in name else ""
    try:
        return int(suffix)
    except ValueError:
        return None


def _battery_cell_payload(cell: BatteryCellMeasurement) -> dict[str, Any]:
    cell_voltage = cell.cell_voltage if cell.cell_voltage is not None else cell.voltage
    cell_status = cell.cell_status if cell.cell_status is not None else cell.status
    data = {
        "module_no": cell.module_no,
        "cell_no": cell.cell_no if cell.cell_no is not None else cell.cell_group_no,
        "cell_voltage": cell_voltage,
        "cell_status": cell_status,
    }
    return {key: value for key, value in data.items() if value is not None}


def _battery_resistance_payload(measurement: BatteryResistanceMeasurement) -> dict[str, Any]:
    data = {
        "module_no": measurement.module_no,
        "cell_no": measurement.cell_no,
        "rest_voltage": measurement.rest_voltage,
        "load_voltage": measurement.load_voltage,
        "load_current": measurement.load_current,
        "voltage_drop_mv": measurement.voltage_drop_mv,
        "internal_resistance_mohm": measurement.internal_resistance_mohm,
        "resistance_status": measurement.resistance_status,
        "note": measurement.note,
    }
    return {key: value for key, value in data.items() if value is not None}


def _battery_discharge_payload(measurement: BatteryDischargeMeasurement) -> dict[str, Any]:
    data = {
        "module_no": measurement.module_no,
        "start_voltage": measurement.start_voltage,
        "end_voltage": measurement.end_voltage,
        "start_min_cell_voltage": measurement.start_min_cell_voltage,
        "end_min_cell_voltage": measurement.end_min_cell_voltage,
        "start_max_cell_voltage": measurement.start_max_cell_voltage,
        "end_max_cell_voltage": measurement.end_max_cell_voltage,
        "start_delta_mv": measurement.start_delta_mv,
        "end_delta_mv": measurement.end_delta_mv,
        "discharge_current": measurement.discharge_current,
        "discharge_duration_minutes": measurement.discharge_duration_minutes,
        "discharged_ah": measurement.discharged_ah,
        "discharged_wh": measurement.discharged_wh,
        "min_cell_no": measurement.min_cell_no,
        "max_cell_no": measurement.max_cell_no,
        "cutoff_reason": measurement.cutoff_reason,
        "discharge_status": measurement.discharge_status,
        "note": measurement.note,
    }
    return {key: value for key, value in data.items() if value is not None}


def _battery_balance_payload(measurement: BatteryBalanceMeasurement) -> dict[str, Any]:
    data = {
        "module_no": measurement.module_no,
        "cell_no": measurement.cell_no,
        "start_voltage": measurement.start_voltage,
        "end_voltage": measurement.end_voltage,
        "target_voltage": measurement.target_voltage,
        "voltage_change_mv": measurement.voltage_change_mv,
        "balance_current": measurement.balance_current,
        "balance_duration_minutes": measurement.balance_duration_minutes,
        "charged_ah": measurement.charged_ah,
        "charged_wh": measurement.charged_wh,
        "balance_status": measurement.balance_status,
        "balance_direction": measurement.balance_direction,
        "cutoff_reason": measurement.cutoff_reason,
        "note": measurement.note,
    }
    return {key: value for key, value in data.items() if value is not None}


def _battery_charge_payload(measurement: BatteryChargeMeasurement) -> dict[str, Any]:
    data = {
        "module_no": measurement.module_no,
        "start_voltage": measurement.start_voltage,
        "end_voltage": measurement.end_voltage,
        "start_min_cell_voltage": measurement.start_min_cell_voltage,
        "end_min_cell_voltage": measurement.end_min_cell_voltage,
        "start_max_cell_voltage": measurement.start_max_cell_voltage,
        "end_max_cell_voltage": measurement.end_max_cell_voltage,
        "start_delta_mv": measurement.start_delta_mv,
        "end_delta_mv": measurement.end_delta_mv,
        "charge_current": measurement.charge_current,
        "charge_duration_minutes": measurement.charge_duration_minutes,
        "charged_ah": measurement.charged_ah,
        "charged_wh": measurement.charged_wh,
        "min_cell_no": measurement.min_cell_no,
        "max_cell_no": measurement.max_cell_no,
        "cutoff_reason": measurement.cutoff_reason,
        "charge_status": measurement.charge_status,
        "note": measurement.note,
    }
    return {key: value for key, value in data.items() if value is not None}


def _battery_measurement_value_payload(value) -> dict[str, Any]:
    data = {
        "key": value.key,
        "value": value.value,
        "unit": value.unit,
        "note": value.note,
    }
    return {key: item for key, item in data.items() if item is not None}


def _module_count_from_repair_job(document: dict[str, Any]) -> int | None:
    value = document.get("module_count")
    if value not in (None, ""):
        try:
            return int(value)
        except (TypeError, ValueError):
            pass
    modules = document.get("battery_modules")
    if isinstance(modules, list) and modules:
        module_numbers = []
        for module in modules:
            if not isinstance(module, dict):
                continue
            try:
                module_numbers.append(int(module.get("module_no")))
            except (TypeError, ValueError):
                continue
        return max(module_numbers) if module_numbers else len(modules)
    return None
