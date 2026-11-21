import numpy as np
import pandas as pd
import pytest
from simulator import lab as L
from common.config import abs_path


@pytest.fixture(scope="module")
def loc(cfg):
    return pd.read_csv(abs_path(cfg["paths"]["sample_dir"]) / "locations.csv")


def test_presets_resolution_and_overrides(cfg):
    p = L.resolve_params("cooling_drift", cfg, progress=0.7, seed=1)
    assert p["progress"] == 0.7 and p["drift"]["rate_c_per_h"] == 0.7 and p["preset"] == "cooling_drift"
    with pytest.raises(KeyError): L.resolve_params("nope", cfg)
    with pytest.raises(KeyError): L.resolve_params("normal", cfg, bogus=1)
    assert L.resolve_params("normal", cfg)["drift"] is None


def test_simulation_is_reproducible_and_schema_compatible(cfg, loc):
    p = L.resolve_params("normal", cfg)
    a, ship = L.simulate_container(p, loc, cfg); b, _ = L.simulate_container(p, loc, cfg)
    assert a.equals(b) and a["source"].eq("SIMULATED (lab)").all()
    assert {"event_id", "container_id", "sensor_id", "shipment_id", "reading_ts", "temperature_c", "humidity_pct", "vibration_g"} <= set(a.columns)
    assert ship.iloc[0]["planned_destination_id"] == "CHICAGO" and not a["event_id"].duplicated().any()
    assert not a.equals(L.simulate_container({**p, "seed": 99}, loc, cfg)[0])


def test_normal_scenario_stays_near_setpoint(cfg, loc):
    raw, _ = L.simulate_container(L.resolve_params("normal", cfg), loc, cfg)
    assert abs(raw["temperature_c"].mean() - cfg["simulator"]["setpoint_temp_c"]) < 0.2 and raw["temperature_c"].max() < 9


def test_temperature_spike_is_local_and_has_requested_size(cfg, loc):
    n, _ = L.simulate_container(L.resolve_params("normal", cfg), loc, cfg)
    s, _ = L.simulate_container(L.resolve_params("temperature_spike", cfg), loc, cfg)
    diff = s["temperature_c"] - n["temperature_c"]                 # identical noise => difference is exactly the spike
    assert diff.max() == pytest.approx(8.0, abs=0.35) and (diff > 0.5).sum() < len(diff) * 0.2 and diff.iloc[0] < 0.01 and diff.iloc[-1] < 0.5


def test_drift_humidity_and_vibration_effects(cfg, loc):
    n, _ = L.simulate_container(L.resolve_params("normal", cfg), loc, cfg)
    d, _ = L.simulate_container(L.resolve_params("compressor_failure", cfg), loc, cfg)
    assert d["temperature_c"].iloc[-1] - n["temperature_c"].iloc[-1] > 8
    lo, _ = L.simulate_container(L.resolve_params("low_humidity", cfg), loc, cfg)
    assert lo["humidity_pct"].iloc[-1] < n["humidity_pct"].iloc[-1] - 5
    fl, _ = L.simulate_container(L.resolve_params("humidity_fluctuation", cfg), loc, cfg)
    assert fl["humidity_pct"].std() > n["humidity_pct"].std() * 2
    vb, _ = L.simulate_container(L.resolve_params("vibration_anomaly", cfg), loc, cfg)
    assert vb["vibration_g"].max() > n["vibration_g"].max() * 2.5


def test_compare_scenarios_normal_vs_abnormal(cfg, loc):
    c = L.compare_scenarios(L.resolve_params("normal", cfg), L.resolve_params("compressor_failure", cfg), loc, cfg)
    t = c["table"].set_index("metric")
    assert t.loc["risk_category", "normal"] == "LOW" and t.loc["risk_category", "abnormal"] in ("MEDIUM", "HIGH", "CRITICAL")
    assert t.loc["health_score", "abnormal"] < t.loc["health_score", "normal"] and t.loc["anomalies_total", "normal"] == 0 < t.loc["anomalies_total", "abnormal"]
    assert t.loc["max_temp_c", "difference"] > 8 and t.loc["recent_burn_rate", "difference"] > 1


def test_route_progress_changes_trip_length(cfg, loc):
    a, _ = L.simulate_container(L.resolve_params("normal", cfg, progress=0.3), loc, cfg); b, _ = L.simulate_container(L.resolve_params("normal", cfg, progress=0.6), loc, cfg)
    assert len(b) > len(a)


def test_replay_status_uses_only_past_data(cfg, loc, results):
    ship = pd.read_csv(abs_path(cfg["paths"]["sample_dir"]) / "shipments.csv"); rd = results["readings"]
    mid = rd["reading_ts"].min() + (rd["reading_ts"].max() - rd["reading_ts"].min()) / 2
    early = L.replay_status_at(rd, ship, loc, cfg, mid).set_index("container_id"); end = L.replay_status_at(rd, ship, loc, cfg, rd["reading_ts"].max()).set_index("container_id")
    assert (early["as_of_ts"] <= mid).all() and early.loc["CNT-009", "life_consumed_fraction"] < end.loc["CNT-009", "life_consumed_fraction"]
    full = results["status"].set_index("container_id")
    assert end.loc["CNT-009", "risk_score"] == pytest.approx(full.loc["CNT-009", "risk_score"])        # final replay frame == normal result
    assert L.replay_status_at(rd, ship, loc, cfg, rd["reading_ts"].min() - pd.Timedelta(days=1)).empty


def test_replay_timeline_shows_deterioration(cfg, loc, results):
    ship = pd.read_csv(abs_path(cfg["paths"]["sample_dir"]) / "shipments.csv")
    tl = L.replay_timeline(results["readings"], ship, loc, cfg, 4.0)
    x = tl[tl.container_id == "CNT-009"].sort_values("replay_ts")
    assert x["risk_score"].iloc[-1] > x["risk_score"].iloc[0] and x["replay_ts"].is_monotonic_increasing


def test_compare_containers(results):
    t = L.compare_containers(results["readings"], results["status"], "CNT-001", "CNT-009").set_index("metric")
    assert t.loc["risk_category", "CNT-001"] == "LOW" and t.loc["risk_category", "CNT-009"] == "CRITICAL" and t.loc["max_temp_c", "CNT-009"] > t.loc["max_temp_c", "CNT-001"]
