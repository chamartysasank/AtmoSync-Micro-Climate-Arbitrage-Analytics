import numpy as np
import pandas as pd
import pytest
from analytics import health as H
from common.store import Store


def _readings(temp=9.0, rh=90.0, vib=0.2, n=30, container="C1"):
    ts = pd.date_range("2026-01-01", periods=n, freq="15min")
    return pd.DataFrame(dict(container_id=container, shipment_id="SH1", reading_ts=ts, temperature_c=temp, humidity_pct=rh, vibration_g=vib))


def test_perfect_conditions_score_100(cfg):
    cur = H.current_health(H.health_timeline(_readings(), cfg))
    assert cur.iloc[0]["health_score"] == 100 and cur.iloc[0]["category"] == "Healthy" and cur.iloc[0]["main_driver"] == "none"


def test_scores_decrease_with_deviation(cfg):
    a = H.current_health(H.health_timeline(_readings(temp=14), cfg)).iloc[0]["health_score"]
    b = H.current_health(H.health_timeline(_readings(temp=17), cfg)).iloc[0]["health_score"]
    assert 100 > a > b


def test_failed_variable_caps_score_and_explains(cfg):
    row = H.current_health(H.health_timeline(_readings(temp=25), cfg)).iloc[0]       # 12 C above range: temp sub-score 0
    assert row["health_score"] <= cfg["health"]["failure_cap"] and row["category"] == "Critical"
    assert row["main_driver"] == "temperature" and "capped" in row["explanation"]


def test_weights_are_configurable(cfg):
    f = _readings(vib=1.5)                                                       # vibration fully penalised
    base = H.current_health(H.health_timeline(f, {**cfg, "health": {**cfg["health"], "failure_floor": -1}})).iloc[0]["health_score"]
    heavy = {**cfg, "health": {**cfg["health"], "failure_floor": -1, "weights": {"temperature": 0.1, "humidity": 0.1, "vibration": 0.8}}}
    assert H.current_health(H.health_timeline(f, heavy)).iloc[0]["health_score"] < base


@pytest.mark.parametrize("score,cat", [(100, "Healthy"), (80, "Healthy"), (79.9, "Warning"), (60, "Warning"), (59.9, "At Risk"), (40, "At Risk"), (39.9, "Critical"), (0, "Critical")])
def test_classification_boundaries(cfg, score, cat):
    assert H.classify_health(score, cfg) == cat


def test_missing_vibration_renormalises_weights(cfg):
    assert H.current_health(H.health_timeline(_readings(vib=np.nan), cfg)).iloc[0]["health_score"] == 100


def test_too_few_readings_gives_no_score(cfg):
    assert H.health_timeline(_readings(n=3), cfg).empty


def test_sample_data_ranking(cfg, results):
    cur = H.current_health(H.health_timeline(results["readings"], cfg)).set_index("container_id")
    assert cur.loc["CNT-009", "category"] == "Critical" and cur.loc["CNT-001", "category"] == "Healthy"
    assert cur["health_score"].between(0, 100).all() and sum(H.health_summary(cur.reset_index()).get(c, 0) for c in H.CATEGORIES) == 12


def test_history_is_hourly_and_persisted_idempotently(cfg, results, tmp_path):
    tl = H.health_timeline(results["readings"], cfg)
    st = Store(tmp_path / "t.duckdb")
    n1 = H.save_health_history(tl, st); n2 = H.save_health_history(tl, st)            # second save must not duplicate
    h = H.load_health_history(st)
    assert n1 == n2 == len(h) and not h.duplicated(["container_id", "as_of_ts"]).any()
    assert h.groupby("container_id")["as_of_ts"].apply(lambda s: s.dt.floor("h").is_unique).all()
    assert set(H.load_health_history(st, ["CNT-009"])["container_id"]) == {"CNT-009"}


def test_store_schema_evolution_and_append(tmp_path):
    st = Store(tmp_path / "s.duckdb")
    assert st.read_table("nope").empty and not st.table_exists("nope")
    st.upsert_df("t", pd.DataFrame({"k": [1, 2], "v": ["a", "b"]}), ["k"])
    st.upsert_df("t", pd.DataFrame({"k": [2, 3], "v": ["B", "c"], "extra": [1.5, 2.5]}), ["k"])     # new column + replace key 2
    df = st.read_table("t").sort_values("k")
    assert list(df["k"]) == [1, 2, 3] and list(df["v"]) == ["a", "B", "c"] and "extra" in df
    st.append_df("t", pd.DataFrame({"k": [9], "v": ["z"]}))
    assert len(st.read_table("t")) == 4
