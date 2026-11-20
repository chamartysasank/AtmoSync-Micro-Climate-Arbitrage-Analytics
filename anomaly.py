"""Anomaly Detection page (Feature 1)."""
import streamlit as st
from analytics.anomaly import detect_anomalies, summarize_anomalies, anomaly_kpis

TITLE, ORDER = "Anomaly Detection", 30


@st.cache_data(show_spinner=False)
def _anoms(_raw, _cfg_key):
    from common.config import load_settings
    return detect_anomalies(_raw, load_settings())


def render(ctx):
    r, cfg = ctx["r"], ctx["cfg"]
    a = _anoms(r["raw"], str(sorted(cfg["anomaly"].items())))
    st.caption("Flags come from configurable thresholds and simple statistics (config/features/anomaly.yaml). Heuristic, not validated.")
    c1, c2, c3 = st.columns(3)
    sev = c1.multiselect("Severity", ["CRITICAL", "WARNING"], default=["CRITICAL", "WARNING"], key="an_sev")
    cont = c2.multiselect("Container", sorted(a["container_id"].dropna().unique()), key="an_cont")
    typ = c3.multiselect("Type", sorted(a["anomaly_type"].unique()), key="an_typ")
    f = a[a["severity"].isin(sev)]
    if cont: f = f[f["container_id"].isin(cont)]
    if typ: f = f[f["anomaly_type"].isin(typ)]
    k = anomaly_kpis(f, len(r["raw"]))
    cols = st.columns(5)
    for col, (label, key) in zip(cols, [("Anomalies", "total_anomalies"), ("Critical", "critical"), ("Warning", "warning"), ("Containers affected", "containers_affected"), ("Anomalous readings %", "anomaly_rate_pct")]):
        col.metric(label, k[key])
    st.subheader("By container"); st.dataframe(summarize_anomalies(f), use_container_width=True)
    st.subheader("By type"); st.bar_chart(f.groupby(["anomaly_type", "severity"]).size().unstack(fill_value=0))
    st.subheader("Flagged readings (with explanation)")
    st.dataframe(f[["reading_ts", "container_id", "metric", "value", "anomaly_type", "severity", "reason"]], use_container_width=True)
    st.download_button("Download anomalies (CSV)", f.to_csv(index=False), "anomalies.csv", "text/csv")
