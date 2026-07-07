import json
from pathlib import Path

from .models import BatteryMeasurementPayload


class LocalMeasurementStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(__file__).resolve().parents[2] / "data" / "measurements"

    def save(self, payload: BatteryMeasurementPayload) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        module_part = f"_MOD{payload.module_no:02d}" if payload.module_no is not None and payload.module_no > 0 else ""
        filename = _safe_filename(
            f"{payload.repair_job}{module_part}_{payload.test_type.upper()}_{payload.measurement_stage.upper()}_{payload.api_measurement_id}.json"
        )
        path = self.root / filename
        path.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
        return path


def _safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in ("-", "_", ".") else "_" for char in value)
