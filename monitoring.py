"""System monitoring (Feature 10): pipeline run / step / log / ingestion-statistics recording and health indicators.

Records are buffered in memory and written ONCE at the end of a run (tables in schema `ops`: pipeline_runs, pipeline_steps,
pipeline_logs, ingestion_stats).  No database connection is held while external tools (e.g. dbt) run, so they can use the same file.
"""
from __future__ import annotations
import logging, os, time, uuid
from contextlib import contextmanager
import pandas as pd
from common.store import Store

_NOW = lambda: pd.Timestamp.now("UTC").tz_localize(None)


class _BufferHandler(logging.Handler):
    def __init__(self, level):
        super().__init__(level); self.rows = []

    def emit(self, record):
        self.rows.append(dict(ts=pd.Timestamp(record.created, unit="s"), level=record.levelname, logger=record.name, message=record.getMessage()[:2000]))


class _Step:
    def __init__(self): self.rows_in = self.rows_out = None; self.message = ""
    def metrics(self, rows_in=None, rows_out=None, message=""):
        self.rows_in, self.rows_out, self.message = rows_in, rows_out, message


class PipelineMonitor:
    """with PipelineMonitor('run_local', store) as run:  with run.step('load') as s: s.metrics(rows_out=10)"""
    def __init__(self, name: str, store: Store | None = None, trigger: str = "cli", cfg: dict | None = None, enabled: bool = True):
        self.name, self.trigger, self.enabled = name, trigger, enabled
        self.store = store or Store(); self.run_id = f"RUN-{_NOW():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:6]}"
        self.status, self.error_summary = "SUCCESS", ""; self.steps, self.ingestion = [], []
        level = getattr(logging, ((cfg or {}).get("monitoring", {}).get("log_level_capture", "INFO")), logging.INFO)
        self._handler = _BufferHandler(level)

    def __enter__(self):
        self.started = _NOW(); self._t0 = time.perf_counter()
        if self.enabled:
            logging.getLogger().addHandler(self._handler)
            if logging.getLogger().level > self._handler.level or logging.getLogger().level == logging.NOTSET:
                logging.getLogger().setLevel(min(self._handler.level, logging.getLogger().level or logging.INFO))
        return self

    def fail(self, message: str) -> None:
        self.status, self.error_summary = "FAILED", message[:1000]

    @contextmanager
    def step(self, name: str):
        s = _Step(); t0 = time.perf_counter(); started = _NOW(); status = "SUCCESS"
        try:
            yield s
        except Exception as e:                                        # record, then propagate
            status, s.message = "FAILED", f"{type(e).__name__}: {e}"[:1000]; self.fail(s.message); raise
        finally:
            self.steps.append(dict(run_id=self.run_id, step=name, step_order=len(self.steps) + 1, started_at=started, duration_s=round(time.perf_counter() - t0, 3),
                                   status=status, rows_in=s.rows_in, rows_out=s.rows_out, message=s.message))

    def record_ingestion(self, cleaning_stats: dict, quality_summary: dict | None = None) -> None:
        q = quality_summary or {}
        self.ingestion.append(dict(run_id=self.run_id, recorded_at=_NOW(), input_rows=int(cleaning_stats.get("input_rows", 0)), clean_rows=int(cleaning_stats.get("clean_rows", 0)),
                                   rejected_rows=int(cleaning_stats.get("rejected_rows", 0)), duplicates_removed=int(cleaning_stats.get("duplicates_removed", 0)),
                                   quality_score=float(q.get("overall_score", float("nan"))), completeness_score=float(q.get("completeness_score", float("nan"))),
                                   validity_score=float(q.get("validity_score", float("nan")))))

    def __exit__(self, exc_type, exc, tb):
        logging.getLogger().removeHandler(self._handler)
        if exc_type is not None:
            self.fail(f"{exc_type.__name__}: {exc}")
        if not self.enabled:
            return False
        finished = _NOW()
        try:
            self.store.upsert_df("pipeline_runs", pd.DataFrame([dict(run_id=self.run_id, name=self.name, trigger=self.trigger, started_at=self.started, finished_at=finished,
                                 duration_s=round(time.perf_counter() - self._t0, 3), status=self.status, error_summary=self.error_summary)]), ["run_id"])
            if self.steps: self.store.append_df("pipeline_steps", pd.DataFrame(self.steps))
            if self._handler.rows: self.store.append_df("pipeline_logs", pd.DataFrame(self._handler.rows).assign(run_id=self.run_id))
            if self.ingestion: self.store.append_df("ingestion_stats", pd.DataFrame(self.ingestion))
        except Exception as e:                                       # monitoring must never break the pipeline
            logging.getLogger(__name__).warning("could not persist monitoring data: %s", e)
        return False                                                 # never swallow the pipeline's own exception


