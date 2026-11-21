"""Alert Centre page (Feature 6)."""
import pandas as pd
import streamlit as st
from analytics.alert_center import (collect_candidates, sync_alerts, acknowledge, resolve, query_alerts, alert_history, alert_counts,
                                    SEVERITIES, STATUSES, CATEGORIES)

TITLE, ORDER = "Alert Centre", 80


def render(ctx):
    r, cfg = ctx["r"], ctx["cfg"]
    st.caption("Alerts are generated from risk, health, anomaly, forecast (heuristic) and arbitrage results and stored in the local database (ops.alerts).")
    if st.button("Run detection and sync alerts", key="al_sync"):
        st.success(f"Sync result: {sync_alerts(collect_candidates(r, cfg))}")
    k = alert_counts()
    cols = st.columns(5)
    for col, (lab, key) in zip(cols, [("Open critical", "open_critical"), ("Open warning", "open_warning"), ("Acknowledged", "acknowledged"), ("Resolved", "resolved"), ("Total", "total")]):
        col.metric(lab, k[key])
    allv = query_alerts()
    if allv.empty:
        st.info("No alerts stored yet. Click 'Run detection and sync alerts'."); return
    c1, c2, c3 = st.columns(3)
    sev = c1.multiselect("Severity", SEVERITIES, default=SEVERITIES, key="al_sev")
    stat = c2.multiselect("Status", STATUSES, default=["OPEN", "ACKNOWLEDGED"], key="al_stat")
    cat = c3.multiselect("Category", CATEGORIES, key="al_cat")
    c4, c5, c6 = st.columns(3)
    ship = c4.multiselect("Shipment", sorted(allv["shipment_id"].dropna().unique()), key="al_ship")
    cont = c5.multiselect("Container", sorted(allv["container_id"].unique()), key="al_cont")
    lo, hi = allv["event_time"].min().to_pydatetime(), allv["event_time"].max().to_pydatetime()
    rng = c6.slider("Event time", lo, hi, (lo, hi), key="al_rng") if lo < hi else (lo, hi)
    f = query_alerts(severities=sev, statuses=stat, categories=cat, shipments=ship, containers=cont, date_from=rng[0], date_to=rng[1])
    st.dataframe(f[["alert_id", "event_time", "container_id", "shipment_id", "category", "severity", "status", "title", "occurrences", "acknowledged_by", "resolved_by"]], use_container_width=True)
    st.subheader("Manage an alert")
    if len(f):
        aid = st.selectbox("Alert", list(f["alert_id"]), format_func=lambda a: f"{a} - {f.set_index('alert_id').loc[a, 'title']}", key="al_pick")
        st.write(f.set_index("alert_id").loc[aid, "message"])
        who = st.text_input("Your name", cfg["alert_center"]["default_actor"], key="al_who"); note = st.text_input("Note", key="al_note")
        b1, b2 = st.columns(2)
        try:
            if b1.button("Acknowledge", key="al_ack"): acknowledge(aid, actor=who, note=note); st.rerun()
            if b2.button("Resolve", key="al_res"): resolve(aid, actor=who, note=note); st.rerun()
        except ValueError as e:
            st.error(str(e))
        st.subheader("History"); st.dataframe(alert_history(alert_id=aid)[["event_ts", "action", "actor", "severity", "note"]], use_container_width=True)
    with st.expander("Full alert history"):
        st.dataframe(alert_history(), use_container_width=True)
    st.download_button("Download alerts (CSV)", allv.to_csv(index=False), "alerts.csv", "text/csv")
