import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .models import MeasurementStatusUpdate, RepairJob


OPEN_REPAIR_JOB_STATUSES = [
    "Diagnosztika alatt",
    "Akkumulátor szétszedve",
    "Akkumulátor újrateszt alatt",
    "Balanszírozás alatt",
]


@dataclass(frozen=True)
class ErpNextConfig:
    base_url: str
    api_key: str
    api_secret: str
    repair_job_doctype: str = "Battery Repair Job"
    timeout_s: float = 10.0

    @classmethod
    def from_env(cls) -> "ErpNextConfig":
        return cls(
            base_url=os.getenv("ERPNEXT_BASE_URL", "").rstrip("/"),
            api_key=os.getenv("ERPNEXT_API_KEY", ""),
            api_secret=os.getenv("ERPNEXT_API_SECRET", ""),
            repair_job_doctype=os.getenv("ERPNEXT_REPAIR_JOB_DOCTYPE", "Battery Repair Job"),
        )

    def validate(self) -> None:
        missing = [
            name
            for name, value in [
                ("ERPNEXT_BASE_URL", self.base_url),
                ("ERPNEXT_API_KEY", self.api_key),
                ("ERPNEXT_API_SECRET", self.api_secret),
                ("ERPNEXT_REPAIR_JOB_DOCTYPE", self.repair_job_doctype),
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
        return [RepairJob(**item) for item in data.get("data", [])]

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
