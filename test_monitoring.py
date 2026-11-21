import logging
import pandas as pd
import pytest
import run_local
from common import monitoring as M
from common.store import Store

NOW = pd.Timestamp("2026-01-02 12:00")


@pytest.fixture
def st(tmp_path):
    return Store(tmp_path / "m.duckdb")


def test_successful_run_is_recorded(cfg, st):
    with M.PipelineMonitor("demo", st, cfg=cfg) as run:
        logging.getLogger("demo").info("hello monitor")
        with run.step("load") as s: s.metrics(rows_in=10, rows_out=9, message="ok")
        run.record_ingestion({"input_rows": 10, "clean_rows": 9, "rejected_rows": 1, "duplicates_removed": 0}, {"overall_score": 95.0})
    r = M.recent_runs(st).iloc[0]
    assert r["status"] == "SUCCESS" and r["name"] == "demo" and r["duration_s"] >= 0
    s = M.run_steps(r["run_id"], st)
    assert list(s["step"]) == ["load"] and s.iloc[0]["rows_out"] == 9
    assert "hello monitor" in set(M.run_logs(r["run_id"], store=st)["message"])
    assert M.ingestion_history(st).iloc[0]["rejected_rows"] == 1


def test_failed_step_marks_run_failed_and_propagates(cfg, st):
    with pytest.raises(ValueError):
        with M.PipelineMonitor("demo", st, cfg=cfg) as run:
            with run.step("ok"): pass
            with run.step("boom"): raise ValueError("bad data")
    r = M.recent_runs(st).iloc[0]
    assert r["status"] == "FAILED" and "bad data" in r["error_summary"]
    s = M.run_steps(r["run_id"], st).set_index("step")
    assert s.loc["ok", "status"] == "SUCCESS" and s.loc["boom", "status"] == "FAILED"
    es = M.error_summary(st, 24)
    assert es.iloc[0]["kind"] == "step" and "bad data" in es.iloc[0]["message"]


def test_explicit_fail_and_error_log_summary(cfg, st):
    with M.PipelineMonitor("demo", st, cfg=cfg) as run:
        logging.getLogger("demo").error("disk problem")
        logging.getLogger("demo").error("disk problem")
        run.fail("stopped by operator")
    assert M.recent_runs(st).iloc[0]["status"] == "FAILED"
    es = M.error_summary(st, 24)
    assert es[(es.kind == "log")].iloc[0]["count"] == 2
    assert M.run_logs(levels=["ERROR"], store=st)["level"].eq("ERROR").all()


def test_disabled_monitor_writes_nothing(cfg, st):
    with M.PipelineMonitor("demo", st, cfg=cfg, enabled=False) as run:
        with run.step("x"): pass
    assert M.recent_runs(st).empty


def test_persistence_failure_never_breaks_pipeline(cfg, tmp_path, caplog):
    class Broken(Store):
        def upsert_df(self, *a, **k): raise RuntimeError("db locked")
    with M.PipelineMonitor("demo", Broken(tmp_path / "b.duckdb"), cfg=cfg) as run:
        with run.step("x"): pass                                    # must not raise


def test_health_indicators_thresholds(cfg, st):
    empty = M.system_health(cfg, st, NOW).set_index("indicator")
    assert empty.loc["Last pipeline run", "status"] == "WARN" and M.overall_status(empty.reset_index()) == "WARN"
    st.upsert_df("pipeline_runs", pd.DataFrame([dict(run_id="R1", name="x", trigger="t", started_at=NOW - pd.Timedelta(hours=30), finished_at=NOW - pd.Timedelta(hours=30),
                                                      duration_s=1.0, status="SUCCESS", error_summary="")]), ["run_id"])
    h = M.system_health(cfg, st, NOW).set_index("indicator")
    assert h.loc["Last pipeline run", "status"] == "OK" and h.loc["Run age (hours)", "status"] == "WARN"
    st.append_df("ingestion_stats", pd.DataFrame([dict(run_id="R1", recorded_at=NOW, input_rows=100, clean_rows=80, rejected_rows=20, duplicates_removed=0,
                                                       quality_score=60.0, completeness_score=90.0, validity_score=80.0)]))
    h = M.system_health(cfg, st, NOW).set_index("indicator")
    assert h.loc["Ingestion rejection rate (%)", "status"] == "FAIL" and h.loc["Data quality score", "status"] == "FAIL"
    assert M.overall_status(h.reset_index()) == "FAIL"