# --------------------------------------------------------------------------------------- queries
def recent_runs(store: Store | None = None, limit: int = 20) -> pd.DataFrame:
    df = (store or Store()).read_table("pipeline_runs")
    return df.sort_values("started_at", ascending=False).head(limit).reset_index(drop=True) if not df.empty else df


def run_steps(run_id: str, store: Store | None = None) -> pd.DataFrame:
    df = (store or Store()).read_table("pipeline_steps")
    return df[df["run_id"] == run_id].sort_values("step_order").reset_index(drop=True) if not df.empty else df


def run_logs(run_id: str | None = None, levels: list[str] | None = None, store: Store | None = None) -> pd.DataFrame:
    df = (store or Store()).read_table("pipeline_logs")
    if df.empty: return df
    if run_id: df = df[df["run_id"] == run_id]
    if levels: df = df[df["level"].isin(levels)]
    return df.sort_values("ts").reset_index(drop=True)


def error_summary(store: Store | None = None, hours: float = 24, now=None) -> pd.DataFrame:
    """ERROR/CRITICAL log lines and failed steps in the window, grouped by source and message."""
    store = store or Store(); since = (pd.Timestamp(now) if now is not None else _NOW()) - pd.Timedelta(hours=hours); rows = []
    lg = store.read_table("pipeline_logs")
    if not lg.empty:
        e = lg[lg["level"].isin(["ERROR", "CRITICAL"]) & (lg["ts"] >= since)]
        rows += [dict(source=r.logger, message=r.message, kind="log") for r in e.itertuples()]
    st = store.read_table("pipeline_steps")
    if not st.empty:
        f = st[(st["status"] == "FAILED") & (st["started_at"] >= since)]
        rows += [dict(source=r.step, message=r.message, kind="step") for r in f.itertuples()]
    if not rows: return pd.DataFrame(columns=["kind", "source", "message", "count"])
    return pd.DataFrame(rows).groupby(["kind", "source", "message"]).size().reset_index(name="count").sort_values("count", ascending=False).reset_index(drop=True)


def ingestion_history(store: Store | None = None) -> pd.DataFrame:
    df = (store or Store()).read_table("ingestion_stats")
    return df.sort_values("recorded_at").reset_index(drop=True) if not df.empty else df


def purge_old_logs(store: Store | None = None, days: int = 30, now=None) -> int:
    store = store or Store(); cutoff = (pd.Timestamp(now) if now is not None else _NOW()) - pd.Timedelta(days=days)
    if not store.table_exists("pipeline_logs"): return 0
    n = store.read("select count(*) n from ops.pipeline_logs where ts < ?", [cutoff]).iloc[0, 0]
    store.execute("delete from ops.pipeline_logs where ts < ?", [cutoff]); return int(n)


