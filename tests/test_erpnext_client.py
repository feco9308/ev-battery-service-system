import json
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

import pytest
from pydantic import ValidationError

from app.integrations.erpnext_client import ErpNextClient, ErpNextConfig, ErpNextError
from app.integrations.models import (
    BatteryBalanceMeasurement,
    BatteryCellMeasurement,
    BatteryChargeMeasurement,
    BatteryDischargeMeasurement,
    BatteryMeasurementPayload,
    BatteryResistanceMeasurement,
    MeasurementStatusUpdate,
)


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
    detail_payload = {
        "data": {
            "name": "AKKU-2026-00001",
            "module_count": "9",
        }
    }
    with patch("app.integrations.erpnext_client.urlopen", side_effect=[FakeResponse(payload), FakeResponse(detail_payload)]) as urlopen:
        jobs = client().list_open_repair_jobs()

    assert jobs[0].name == "AKKU-2026-00001"
    assert jobs[0].license_plate == "AAA-001"
    assert jobs[0].module_count == 9
    request_url = urlopen.call_args_list[0].args[0].full_url
    query = parse_qs(urlparse(request_url).query)
    fields = json.loads(query["fields"][0])
    assert "cell_count" not in fields
    assert "module_count" not in fields
    assert urlopen.call_args_list[1].args[0].full_url == "https://erp.example.hu/api/resource/Battery%20Repair%20Job/AKKU-2026-00001"
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


def test_create_battery_measurement_posts_named_record_and_cells() -> None:
    payload = BatteryMeasurementPayload(
        repair_job="AKKU-2026-00001",
        measurement_stage="Beérkezéskori mérés",
        test_type="Nyugalmi mérés",
        api_measurement_id="MEAS-2026-00001",
        measurement_start=datetime(2026, 7, 1, 14, 30, tzinfo=timezone.utc),
        measurement_end=datetime(2026, 7, 1, 14, 31, tzinfo=timezone.utc),
        module_no=1,
        min_cell_voltage=3.7,
        max_cell_voltage=3.72,
        max_cell_delta_mv=20,
        weakest_module="1",
        weakest_cell="1",
        cells=[
            BatteryCellMeasurement(
                module_no=1,
                cell_no=1,
                cell_voltage=3.7,
                loaded_cell_voltage=3.68,
                internal_resistance=2.1,
                cell_status="OK",
            )
        ],
        summary="OK",
    )
    with patch(
        "app.integrations.erpnext_client.urlopen",
        side_effect=[
            HTTPError(
                url="https://erp.example.hu/api/resource/Battery%20Measurement/AKKU-2026-00001-MOD01-M01-01",
                code=404,
                msg="Not Found",
                hdrs={},
                fp=BytesIO(b'{"exc": "missing"}'),
            ),
            FakeResponse({"data": {"name": "AKKU-2026-00001-MOD01-M01-01"}}),
        ],
    ) as urlopen:
        result = client().create_battery_measurement(payload)

    get_request = urlopen.call_args_list[0].args[0]
    assert get_request.full_url == "https://erp.example.hu/api/resource/Battery%20Measurement/AKKU-2026-00001-MOD01-M01-01"

    request = urlopen.call_args_list[1].args[0]
    body = json.loads(request.data.decode("utf-8"))
    assert result["name"] == "AKKU-2026-00001-MOD01-M01-01"
    assert request.full_url == "https://erp.example.hu/api/resource/Battery%20Measurement"
    assert body["__newname"] == "AKKU-2026-00001-MOD01-M01-01"
    assert body["name"] == "AKKU-2026-00001-MOD01-M01-01"
    assert body["measurement_no"] == 10101
    assert body["measurement_code"] == "AKKU-2026-00001-MOD01-M01-01"
    assert body["repair_job"] == "AKKU-2026-00001"
    assert body["module_no"] == 1
    assert body["measurement_stage"] == "Beérkezéskori mérés"
    assert body["test_type"] == "Nyugalmi mérés"
    assert body["measurement_status"] == "Kész"
    assert body["duration_minutes"] == 1.0
    assert "cell_count" not in body
    assert "module_count" not in body
    assert "min_cell_voltage" not in body
    assert "max_cell_voltage" not in body
    assert "summary" not in body
    assert body["cell_measurements"] == [
        {
            "module_no": 1,
            "cell_no": 1,
            "cell_voltage": 3.7,
            "cell_status": "OK",
        }
    ]
    assert "resistance_measurements" not in body


