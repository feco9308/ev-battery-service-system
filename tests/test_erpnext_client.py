import json
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

import pytest
from pydantic import ValidationError

from app.integrations.erpnext_client import ErpNextClient, ErpNextConfig, ErpNextError
from app.integrations.models import MeasurementStatusUpdate


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def client() -> ErpNextClient:
    return ErpNextClient(
        ErpNextConfig(
            base_url="https://erp.example.hu",
            api_key="key",
            api_secret="secret",
            repair_job_doctype="Battery Repair Job",
        )
    )


def test_health_check_success() -> None:
    with patch("app.integrations.erpnext_client.urlopen", return_value=FakeResponse({"data": [{"name": "AKKU-1"}]})) as urlopen:
        checked_doctype = client().get_logged_user()

    request = urlopen.call_args.args[0]
    assert checked_doctype == "Battery Repair Job"
    assert request.headers["Authorization"] == "token key:secret"
    assert request.full_url.startswith("https://erp.example.hu/api/resource/Battery%20Repair%20Job?")
    assert "limit_page_length=1" in request.full_url


def test_health_check_bad_token() -> None:
    error = HTTPError(
        url="https://erp.example.hu/api/method/frappe.auth.get_logged_user",
        code=401,
        msg="Unauthorized",
        hdrs={},
        fp=BytesIO(b'{"exc": "bad token"}'),
    )
    with patch("app.integrations.erpnext_client.urlopen", side_effect=error):
        with pytest.raises(ErpNextError) as exc_info:
            client().get_logged_user()

    assert exc_info.value.status_code == 401


def test_health_check_permission_denied() -> None:
    error = HTTPError(
        url="https://erp.example.hu/api/resource/Battery%20Repair%20Job",
        code=403,
        msg="Forbidden",
        hdrs={},
        fp=BytesIO(b'{"_error_message": "No permission for Battery Repair Job"}'),
    )
    with patch("app.integrations.erpnext_client.urlopen", side_effect=error):
        with pytest.raises(ErpNextError) as exc_info:
            client().get_logged_user()

    assert exc_info.value.status_code == 403
    assert str(exc_info.value) == "ERPNext permission denied"


def test_list_open_repair_jobs() -> None:
    payload = {
        "data": [
            {
                "name": "AKKU-2026-00001",
                "customer": "Teszt ugyfel",
                "license_plate": "AAA-001",
                "vehicle_make": "Hyundai",
                "vehicle_model": "Kona EV",
                "vehicle_year": 2021,
                "vin": "VIN123",
                "job_status": "Diagnosztika alatt",
                "pre_measurement_done": False,
                "post_measurement_done": False,
                "last_measurement_datetime": None,
            }
        ]
    }
    with patch("app.integrations.erpnext_client.urlopen", return_value=FakeResponse(payload)) as urlopen:
        jobs = client().list_open_repair_jobs()

    assert jobs[0].name == "AKKU-2026-00001"
    assert jobs[0].license_plate == "AAA-001"
    request_url = urlopen.call_args.args[0].full_url
    query = parse_qs(urlparse(request_url).query)
    filters = json.loads(query["filters"][0])
    assert filters == [
        [
            "job_status",
            "in",
            [
                "Diagnosztika alatt",
                "Akkumulátor szétszedve",
                "Akkumulátor újrateszt alatt",
                "Balanszírozás alatt",
            ],
        ]
    ]


def test_pre_measurement_status_update() -> None:
    update = MeasurementStatusUpdate(
        measurement_type="pre",
        measurement_id="MEAS-2026-00001",
        measurement_datetime=datetime(2026, 7, 1, 14, 30, tzinfo=timezone.utc),
    )
    with patch(
        "app.integrations.erpnext_client.urlopen",
        side_effect=[
            FakeResponse(
                {
                    "data": {
                        "name": "AKKU-1",
                        "pre_measurement_done": False,
                        "post_measurement_done": False,
                        "last_measurement_status": "Nincs mérés",
                    }
                }
            ),
            FakeResponse({"data": {"name": "AKKU-1"}}),
        ],
    ) as urlopen:
        result = client().update_measurement_status("AKKU-1", update)

    request = urlopen.call_args_list[1].args[0]
    body = json.loads(request.data.decode("utf-8"))
    assert result["name"] == "AKKU-1"
    assert body["pre_measurement_done"] is True
    assert body["last_measurement_status"] == "Mérés kész"
    assert "last_measurement_id" not in body


