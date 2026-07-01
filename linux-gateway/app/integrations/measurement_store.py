import json
from pathlib import Path

from .models import BatteryMeasurementPayload


class LocalMeasurementStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(__file__).resolve().parents[2] / "data" / "measurements"

    def save(self, payload: BatteryMeasurementPayload) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        filename = _safe_filename(
            f"{payload.repair_job}_{payload.measurement_type.upper()}_{payload.api_measurement_id}.json"
        )
        path = self.root / filename
        path.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
        return path


def _safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in ("-", "_", ".") else "_" for char in value)
