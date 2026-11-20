"""Shipment Monitoring: per-container temperature / humidity / vibration trends (Phase 1 'Container monitoring' tab)."""
import streamlit as st

TITLE, ORDER = "Shipment Monitoring", 20


def render(ctx):
    rd = ctx["r"]["readings"]
    ids = sorted(rd["container_id"].unique())
    sel = st.multiselect("Containers", ids, default=[c for c in ("CNT-009", "CNT-001") if c in ids], key="mon_sel")
    d = rd[rd["container_id"].isin(sel)]
    if d.empty:
        st.info("Select at least one container."); return
    for m, label in [("temperature_c", "Temperature (°C)"), ("humidity_pct", "Relative humidity (%)"), ("vibration_g", "Vibration (g)")]:
        st.subheader(label); st.line_chart(d.pivot_table(index="reading_ts", columns="container_id", values=m))