def test_create_battery_resistance_measurement_uses_resistance_child_table() -> None:
    payload = BatteryMeasurementPayload(
        repair_job="AKKU-2026-00001",
        measurement_stage="Beérkezéskori mérés",
        test_type="Ellenállásmérés",
        api_measurement_id="MEAS-2026-00002",
        measurement_start=datetime(2026, 7, 1, 14, 30, tzinfo=timezone.utc),
        measurement_end=datetime(2026, 7, 1, 14, 31, tzinfo=timezone.utc),
        module_no=3,
        cells=[],
        resistance_measurements=[
            BatteryResistanceMeasurement(
                module_no=3,
                cell_no=1,
                rest_voltage=3.7,
                load_voltage=3.674,
                load_current=12.3,
                voltage_drop_mv=26.0,
                internal_resistance_mohm=2.114,
                resistance_status="OK",
                note="",
            )
        ],
    )
    with patch(
        "app.integrations.erpnext_client.urlopen",
        side_effect=[
            HTTPError(
                url="https://erp.example.hu/api/resource/Battery%20Measurement/AKKU-2026-00001-MOD03-M02-01",
                code=404,
                msg="Not Found",
                hdrs={},
                fp=BytesIO(b'{"exc": "missing"}'),
            ),
            FakeResponse({"data": {"name": "AKKU-2026-00001-MOD03-M02-01"}}),
        ],
    ) as urlopen:
        result = client().create_battery_measurement(payload)

    request = urlopen.call_args_list[1].args[0]
    body = json.loads(request.data.decode("utf-8"))
    assert result["name"] == "AKKU-2026-00001-MOD03-M02-01"
    assert body["__newname"] == "AKKU-2026-00001-MOD03-M02-01"
    assert body["measurement_no"] == 30201
    assert body["measurement_code"] == "AKKU-2026-00001-MOD03-M02-01"
    assert body["module_no"] == 3
    assert body["test_type"] == "Ellenállásmérés"
    assert "cell_measurements" not in body
    assert body["resistance_measurements"] == [
        {
            "module_no": 3,
            "cell_no": 1,
            "rest_voltage": 3.7,
            "load_voltage": 3.674,
            "load_current": 12.3,
            "voltage_drop_mv": 26.0,
            "internal_resistance_mohm": 2.114,
            "resistance_status": "OK",
            "note": "",
        }
    ]