def integration_status() -> pd.DataFrame:
    """Configuration presence only - NO live connection is attempted here."""
    def importable(m):
        try:
            __import__(m); return True
        except ImportError:
            return False
    rows = [("Kafka client library", "installed" if importable("confluent_kafka") else "not installed", "OK" if importable("confluent_kafka") else "N/A"),
            ("Kafka bootstrap servers", os.getenv("KAFKA_BOOTSTRAP_SERVERS", "default localhost:9092 (not verified)"), "N/A"),
            ("Snowflake connector", "installed" if importable("snowflake.connector") else "not installed", "OK" if importable("snowflake.connector") else "N/A"),
            ("Snowflake credentials", "set" if all(os.getenv(k) for k in ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD")) else "not set (local mode)", "OK" if os.getenv("SNOWFLAKE_ACCOUNT") else "N/A")]
    return pd.DataFrame(rows, columns=["integration", "configuration", "status"]).assign(note="presence check only - live connection NOT tested")


def system_health(cfg: dict, store: Store | None = None, now=None) -> pd.DataFrame:
    """Pipeline health indicators with OK / WARN / FAIL status (thresholds in config/features/monitoring.yaml)."""
    m = cfg["monitoring"]; store = store or Store(); now = pd.Timestamp(now) if now is not None else _NOW(); rows = []
    add = lambda name, status, value, detail="": rows.append(dict(indicator=name, status=status, value=value, detail=detail))
    runs = store.read_table("pipeline_runs")
    if runs.empty:
        add("Last pipeline run", "WARN", "none recorded", "run `python run_local.py`")
        add("Run age", "WARN", "n/a")
    else:
        last = runs.sort_values("started_at").iloc[-1]
        add("Last pipeline run", "OK" if last["status"] == "SUCCESS" else "FAIL", f"{last['status']} ({last['run_id']})", last["error_summary"] or f"{last['duration_s']:.1f} s")
        age = (now - last["finished_at"]).total_seconds() / 3600
        add("Run age (hours)", "OK" if age <= m["max_run_age_hours"] else "WARN", round(age, 1), f"limit {m['max_run_age_hours']} h")
        steps = store.read_table("pipeline_steps"); d = steps[(steps["run_id"] == last["run_id"]) & (steps["step"] == "dbt_build")] if not steps.empty else steps
        add("dbt build (last run)", "N/A" if d.empty else ("OK" if d.iloc[0]["status"] == "SUCCESS" else "FAIL"), "not run" if d.empty else d.iloc[0]["status"])
    errs = error_summary(store, 24, now)["count"].sum() if not error_summary(store, 24, now).empty else 0
    add("Errors (24 h)", "FAIL" if errs >= m["error_fail_count"] else "WARN" if errs >= m["error_warn_count"] else "OK", int(errs))
    ing = store.read_table("ingestion_stats")
    if ing.empty:
        add("Ingestion rejection rate", "N/A", "no data")
        add("Data quality score", "N/A", "no data")
    else:
        li = ing.sort_values("recorded_at").iloc[-1]; rej = 100 * li["rejected_rows"] / max(li["input_rows"], 1)
        add("Ingestion rejection rate (%)", "FAIL" if rej >= m["rejection_fail_pct"] else "WARN" if rej >= m["rejection_warn_pct"] else "OK", round(rej, 2), f"{int(li['rejected_rows'])} of {int(li['input_rows'])} rows")
        q, dq = li["quality_score"], cfg["data_quality"]
        add("Data quality score", "N/A" if pd.isna(q) else "FAIL" if q < dq["critical_below"] else "WARN" if q < dq["warning_below"] else "OK", "n/a" if pd.isna(q) else round(q, 1))
    al = store.read_table("alerts")
    oc = int(((al["status"] == "OPEN") & (al["severity"] == "CRITICAL")).sum()) if not al.empty else 0
    add("Open critical alerts", "WARN" if oc else "OK", oc, "see Alert Centre")
    return pd.DataFrame(rows)


def overall_status(health: pd.DataFrame) -> str:
    s = set(health["status"]); return "FAIL" if "FAIL" in s else "WARN" if "WARN" in s else "OK"