def test_failed_last_run_and_dbt_indicator(cfg, st):
    st.upsert_df("pipeline_runs", pd.DataFrame([dict(run_id="R2", name="x", trigger="t", started_at=NOW, finished_at=NOW, duration_s=1.0, status="FAILED", error_summary="dbt build failed")]), ["run_id"])
    st.append_df("pipeline_steps", pd.DataFrame([dict(run_id="R2", step="dbt_build", step_order=1, started_at=NOW, duration_s=1.0, status="FAILED", rows_in=None, rows_out=None, message="exit 2")]))
    h = M.system_health(cfg, st, NOW).set_index("indicator")
    assert h.loc["Last pipeline run", "status"] == "FAIL" and h.loc["dbt build (last run)", "status"] == "FAIL" and h.loc["Errors (24 h)", "status"] == "WARN"


def test_purge_old_logs(cfg, st):
    st.append_df("pipeline_logs", pd.DataFrame([dict(ts=NOW - pd.Timedelta(days=40), level="INFO", logger="a", message="old", run_id="R"),
                                                dict(ts=NOW, level="INFO", logger="a", message="new", run_id="R")]))
    assert M.purge_old_logs(st, 30, NOW) == 1 and list(M.run_logs(store=st)["message"]) == ["new"]
    assert M.purge_old_logs(Store(st.db_path.parent / "none.duckdb"), 30) == 0


def test_integration_status_is_presence_only(monkeypatch):
    monkeypatch.delenv("SNOWFLAKE_ACCOUNT", raising=False)
    df = M.integration_status()
    assert df["note"].str.contains("NOT tested").all() and set(df["integration"]) >= {"Kafka bootstrap servers", "Snowflake credentials"}


def test_run_local_records_monitored_run_and_phase2_outputs(monkeypatch):
    class Done: returncode = 0
    monkeypatch.setattr(run_local.subprocess, "run", lambda cmd, **kw: Done())
    monkeypatch.setattr(run_local, "load_local_warehouse", lambda cfg: None)
    monkeypatch.setattr(run_local, "export", lambda cfg: None)
    assert run_local.main([]) == 0
    st = Store(); r = M.recent_runs(st).iloc[0]
    steps = list(M.run_steps(r["run_id"], st)["step"])
    assert r["status"] == "SUCCESS" and steps == ["analytics_pipeline", "load_local_warehouse", "dbt_build", "tableau_export", "slack_email_alerts", "health_history", "quality_summary", "alert_sync"]
    assert len(st.read_table("alerts")) == 13 and len(st.read_table("health_history")) > 100 and len(st.read_table("dq_reports")) == 1
    assert M.ingestion_history(st).iloc[0]["input_rows"] == 819
    assert M.system_health(__import__("common.config", fromlist=["load_settings"]).load_settings(), st).set_index("indicator").loc["dbt build (last run)", "status"] == "OK"


def test_run_local_dbt_failure_is_recorded_as_failed(monkeypatch):
    class Done: returncode = 3
    monkeypatch.setattr(run_local.subprocess, "run", lambda cmd, **kw: Done())
    monkeypatch.setattr(run_local, "load_local_warehouse", lambda cfg: None)
    exported = []; monkeypatch.setattr(run_local, "export", lambda cfg: exported.append(1))
    assert run_local.main([]) == 1 and not exported
    st = Store(); r = M.recent_runs(st).iloc[0]
    assert r["status"] == "FAILED" and "exit code 3" in r["error_summary"]
    assert not st.table_exists("alerts")                         # phase 2 steps did not run after the failed build


def test_run_local_skip_phase2_and_no_monitor(monkeypatch):
    monkeypatch.setattr(run_local, "load_local_warehouse", lambda cfg: None); monkeypatch.setattr(run_local, "export", lambda cfg: None)
    assert run_local.main(["--skip-dbt", "--skip-phase2", "--no-monitor"]) == 0
    assert not Store().table_exists("pipeline_runs") and not Store().table_exists("alerts")