def test_post_measurement_status_update() -> None:
    update = MeasurementStatusUpdate(
        measurement_type="post",
        measurement_id="MEAS-2026-00002",
        measurement_datetime=datetime(2026, 7, 1, 15, 30, tzinfo=timezone.utc),
    )
    with patch(
        "app.integrations.erpnext_client.urlopen",
        side_effect=[
            FakeResponse(
                {
                    "data": {
                        "name": "AKKU-1",
                        "pre_measurement_done": False,
                        "post_measurement_done": False,
                        "last_measurement_status": "Nincs mérés",
                    }
                }
            ),
            FakeResponse({"data": {"name": "AKKU-1"}}),
        ],
    ) as urlopen:
        client().update_measurement_status("AKKU-1", update)

    body = json.loads(urlopen.call_args_list[1].args[0].data.decode("utf-8"))
    assert body["post_measurement_done"] is True
    assert body["last_measurement_status"] == "Mérés kész"


def test_submitted_measurement_status_permission_error_is_clear() -> None:
    update = MeasurementStatusUpdate(
        measurement_type="pre",
        measurement_id="MEAS-2026-00001",
        measurement_datetime=datetime(2026, 7, 1, 14, 30, tzinfo=timezone.utc),
    )
    permission_error = HTTPError(
        url="https://erp.example.hu/api/resource/Battery%20Repair%20Job/AKKU-1",
        code=403,
        msg="Forbidden",
        hdrs={},
        fp=BytesIO(b'{"_error_message": "No permission for Battery Repair Job"}'),
    )
    with patch(
        "app.integrations.erpnext_client.urlopen",
        side_effect=[
            FakeResponse(
                {
                    "data": {
                        "name": "AKKU-1",
                        "docstatus": 1,
                        "pre_measurement_done": False,
                        "post_measurement_done": False,
                        "last_measurement_status": "Nincs mérés",
                    }
                }
            ),
            permission_error,
        ],
    ):
        with pytest.raises(ErpNextError) as exc_info:
            client().update_measurement_status("AKKU-1", update)

    assert exc_info.value.status_code == 403
    assert str(exc_info.value) == "ERPNext permission denied for submitted repair job"


def test_measurement_status_marks_both_done_when_other_side_ready() -> None:
    update = MeasurementStatusUpdate(
        measurement_type="post",
        measurement_id="MEAS-2026-00002",
        measurement_datetime=datetime(2026, 7, 1, 15, 30, tzinfo=timezone.utc),
    )
    with patch(
        "app.integrations.erpnext_client.urlopen",
        side_effect=[
            FakeResponse(
                {
                    "data": {
                        "name": "AKKU-1",
                        "pre_measurement_done": True,
                        "post_measurement_done": False,
                        "last_measurement_status": "Mérés kész",
                    }
                }
            ),
            FakeResponse({"data": {"name": "AKKU-1"}}),
        ],
    ) as urlopen:
        client().update_measurement_status("AKKU-1", update)

    body = json.loads(urlopen.call_args_list[1].args[0].data.decode("utf-8"))
    assert body["last_measurement_status"] == "Mérés kész"


def test_missing_erpnext_config_raises_clear_error() -> None:
    erp_client = ErpNextClient(ErpNextConfig(base_url="", api_key="", api_secret=""))

    with pytest.raises(ErpNextError) as exc_info:
        erp_client.get_logged_user()

    assert exc_info.value.status_code == 503
    assert "ERPNEXT_BASE_URL" in str(exc_info.value)


def test_invalid_measurement_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        MeasurementStatusUpdate.model_validate(
            {
                "measurement_type": "during",
                "measurement_id": "MEAS-1",
                "measurement_datetime": "2026-07-01T14:30:00Z",
            }
        )
