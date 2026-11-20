"""Shipment Health page (Feature 2)."""
import pandas as pd
import streamlit as st
from analytics.health import health_timeline, current_health, health_summary, save_health_history, load_health_history, CATEGORIES

TITLE, ORDER = "Shipment Health", 40


@st.cache_data(show_spinner=False)
def _timeline(_readings, _key):
    from common.config import load_settings
    return health_timeline(_readings, load_settings())


def render(ctx):
    r, cfg = ctx["r"], ctx["cfg"]
    tl = _timeline(r["readings"], str(cfg["health"]) + str(cfg["thresholds"]))
    cur = current_health(tl)
    st.caption("Condition score 0-100 over the trailing window (config/features/health.yaml). A heuristic, explainable score — not a spoilage prediction.")
    cats = st.multiselect("Category", CATEGORIES, default=CATEGORIES, key="hl_cats")
    f = cur[cur["category"].isin(cats)]
    s = health_summary(cur)
    cols = st.columns(5)
    for col, c in zip(cols, CATEGORIES):
        col.metric(c, s[c])
    cols[4].metric("Average score", s["average_score"])
    st.subheader("Current health (worst first)")
    st.dataframe(f[["container_id", "shipment_id", "health_score", "category", "temperature_score", "humidity_score", "vibration_score", "main_driver", "explanation"]].round(1), use_container_width=True)
    st.subheader("Health trend")
    ids = st.multiselect("Containers", sorted(tl["container_id"].unique()), default=list(cur["container_id"].head(3)), key="hl_ids")
    if ids:
        d = tl[tl["container_id"].isin(ids)]
        lo, hi = d["as_of_ts"].min().to_pydatetime(), d["as_of_ts"].max().to_pydatetime()
        rng = st.slider("Date range", lo, hi, (lo, hi), key="hl_rng")
        d = d[d["as_of_ts"].between(*[pd.Timestamp(x) for x in rng])]
        st.line_chart(d.pivot_table(index="as_of_ts", columns="container_id", values="health_score"))
    st.subheader("Stored history")
    if st.button("Save hourly snapshot to local database", key="hl_save"):
        st.success(f"{save_health_history(tl)} rows upserted into ops.health_history")
    h = load_health_history()
    st.write(f"{len(h)} stored hourly records." if not h.empty else "No stored history yet.")
    st.download_button("Download current health (CSV)", cur.to_csv(index=False), "shipment_health.csv", "text/csv")
