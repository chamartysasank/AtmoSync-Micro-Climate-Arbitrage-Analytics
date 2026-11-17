import yaml
from pathlib import Path
from analytics.alerts import build_alerts, send_alerts
from common.config import ROOT


def test_alerts_dry_run(results, cfg):
    msgs = build_alerts(results["recs"], results["status"], cfg)
    assert any("REROUTE" in m for m in msgs)
    assert send_alerts(msgs, cfg)["sent"] is False


def test_dbt_vars_match_settings(cfg):
    v = yaml.safe_load(open(ROOT / "dbt_project" / "dbt_project.yml"))["vars"]
    q, t, r, a, s = cfg["quality_model"], cfg["thresholds"], cfg["risk"], cfg["arbitrage"], cfg["simulator"]
    expected = {"base_shelf_life_days": q["base_shelf_life_days"], "reference_temp_c": q["reference_temp_c"], "q10": q["q10"],
                "chill_floor_c": q["chill_floor_c"], "rh_penalty_per_10pct": q["rh_penalty_per_10pct"], "max_gap_hours": q["max_gap_hours"],
                "recent_window_minutes": q["recent_window_minutes"], "required_retail_shelf_hours": q["required_retail_shelf_hours"],
                "salvage_value_fraction": q["salvage_value_fraction"], "rate_cap": q["rate_cap"], "temp_min_c": t["temp_min_c"],
                "temp_max_c": t["temp_max_c"], "rh_min_pct": t["rh_min_pct"], "rh_max_pct": t["rh_max_pct"],
                "w_burn": r["weights"]["burn"], "w_margin": r["weights"]["margin"], "w_excursion": r["weights"]["excursion"],
                "w_consumed": r["weights"]["consumed"], "slack_scale_hours": r["slack_scale_hours"], "high_slack_hours": r["high_slack_hours"],
                "medium_score": r["medium_score"], "avg_speed_kmph": s["avg_speed_kmph"], "road_factor": s["road_factor"],
                "transport_usd_per_tonne_km": a["transport_usd_per_tonne_km"], "handling_usd_per_kg": a["handling_usd_per_kg"],
                "reroute_fixed_fee_usd": a["reroute_fixed_fee_usd"], "min_benefit_usd": a["min_benefit_usd"], "min_benefit_pct": a["min_benefit_pct"]}
    for k, val in expected.items():
        assert v[k] == val, f"dbt var {k} out of sync with settings.yaml"


def test_hab_adapter_with_handmade_fixture(tmp_path):
    """Fixture is HAND-MADE (3 rows) to test the adapter's logic only - it is NOT real HAB data."""
    from ingestion.hab_prices import load_hab_avocado
    p = tmp_path / "avocado.csv"
    p.write_text("Date,AveragePrice,type,region\n2018-01-07,1.00,conventional,Chicago\n2018-01-07,2.00,organic,Chicago\n2018-01-07,1.10,conventional,SomewhereElse\n")
    out = load_hab_avocado(str(p))
    assert len(out) == 1 and out.iloc[0]["market_id"] == "CHICAGO" and out.iloc[0]["price_modal_usd_kg"] == 3.0
