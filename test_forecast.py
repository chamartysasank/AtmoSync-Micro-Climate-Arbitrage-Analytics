import numpy as np
import pandas as pd
import pytest
from analytics import engine as E
from analytics.forecast import forecast_risk, forecast_summary, forecast_assumptions, DISCLAIMER


def _inputs(temp, rh=90.0, n=40, slope=0.0, consumed=0.1, hours_to_dest=30.0):
    ts = pd.date_range("2026-01-01", periods=n, freq="15min")
    hrs = np.arange(n) * 0.25
    rd = pd.DataFrame(dict(container_id="C1", reading_ts=ts, temperature_c=temp + slope * hrs, humidity_pct=rh))
    st = pd.DataFrame([dict(container_id="C1", shipment_id="S1", life_consumed_fraction=consumed, hours_to_destination=hours_to_dest, excursion_share=0.0)])
    return rd, st


def test_hold_at_reference_consumes_life_linearly(cfg):
    rd, st = _inputs(7.0)
    fc = forecast_risk(rd, st, cfg); base_h = cfg["quality_model"]["base_shelf_life_days"] * 24
    for h in (6, 12, 24, 48):
        row = fc[(fc.scenario == "hold") & (fc.horizon_h == h)].iloc[0]
        assert row["life_consumed_fraction"] == pytest.approx(0.1 + h / base_h, rel=1e-9)
        assert row["projected_burn_rate"] == pytest.approx(1.0)


def test_horizons_and_scenarios_are_configurable(cfg):
    rd, st = _inputs(7.0)
    c2 = {**cfg, "forecast": {**cfg["forecast"], "horizons_hours": [3, 9], "scenarios": {"hold": cfg["forecast"]["scenarios"]["hold"]}}}
    fc = forecast_risk(rd, st, c2)
    assert sorted(fc["horizon_h"].unique()) == [0, 3, 9] and set(fc["scenario"]) == {"hold"}


def test_warming_trend_raises_risk_and_scenario_ordering(cfg):
    rd, st = _inputs(8.0, slope=0.5, consumed=0.5)                   # +0.5 C/h warming
    fc = forecast_risk(rd, st, cfg).set_index(["scenario", "horizon_h"])
    for h in (6, 12, 24, 48):
        hold, trend, pess = (fc.loc[(s, h), "life_consumed_fraction"] for s in ("hold", "trend", "pessimistic"))
        assert hold < trend <= pess
    assert fc.loc[("trend", 48), "projected_temp_c"] > fc.loc[("trend", 6), "projected_temp_c"] > fc.loc[("hold", 6), "projected_temp_c"]
    assert fc.loc[("trend", 48), "risk_score"] >= fc.loc[("hold", 48), "risk_score"]


def test_projections_are_clipped(cfg):
    rd, st = _inputs(20.0, slope=5.0, n=40)
    fc = forecast_risk(rd, st, cfg)
    assert fc["projected_temp_c"].max() <= cfg["forecast"]["temp_bounds_c"][1]
    assert fc["projected_rh_pct"].between(*cfg["forecast"]["rh_bounds_pct"]).all()


def test_low_humidity_trend_increases_burn(cfg):
    ts = pd.date_range("2026-01-01", periods=40, freq="15min")
    rd = pd.DataFrame(dict(container_id="C1", reading_ts=ts, temperature_c=7.0, humidity_pct=90 - np.arange(40) * 0.5))
    _, st = _inputs(7.0)
    fc = forecast_risk(rd, st, cfg).set_index(["scenario", "horizon_h"])
    assert fc.loc[("trend", 24), "projected_burn_rate"] > fc.loc[("hold", 24), "projected_burn_rate"]


def test_threshold_crossing_time_and_labels(cfg):
    rd, st = _inputs(15.0, consumed=0.8)
    fc = forecast_risk(rd, st, cfg)
    row = fc[(fc.scenario == "hold") & (fc.horizon_h == 48)].iloc[0]
    assert row["below_quality_threshold"] and 0 < row["hours_until_threshold"] <= 48
    assert (fc["evidence_level"] == "HEURISTIC (not validated)").all()
    assert "not a scientifically validated" in DISCLAIMER and "NOT VALIDATED" in forecast_assumptions(cfg)["Evidence level"].str.cat()


def test_insufficient_points_falls_back_to_no_trend(cfg):
    rd, st = _inputs(8.0, slope=1.0, n=4)
    fc = forecast_risk(rd, st, cfg).set_index(["scenario", "horizon_h"])
    assert fc.loc[("trend", 24), "projected_temp_c"] == pytest.approx(fc.loc[("hold", 24), "projected_temp_c"])


def test_sample_data_forecast(cfg, results):
    fc = forecast_risk(results["readings"], results["status"], cfg)
    assert len(fc) == 12 * 3 * 5
    s = forecast_summary(fc, "trend").set_index("container_id")
    assert s.loc["CNT-009", "+6h"] == "CRITICAL" and (s.loc["CNT-001"] == "LOW").all()
    # horizon-0 rows reproduce the 'now' category for the healthy containers
    now = fc[(fc.scenario == "hold") & (fc.horizon_h == 0) & (fc.container_id == "CNT-001")].iloc[0]
    assert now["risk_category"] == "LOW"


def test_engine_helpers_match_container_status(cfg, results):
    r = results["status"].iloc[0]
    assert E.risk_score(r["recent_burn_rate"], r["slack_hours"], r["excursion_share"], r["life_consumed_fraction"], cfg) == pytest.approx(r["risk_score"])
    assert E.risk_category(r["slack_hours"], r["risk_score"], cfg) == r["risk_category"]
    assert E.burn_rate_at(17.0, 90.0, cfg) == pytest.approx(cfg["quality_model"]["q10"])