def test_create_battery_discharge_measurement_uses_discharge_child_table() -> None:
    payload = BatteryMeasurementPayload(
        repair_job="AKKU-2026-00001",
        measurement_stage="Javítás utáni mérés",
        test_type="Merítés",
        api_measurement_id="MEAS-2026-00003",
        measurement_start=datetime(2026, 7, 1, 14, 30, tzinfo=timezone.utc),
        measurement_end=datetime(2026, 7, 1, 14, 31, tzinfo=timezone.utc),
        module_no=4,
        cells=[],
        discharge_measurements=[
            BatteryDischargeMeasurement(
                module_no=4,
                start_voltage=66.8,
                end_voltage=65.0,
                start_min_cell_voltage=3.2,
                end_min_cell_voltage=3.0,
                start_max_cell_voltage=3.4,
                end_max_cell_voltage=3.2,
                start_delta_mv=200,
                end_delta_mv=200,
                discharge_current=10.5,
                discharge_duration_minutes=3.0,
                discharged_ah=0.003,
                discharged_wh=0.195,
                min_cell_no=1,
                max_cell_no=2,
                cutoff_reason="Elérte az alsó cellafeszültséget",
                discharge_status="OK",
            )
        ],
    )
    with patch(
        "app.integrations.erpnext_client.urlopen",
        side_effect=[
            HTTPError(
                url="https://erp.example.hu/api/resource/Battery%20Measurement/AKKU-2026-00001-MOD04-M03-02",
                code=404,
                msg="Not Found",
                hdrs={},
                fp=BytesIO(b'{"exc": "missing"}'),
            ),
            FakeResponse({"data": {"name": "AKKU-2026-00001-MOD04-M03-02"}}),
        ],
    ) as urlopen:
        result = client().create_battery_measurement(payload)

    request = urlopen.call_args_list[1].args[0]
    body = json.loads(request.data.decode("utf-8"))
    assert result["name"] == "AKKU-2026-00001-MOD04-M03-02"
    assert body["measurement_no"] == 40302
    assert body["module_no"] == 4
    assert body["test_type"] == "Merítés"
    assert "cell_measurements" not in body
    assert "resistance_measurements" not in body
    assert body["discharge_measurements"] == [
        {
            "module_no": 4,
            "start_voltage": 66.8,
            "end_voltage": 65.0,
            "start_min_cell_voltage": 3.2,
            "end_min_cell_voltage": 3.0,
            "start_max_cell_voltage": 3.4,
            "end_max_cell_voltage": 3.2,
            "start_delta_mv": 200,
            "end_delta_mv": 200,
            "discharge_current": 10.5,
            "discharge_duration_minutes": 3.0,
            "discharged_ah": 0.003,
            "discharged_wh": 0.195,
            "min_cell_no": 1,
            "max_cell_no": 2,
            "cutoff_reason": "Elérte az alsó cellafeszültséget",
            "discharge_status": "OK",
        }
    ]


def test_create_battery_balance_measurement_uses_balance_child_table() -> None:
    payload = BatteryMeasurementPayload(
        repair_job="AKKU-2026-00001",
        measurement_stage="Végső mérés",
        test_type="Balanszírozás",
        api_measurement_id="MEAS-2026-00004",
        measurement_start=datetime(2026, 7, 1, 14, 30, tzinfo=timezone.utc),
        measurement_end=datetime(2026, 7, 1, 14, 31, tzinfo=timezone.utc),
        module_no=1,
        cells=[],
        balance_measurements=[
            BatteryBalanceMeasurement(
                module_no=1,
                cell_no=1,
                start_voltage=3.665,
                end_voltage=3.7,
                target_voltage=3.7,
                voltage_change_mv=35.0,
                balance_current=0.5,
                balance_duration_minutes=7.0,
                charged_ah=0.0583,
                charged_wh=0.215,
                balance_status="OK",
                balance_direction="Töltés",
                cutoff_reason="Elérte a célfeszültséget",
                note="",
            )
        ],
    )
    with patch(
        "app.integrations.erpnext_client.urlopen",
        side_effect=[
            HTTPError(
                url="https://erp.example.hu/api/resource/Battery%20Measurement/AKKU-2026-00001-MOD01-M05-04",
                code=404,
                msg="Not Found",
                hdrs={},
                fp=BytesIO(b'{"exc": "missing"}'),
            ),
            FakeResponse({"data": {"name": "AKKU-2026-00001-MOD01-M05-04"}}),
        ],
    ) as urlopen:
        result = client().create_battery_measurement(payload)

    request = urlopen.call_args_list[1].args[0]
    body = json.loads(request.data.decode("utf-8"))
    assert result["name"] == "AKKU-2026-00001-MOD01-M05-04"
    assert body["measurement_no"] == 10504
    assert body["module_no"] == 1
    assert body["test_type"] == "Balanszírozás"
    assert "cell_measurements" not in body
    assert "resistance_measurements" not in body
    assert "discharge_measurements" not in body
    assert body["balance_measurements"] == [
        {
            "module_no": 1,
            "cell_no": 1,
            "start_voltage": 3.665,
            "end_voltage": 3.7,
            "target_voltage": 3.7,
            "voltage_change_mv": 35.0,
            "balance_current": 0.5,
            "balance_duration_minutes": 7.0,
            "charged_ah": 0.0583,
            "charged_wh": 0.215,
            "balance_status": "OK",
            "balance_direction": "Töltés",
            "cutoff_reason": "Elérte a célfeszültséget",
            "note": "",
        }
    ]


