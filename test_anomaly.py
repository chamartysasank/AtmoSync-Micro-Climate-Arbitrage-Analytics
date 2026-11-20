import numpy as np
import pandas as pd
import pytest
from analytics.anomaly import detect_anomalies, summarize_anomalies, anomaly_kpis


def _frame(n=20, temp=7.0, rh=90.0, vib=0.25, container="C1"):
    ts = pd.date_range("2026-01-01", periods=n, freq="15min")
    rng = np.random.default_rng(0)
    return pd.DataFrame(dict(event_id=[f"{container}-{i}" for i in range(n)], container_id=container, sensor_id="S1", shipment_id="SH1",
                             reading_ts=ts.strftime("%Y-%m-%dT%H:%M:%SZ"), temperature_c=temp + rng.normal(0, 0.1, n),
                             humidity_pct=rh + rng.normal(0, 0.5, n), vibration_g=vib + rng.normal(0, 0.02, n)))


def _types(a, **kw):
    q = a
    for k, v in kw.items(): q = q[q[k] == v]
    return q


def test_clean_data_has_no_anomalies(cfg):
    assert detect_anomalies(_frame(), cfg).empty


def test_temperature_threshold_severity_and_reason(cfg):
    f = _frame(); f.loc[10, "temperature_c"] = 14.5; f.loc[15, "temperature_c"] = 20.0
    a = _types(detect_anomalies(f, cfg), anomaly_type="threshold", metric="temperature_c")
    sev = dict(zip(a["event_id"], a["severity"]))
    assert sev["C1-10"] == "WARNING" and sev["C1-15"] == "CRITICAL"
    assert "above the 13 °C upper limit" in a.set_index("event_id").loc["C1-10", "reason"]


def test_low_temperature_and_humidity_thresholds(cfg):
    f = _frame(); f.loc[8, "temperature_c"] = 4.0; f.loc[9, "humidity_pct"] = 60.0
    a = detect_anomalies(f, cfg)
    assert _types(a, event_id="C1-8", anomaly_type="threshold").iloc[0]["severity"] == "WARNING"
    assert _types(a, event_id="C1-9", anomaly_type="threshold", metric="humidity_pct").iloc[0]["severity"] == "CRITICAL"


def test_vibration_threshold(cfg):
    f = _frame(); f.loc[5, "vibration_g"] = 0.7; f.loc[6, "vibration_g"] = 1.4
    a = _types(detect_anomalies(f, cfg), anomaly_type="threshold", metric="vibration_g")
    assert dict(zip(a["event_id"], a["severity"])) == {"C1-5": "WARNING", "C1-6": "CRITICAL"}


def test_missing_invalid_and_sentinel(cfg):
    f = _frame(); f.loc[3, "temperature_c"] = np.nan; f.loc[4, "temperature_c"] = -999; f.loc[5, "humidity_pct"] = 140; f.loc[6, "vibration_g"] = np.nan
    a = detect_anomalies(f, cfg)
    assert _types(a, event_id="C1-3", anomaly_type="missing_value").shape[0] == 1
    assert "error code" in _types(a, event_id="C1-4", anomaly_type="invalid_reading").iloc[0]["reason"]
    assert "plausible range" in _types(a, event_id="C1-5", anomaly_type="invalid_reading").iloc[0]["reason"]
    assert _types(a, event_id="C1-6", anomaly_type="missing_value", metric="vibration_g").shape[0] == 1
    assert (_types(a, anomaly_type="invalid_reading")["severity"] == cfg["anomaly"]["invalid_severity"]).all()


def test_invalid_timestamp(cfg):
    f = _frame(); f.loc[2, "reading_ts"] = "not-a-date"
    assert _types(detect_anomalies(f, cfg), event_id="C1-2", metric="reading_ts").shape[0] == 1


def test_statistical_spike_within_thresholds(cfg):
    f = _frame(); f.loc[12, "temperature_c"] = 8.6            # inside 5-13 C, but ~16 sigma above baseline
    a = _types(detect_anomalies(f, cfg), event_id="C1-12", anomaly_type="statistical")
    assert len(a) == 1 and a.iloc[0]["severity"] == "CRITICAL" and a.iloc[0]["z_score"] > 5


def test_rate_of_change(cfg):
    f = _frame(); f.loc[10:, "temperature_c"] += 2.0         # +2 C in 15 min = 8 C/h
    a = _types(detect_anomalies(f, cfg), anomaly_type="rate_of_change", metric="temperature_c")
    assert a.iloc[0]["event_id"] == "C1-10" and a.iloc[0]["severity"] == "CRITICAL"


def test_gap_detection(cfg):
    f = _frame().drop(index=range(5, 14)).reset_index(drop=True)       # 9 missing readings = 2.25 h
    a = _types(detect_anomalies(f, cfg), anomaly_type="gap")
    assert len(a) == 1 and a.iloc[0]["severity"] == "CRITICAL" and a.iloc[0]["value"] >= 120


def test_stuck_sensor_reported_once(cfg):
    f = _frame(); f.loc[4:14, "temperature_c"] = 7.0
    a = _types(detect_anomalies(f, cfg), anomaly_type="stuck_sensor", metric="temperature_c")
    assert len(a) == 1


def test_config_overrides_thresholds(cfg):
    f = _frame(); f.loc[10, "temperature_c"] = 13.5
    c2 = {**cfg, "anomaly": {**cfg["anomaly"], "temp_warn_max_c": 14.0}}
    assert _types(detect_anomalies(f, c2), anomaly_type="threshold", event_id="C1-10").empty
    assert not _types(detect_anomalies(f, cfg), anomaly_type="threshold", event_id="C1-10").empty


def test_duplicates_not_double_flagged(cfg):
    f = _frame(); f.loc[10, "temperature_c"] = 20.0
    a = detect_anomalies(pd.concat([f, f.iloc[[10]]], ignore_index=True), cfg)
    assert a["anomaly_id"].is_unique


def test_sample_data_and_summaries(cfg, results):
    a = detect_anomalies(results["raw"], cfg)
    assert set(a.columns) >= {"reason", "severity", "anomaly_type"} and a["reason"].str.len().min() > 10
    s = summarize_anomalies(a)
    assert s.iloc[0]["container_id"] == "CNT-009"                 # compressor-failure container is the worst
    k = anomaly_kpis(a, len(results["raw"]))
    assert k["critical"] + k["warning"] == k["total_anomalies"] == len(a)
    assert a[a["container_id"] == "CNT-001"]["severity"].eq("CRITICAL").sum() == 0   # healthy container: no critical anomalies


def test_empty_input_handled(cfg):
    assert summarize_anomalies(pd.DataFrame(columns=["container_id", "severity", "anomaly_id"])).empty
