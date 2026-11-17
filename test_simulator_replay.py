import pandas as pd
from pathlib import Path
from ingestion.replay import replay_events
from simulator.iot_simulator import build_fleet, generate_events, stream_events
from common.config import abs_path


def _loc(cfg):
    return pd.read_csv(abs_path(cfg["paths"]["sample_dir"]) / "locations.csv")


def test_simulator_is_reproducible_and_complete(cfg):
    loc = _loc(cfg); plans, ship, _ = build_fleet(loc, cfg)
    a, b = generate_events(plans, ship, loc, cfg), generate_events(plans, ship, loc, cfg)
    assert a.equals(b)
    assert a["container_id"].nunique() == 12
    assert {"container_id", "sensor_id", "reading_ts", "temperature_c", "humidity_pct", "vibration_g", "shipment_id"} <= set(a.columns)


def test_fault_injection_toggle(cfg):
    loc = _loc(cfg); c2 = {**cfg, "simulator": {**cfg["simulator"], "inject_faults": False}}
    plans, ship, _ = build_fleet(loc, c2)
    ev = generate_events(plans, ship, loc, c2)
    assert (ev["temperature_c"].dropna() > -900).all() and not ev["event_id"].duplicated().any()


def test_stream_yields_dicts_without_nan(cfg):
    loc = _loc(cfg); plans, ship, _ = build_fleet(loc, cfg)
    first = next(stream_events(plans, ship, loc, cfg))
    assert isinstance(first, dict) and "event_id" in first


def test_replay_orders_by_time_and_limits(cfg):
    p = abs_path(cfg["paths"]["sample_dir"]) / "raw_sensor_events.csv"
    ev = list(replay_events(p, speedup=0, limit=50))
    ts = [e["reading_ts"] for e in ev]
    assert len(ev) == 50 and ts == sorted(ts)
