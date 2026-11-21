import pandas as pd
import pytest
from analytics import alert_center as A
from common.store import Store

T0 = pd.Timestamp("2026-01-01 10:00")


def _cand(cont="C1", cat="risk", sev="WARNING", title="t", msg="m", ship="S1"):
    return pd.DataFrame([dict(container_id=cont, shipment_id=ship, category=cat, severity=sev, title=title, message=msg, event_time=T0)])


@pytest.fixture
def st(tmp_path):
    return Store(tmp_path / "a.duckdb")


def test_create_and_idempotent_resync(st):
    assert A.sync_alerts(_cand(), st, now=T0)["created"] == 1
    s = A.sync_alerts(_cand(), st, now=T0 + pd.Timedelta(hours=1))
    assert s["created"] == 0 and s["updated"] == 1
    df = st.read_table("alerts")
    assert len(df) == 1 and df.iloc[0]["occurrences"] == 2 and df.iloc[0]["status"] == "OPEN"
    assert A.alert_id_for("C1", "risk") == df.iloc[0]["alert_id"]


def test_ack_resolve_lifecycle_and_history(st):
    A.sync_alerts(_cand(), st, now=T0); aid = A.alert_id_for("C1", "risk")
    A.acknowledge(aid, st, "alice", "looking", now=T0 + pd.Timedelta(minutes=5))
    row = st.read_table("alerts").iloc[0]
    assert row["status"] == "ACKNOWLEDGED" and row["acknowledged_by"] == "alice"
    A.resolve(aid, st, "bob", "fixed cooling", now=T0 + pd.Timedelta(minutes=30))
    row = st.read_table("alerts").iloc[0]
    assert row["status"] == "RESOLVED" and row["resolved_by"] == "bob" and row["resolution_note"] == "fixed cooling"
    assert list(A.alert_history(st, aid)["action"]) == ["CREATED", "ACKNOWLEDGED", "RESOLVED"]


def test_invalid_transitions_and_unknown(st):
    A.sync_alerts(_cand(), st, now=T0); aid = A.alert_id_for("C1", "risk")
    with pytest.raises(KeyError): A.acknowledge("AL-NOPE", st)
    A.resolve(aid, st, now=T0)
    with pytest.raises(ValueError): A.acknowledge(aid, st)
    with pytest.raises(ValueError): A.resolve(aid, st)


def test_resolve_directly_from_open(st):
    A.sync_alerts(_cand(), st, now=T0); A.resolve(A.alert_id_for("C1", "risk"), st, now=T0)
    assert st.read_table("alerts").iloc[0]["status"] == "RESOLVED"


def test_escalation_resets_acknowledgement(st):
    A.sync_alerts(_cand(sev="WARNING"), st, now=T0); aid = A.alert_id_for("C1", "risk"); A.acknowledge(aid, st, now=T0)
    s = A.sync_alerts(_cand(sev="CRITICAL"), st, now=T0 + pd.Timedelta(hours=1))
    row = st.read_table("alerts").iloc[0]
    assert s["escalated"] == 1 and row["severity"] == "CRITICAL" and row["status"] == "OPEN"
    assert "ESCALATED" in set(A.alert_history(st, aid)["action"])
    A.sync_alerts(_cand(sev="WARNING"), st, now=T0 + pd.Timedelta(hours=2))               # de-escalation does not lower severity
    assert st.read_table("alerts").iloc[0]["severity"] == "CRITICAL"


def test_reopen_after_resolution(st):
    A.sync_alerts(_cand(), st, now=T0); aid = A.alert_id_for("C1", "risk"); A.resolve(aid, st, now=T0)
    s = A.sync_alerts(_cand(), st, now=T0 + pd.Timedelta(hours=3))
    assert s["reopened"] == 1 and st.read_table("alerts").iloc[0]["status"] == "OPEN"


def test_condition_cleared_when_not_redetected(st):
    A.sync_alerts(pd.concat([_cand(), _cand(cont="C2")]), st, now=T0)
    s = A.sync_alerts(_cand(), st, now=T0 + pd.Timedelta(hours=1))
    df = st.read_table("alerts").set_index("container_id")
    assert s["cleared"] == 1 and not df.loc["C2", "condition_active"] and df.loc["C1", "condition_active"] and df.loc["C2", "status"] == "OPEN"


def test_filtering(st):
    cands = pd.concat([_cand("C1", "risk", "CRITICAL", ship="S1"), _cand("C2", "health", "WARNING", ship="S2"), _cand("C3", "anomaly", "WARNING", ship="S3")], ignore_index=True)
    cands.loc[2, "event_time"] = T0 + pd.Timedelta(days=2)
    A.sync_alerts(cands, st, now=T0); A.acknowledge(A.alert_id_for("C2", "health"), st, now=T0)
    assert list(A.query_alerts(st)["container_id"])[0] == "C1"                                   # most severe first
    assert set(A.query_alerts(st, severities=["WARNING"])["container_id"]) == {"C2", "C3"}
    assert set(A.query_alerts(st, statuses=["ACKNOWLEDGED"])["container_id"]) == {"C2"}
    assert set(A.query_alerts(st, shipments=["S3"])["container_id"]) == {"C3"}
    assert set(A.query_alerts(st, categories=["risk", "health"])["container_id"]) == {"C1", "C2"}
    assert set(A.query_alerts(st, date_from=T0 + pd.Timedelta(days=1))["container_id"]) == {"C3"}
    assert set(A.query_alerts(st, date_to=T0 + pd.Timedelta(days=1))["container_id"]) == {"C1", "C2"}
    assert A.alert_counts(st) == dict(open_critical=1, open_warning=1, acknowledged=1, resolved=0, total=3)


def test_empty_store_queries(st):
    assert A.query_alerts(st).empty and A.alert_history(st).empty and A.alert_counts(st)["total"] == 0


def test_candidates_from_sample_data(cfg, results):
    c = A.collect_candidates(results, cfg)
    assert set(c["category"]) == {"risk", "health", "anomaly", "forecast", "arbitrage"} and set(c["severity"]) <= {"WARNING", "CRITICAL"}
    assert len(c[(c.container_id == "CNT-009") & (c.category == "risk")]) == 1
    assert c[c.container_id == "CNT-001"].empty                                                  # healthy container raises nothing


def test_thresholds_are_configurable(cfg, results):
    base = A.collect_candidates(results, cfg)
    strict = {**cfg, "alert_center": {**cfg["alert_center"], "health": {"warning_below": 101, "critical_below": 40}}}
    assert len(A.collect_candidates(results, strict).query("category == 'health'")) == 12 > len(base.query("category == 'health'"))
    off = {**cfg, "alert_center": {**cfg["alert_center"], "arbitrage": {"enabled": False}}}
    assert A.collect_candidates(results, off).query("category == 'arbitrage'").empty


def test_extra_candidates_are_merged(cfg, results):
    extra = _cand("SYSTEM", "data_quality", "WARNING", "Quality score low")
    c = A.collect_candidates(results, cfg, extra=extra)
    assert (c["category"] == "data_quality").sum() == 1
