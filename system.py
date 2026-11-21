"""System Monitoring page (Feature 10): pipeline runs, steps, logs, errors, ingestion statistics, health indicators."""
import streamlit as st
from common.monitoring import (recent_runs, run_steps, run_logs, error_summary, ingestion_history, system_health, overall_status, integration_status)

TITLE, ORDER = "System Monitoring", 120
_ICON = {"OK": "🟢", "WARN": "🟠", "FAIL": "🔴", "N/A": "⚪"}


def render(ctx):
    cfg = ctx["cfg"]
    h = system_health(cfg)
    st.subheader(f"Pipeline health: {_ICON[overall_status(h)]} {overall_status(h)}")
    cols = st.columns(4)
    for i, row in enumerate(h.itertuples()):
        cols[i % 4].metric(f"{_ICON[row.status]} {row.indicator}", str(row.value), row.detail or None, delta_color="off")
    st.caption("Records come from `python run_local.py` (or the button below). Nothing is recorded until a run has happened.")
    if st.button("Run local pipeline now (skip dbt)", key="sys_run"):
        import run_local
        with st.spinner("Running..."):
            code = run_local.main(["--skip-dbt"])
        st.success("Run finished") if code == 0 else st.error(f"Run failed with exit code {code}")
        st.rerun()
    runs = recent_runs()
    if runs.empty:
        st.info("No pipeline runs recorded yet."); return
    st.subheader("Recent runs"); st.dataframe(runs, use_container_width=True)
    rid = st.selectbox("Run", list(runs["run_id"]), key="sys_run_id")
    st.subheader("Steps"); st.dataframe(run_steps(rid), use_container_width=True)
    lv = st.multiselect("Log levels", ["INFO", "WARNING", "ERROR", "CRITICAL"], default=["INFO", "WARNING", "ERROR", "CRITICAL"], key="sys_lv")
    st.subheader("Logs"); st.dataframe(run_logs(rid, lv)[["ts", "level", "logger", "message"]], use_container_width=True)
    st.subheader("Error summary (last 24 h)"); es = error_summary()
    st.dataframe(es, use_container_width=True) if len(es) else st.write("No errors recorded.")
    ing = ingestion_history()
    if not ing.empty:
        st.subheader("Ingestion statistics"); st.dataframe(ing, use_container_width=True)
        st.line_chart(ing.set_index("recorded_at")[["input_rows", "clean_rows", "rejected_rows"]])
    with st.expander("Integration configuration (presence check only; live connections NOT tested)"):
        st.dataframe(integration_status(), use_container_width=True)