def test_create_battery_charge_measurement_uses_charge_child_table() -> None:
    payload = BatteryMeasurementPayload(
        repair_job="AKKU-2026-00001",
        measurement_stage="Javítás utáni mérés",
        test_type="Töltés",
        api_measurement_id="MEAS-2026-00005",
        measurement_start=datetime(2026, 7, 1, 15, 0, tzinfo=timezone.utc),
        measurement_end=datetime(2026, 7, 1, 16, 10, tzinfo=timezone.utc),
        module_no=1,
        cells=[],
        charge_measurements=[
            BatteryChargeMeasurement(
                module_no=1,
                start_voltage=59.8,
                end_voltage=66.35,
                start_min_cell_voltage=3.25,
                end_min_cell_voltage=3.675,
                start_max_cell_voltage=3.41,
                end_max_cell_voltage=3.705,
                start_delta_mv=160,
                end_delta_mv=30,
                charge_current=10.0,
                charge_duration_minutes=70,
                charged_ah=11.7,
                charged_wh=745.0,
                min_cell_no=7,
                max_cell_no=3,
                cutoff_reason="Elérte a felső cellafeszültséget",
                charge_status="OK",
                note="Töltés végén a cellaeltérés elfogadható.",
            )
        ],
    )
    with patch(
        "app.integrations.erpnext_client.urlopen",
        side_effect=[
            HTTPError(
                url="https://erp.example.hu/api/resource/Battery%20Measurement/AKKU-2026-00001-MOD01-M04-02",
                code=404,
                msg="Not Found",
                hdrs={},
                fp=BytesIO(b'{"exc": "missing"}'),
            ),
            FakeResponse({"data": {"name": "AKKU-2026-00001-MOD01-M04-02"}}),
        ],
    ) as urlopen:
        result = client().create_battery_measurement(payload)

    request = urlopen.call_args_list[1].args[0]
    body = json.loads(request.data.decode("utf-8"))
    assert result["name"] == "AKKU-2026-00001-MOD01-M04-02"
    assert body["measurement_no"] == 10402
    assert body["module_no"] == 1
    assert body["test_type"] == "Töltés"
    assert "cell_measurements" not in body
    assert "resistance_measurements" not in body
    assert "discharge_measurements" not in body
    assert "balance_measurements" not in body
    assert body["charge_measurements"] == [
        {
            "module_no": 1,
            "start_voltage": 59.8,
            "end_voltage": 66.35,
            "start_min_cell_voltage": 3.25,
            "end_min_cell_voltage": 3.675,
            "start_max_cell_voltage": 3.41,
            "end_max_cell_voltage": 3.705,
            "start_delta_mv": 160,
            "end_delta_mv": 30,
            "charge_current": 10.0,
            "charge_duration_minutes": 70.0,
            "charged_ah": 11.7,
            "charged_wh": 745.0,
            "min_cell_no": 7,
            "max_cell_no": 3,
            "cutoff_reason": "Elérte a felső cellafeszültséget",
            "charge_status": "OK",
            "note": "Töltés végén a cellaeltérés elfogadható.",
        }
    ]


def test_create_battery_measurement_requires_confirmation_before_overwrite() -> None:
    payload = BatteryMeasurementPayload(
        repair_job="AKKU-2026-00001",
        measurement_stage="Beérkezéskori mérés",
        test_type="Nyugalmi mérés",
        api_measurement_id="MEAS-2026-00001",
        measurement_start=datetime(2026, 7, 1, 14, 30, tzinfo=timezone.utc),
        cells=[BatteryCellMeasurement(module_no=1, cell_no=1, cell_voltage=3.7, cell_status="OK")],
        measurement_name="AKKU-2026-00001-M-001",
    )
    with patch(
        "app.integrations.erpnext_client.urlopen",
        side_effect=[
            FakeResponse({"data": {"name": "AKKU-2026-00001-M-001"}}),
        ],
    ):
        with pytest.raises(ErpNextError) as exc_info:
            client().create_battery_measurement(payload)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["measurement_name"] == "AKKU-2026-00001-M-001"


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
