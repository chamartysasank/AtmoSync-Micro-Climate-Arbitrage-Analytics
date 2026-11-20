"""Overview: KPIs + the original shipment-risk / arbitrage / market tables from the Phase 1 app."""
import streamlit as st

TITLE, ORDER = "Overview", 10


def render(ctx):
    r = ctx["r"]; k = r["kpis"].iloc[0]
    cols = st.columns(6)
    for col, (label, key) in zip(cols, [("Containers", "total_containers"), ("Healthy", "healthy_containers"), ("At risk", "at_risk_containers"),
                                        ("Critical", "critical_alerts"), ("Reroute opps", "arbitrage_opportunities"), ("Est. benefit $", "estimated_benefit_usd")]):
        col.metric(label, f"{k[key]:,.0f}")
    st.subheader("Shipment risk")
    cats = st.multiselect("Risk category", ["CRITICAL", "HIGH", "MEDIUM", "LOW"], default=["CRITICAL", "HIGH", "MEDIUM", "LOW"], key="ov_cats")
    sr = r["shipment_risk"]
    st.dataframe(sr[sr["risk_category"].isin(cats)][["risk_rank", "shipment_id", "container_id", "risk_score", "risk_category",
                 "quality_window_hours", "hours_to_destination", "slack_hours"]].round(2), use_container_width=True)
    st.subheader("Arbitrage recommendations")
    st.dataframe(r["recs"].round(2), use_container_width=True)
    cid = st.selectbox("Container detail", r["recs"]["container_id"], key="ov_cid")
    st.dataframe(r["options"][r["options"]["container_id"] == cid].sort_values("benefit_vs_original_usd", ascending=False).round(2), use_container_width=True)
    with st.expander("Market prices (SIMULATED) — see Market Analytics for more"):
        st.line_chart(r["market_comparison"].pivot_table(index="price_date", columns="market_id", values="price_modal_usd_kg"))
