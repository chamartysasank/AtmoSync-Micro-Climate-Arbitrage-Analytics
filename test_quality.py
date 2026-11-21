import numpy as np
import pandas as pd
import pytest
from ingestion.cleaning import clean_sensor_events
from ingestion.quality import assess_quality, quality_alert_candidates, save_quality_summary
from common.store import Store


def _frame(n=20, container="C1"):
    ts = pd.date_range("2026-01-01", periods=n, freq="15min")
    return pd.DataFrame(dict(event_id=[f"{container}-{i}" for i in range(n)], container_id=container, sensor_id="S1", shipment_id="SH1",
                             reading_ts=ts.strftime("%Y-%m-%dT%H:%M:%SZ"), temperature_c=7.0, humidity_pct=90.0, vibration_g=0.2))


def test_perfect_data_scores_100(cfg):
    r = assess_quality(_frame(), cfg)
    assert r.summary["overall_score"] == pytest.approx(100) and r.summary["status"] == "GOOD" and r.issues.empty
    assert r.by_container.iloc[0]["coverage_pct"] == 100


def test_detects_each_issue_type(cfg):
    f = _frame(); f.loc[2, "temperature_c"] = np.nan; f.loc[3, "temperature_c"] = -999; f.loc[4, "humidity_pct"] = 150
    f = pd.concat([f, f.iloc[[10]]], ignore_index=True)
    s = assess_quality(f, cfg).summary
    assert (s["missing_values"], s["invalid_readings"], s["out_of_range"], s["duplicates"]) == (1, 1, 1, 1)
    assert s["rejected_rows"] == 3 and s["validity_score"] == pytest.approx(100 * (1 - 3 / 21))
    assert s["uniqueness_score"] == pytest.approx(100 * (1 - 1 / 21))


def test_gap_reduces_coverage_and_completeness(cfg):
    f = _frame().drop(index=range(5, 11)).reset_index(drop=True)                 # 6 readings missing
    r = assess_quality(f, cfg); c = r.by_container.iloc[0]
    assert c["expected_readings"] == 20 and c["unique_readings"] == 14 and c["coverage_pct"] == pytest.approx(70)
    assert r.summary["missing_readings"] == 6 and r.summary["completeness_score"] < 100
    assert any("coverage" in x for x in r.issues["finding"])


def test_stale_container_hurts_timeliness(cfg):
    f = pd.concat([_frame(20, "C1"), _frame(4, "C2")], ignore_index=True)        # C2 stops 4 h earlier
    r = assess_quality(f, cfg)
    assert r.summary["stale_containers"] == 1 and r.summary["timeliness_score"] == pytest.approx(50)
    assert bool(r.by_container.set_index("container_id").loc["C2", "stale"])


def test_agrees_with_cleaning_on_sample_data(cfg, results):
    r = results["quality"]; stats = clean_sensor_events(results["raw"], cfg)[2]
    assert r.summary["rejected_rows"] == stats["rejected_rows"] and r.summary["duplicates"] == stats["duplicates_removed"]
    assert r.summary["rows"] == len(results["raw"]) == 819
    assert 90 < r.summary["overall_score"] < 100 and r.by_container.iloc[0]["container_id"] == "CNT-012"   # sensor-dropout container is worst


def test_weights_configurable(cfg):
    f = _frame(); f.loc[1:6, "temperature_c"] = -999
    base = assess_quality(f, cfg).summary["overall_score"]
    c2 = {**cfg, "data_quality": {**cfg["data_quality"], "weights": {"completeness": 0.1, "validity": 0.1, "uniqueness": 0.1, "timeliness": 0.7}}}
    assert assess_quality(f, c2).summary["overall_score"] > base


def test_report_files(cfg, tmp_path):
    r = assess_quality(_frame(), cfg); paths = r.save(tmp_path)
    assert {p.name for p in paths} == {"data_quality_report.md", "quality_by_container.csv", "quality_by_field.csv", "quality_issues.csv"}
    assert "Overall score: 100.0/100" in (tmp_path / "data_quality_report.md").read_text()


def test_alert_candidates_and_alert_centre_integration(cfg, tmp_path, results):
    f = _frame(); f.loc[1:12, "temperature_c"] = -999
    rep = assess_quality(f, cfg); cand = quality_alert_candidates(rep, cfg)
    assert {"SYSTEM", "C1"} <= set(cand["container_id"]) and set(cand["category"]) == {"data_quality"}
    assert quality_alert_candidates(assess_quality(_frame(), cfg), cfg).empty
    from analytics import alert_center as A
    st = Store(tmp_path / "q.duckdb")
    assert A.sync_alerts(A.collect_candidates(results, cfg, extra=cand), st)["created"] > 2
    assert (st.read_table("alerts")["category"] == "data_quality").sum() == 2


def test_history_persistence(cfg, tmp_path):
    st = Store(tmp_path / "h.duckdb"); r = assess_quality(_frame(), cfg)
    save_quality_summary(r, st, run_ts="2026-01-01 00:00"); save_quality_summary(r, st, run_ts="2026-01-02 00:00")
    assert len(st.read_table("dq_reports")) == 2


def test_missing_optional_columns_do_not_crash(cfg):
    f = _frame().drop(columns=["vibration_g", "shipment_id"])
    r = assess_quality(f, cfg)
    assert r.summary["missing_values"] == 40 and r.summary["validity_score"] == 0 and (r.issues["severity"] == "CRITICAL").any()
