import math
import pandas as pd
from analytics import engine as E
from analytics.geo import haversine_km


def _readings(temp, rh=90.0, n=5):
    ts = pd.date_range("2026-01-01", periods=n, freq="15min")
    return pd.DataFrame(dict(event_id=range(n), container_id="C1", reading_ts=ts, temperature_c=temp, humidity_pct=rh,
                             vibration_g=0.2, latitude=30.0, longitude=-100.0))


def test_burn_rate_at_reference_is_one(cfg):
    d = E.add_reading_rates(_readings(7.0), cfg)
    assert math.isclose(d["burn_rate"].iloc[0], 1.0, rel_tol=1e-9)


def test_q10_doubles_by_factor(cfg):
    d = E.add_reading_rates(_readings(17.0), cfg)       # +10C
    assert math.isclose(d["burn_rate"].iloc[0], cfg["quality_model"]["q10"], rel_tol=1e-9)


def test_chill_floor_gives_no_bonus(cfg):
    assert E.add_reading_rates(_readings(1.0), cfg)["burn_rate"].iloc[0] == E.add_reading_rates(_readings(5.0), cfg)["burn_rate"].iloc[0]


def test_low_humidity_increases_rate(cfg):
    assert E.add_reading_rates(_readings(7.0, rh=70), cfg)["burn_rate"].iloc[0] > 1.0


def test_gap_is_capped(cfg):
    d = _readings(7.0, n=2); d.loc[1, "reading_ts"] += pd.Timedelta(hours=10)
    assert E.add_reading_rates(d, cfg)["dt_hours"].iloc[1] == cfg["quality_model"]["max_gap_hours"]


def test_haversine_known_distance():
    assert 3930 < haversine_km(40.71, -74.01, 34.05, -118.24) < 3960     # NYC-LA ~3940 km


def test_risk_orders_and_categories(results):
    s = results["status"].set_index("container_id")
    assert s.loc["CNT-009", "risk_category"] == "CRITICAL"
    assert s["risk_score"].between(0, 100).all()
    assert s.loc["CNT-009", "risk_score"] > s.loc["CNT-001", "risk_score"]


def test_reroute_requires_degradation_and_benefit(results):
    r = results["recs"]
    rr = r[r["recommended_action"] == "REROUTE"]
    assert (rr["original_quality_multiplier"] < 1).all() and (rr["best_benefit_usd"] > 0).all()
    # healthy containers never rerouted even when another market pays more
    healthy_pos_benefit = r[(r["risk_category"] == "LOW") & (r["best_benefit_usd"] > 0)]
    assert len(healthy_pos_benefit) > 0 and (healthy_pos_benefit["recommended_action"] == "NO_ACTION").all()


def test_kpis_consistent(results):
    k = results["kpis"].iloc[0]
    assert k["healthy_containers"] + k["at_risk_containers"] == k["total_containers"] == 12
