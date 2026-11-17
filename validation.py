"""Lightweight event validation used by producer and consumer (no external schema lib)."""
from __future__ import annotations

REQUIRED = {"event_id": str, "container_id": str, "sensor_id": str, "shipment_id": str, "reading_ts": str}
NUMERIC = ["temperature_c", "humidity_pct", "vibration_g", "latitude", "longitude"]


def validate_event(ev: dict) -> list[str]:
    """Return a list of problems (empty list = valid). Nulls in numeric fields are allowed here and
    handled later by the cleaning layer; wrong types or missing keys are not."""
    problems = []
    for k, t in REQUIRED.items():
        if k not in ev or ev[k] in (None, ""):
            problems.append(f"missing:{k}")
        elif not isinstance(ev[k], t):
            problems.append(f"type:{k}")
    for k in NUMERIC:
        v = ev.get(k)
        if v is not None and not isinstance(v, (int, float)):
            problems.append(f"type:{k}")
    return problems
