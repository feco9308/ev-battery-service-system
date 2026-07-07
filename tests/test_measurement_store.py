from datetime import datetime, timezone

from app.integrations.measurement_store import LocalMeasurementStore
from app.integrations.models import BatteryCellMeasurement, BatteryMeasurementPayload


def test_local_measurement_store_writes_json(tmp_path) -> None:
    store = LocalMeasurementStore(root=tmp_path)
    payload = BatteryMeasurementPayload(
        repair_job="AKKU-2026-00001",
        measurement_stage="Beérkezéskori mérés",
        test_type="Ellenállásmérés",
        api_measurement_id="MEAS-2026-00001",
        measurement_start=datetime(2026, 7, 1, 14, 30, tzinfo=timezone.utc),
        module_no=1,
        cells=[
            BatteryCellMeasurement(
                module_no=1,
                cell_no=1,
                voltage=3.7,
                internal_resistance=2.1,
            )
        ],
        summary="OK",
    )

    path = store.save(payload)

    assert path.name == "AKKU-2026-00001_MOD01_ELLENÁLLÁSMÉRÉS_BEÉRKEZÉSKORI_MÉRÉS_MEAS-2026-00001.json"
    assert '"repair_job": "AKKU-2026-00001"' in path.read_text(encoding="utf-8")
