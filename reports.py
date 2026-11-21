"""Reports page (Feature 9): executive KPIs, summary tables, CSV and PDF export."""
import streamlit as st
from analytics.reporting import build_report, csv_bundle_zip, build_pdf_bytes

TITLE, ORDER = "Reports", 110


@st.cache_data(show_spinner="Building report...")
def _report(_r, _key):
    from common.config import load_settings
    return build_report(_r, load_settings())


def render(ctx):
    r, cfg = ctx["r"], ctx["cfg"]
    rep = _report(r, str(cfg["reporting"]) + str(cfg["market"]["datasets"]))
    for line in rep.labels:
        (st.warning if line.startswith("SIMULATED") else st.caption)(line)
    st.subheader(f"Executive KPIs - data as of {rep.as_of}")
    k = rep.kpis.set_index("kpi")["value"]
    cols = st.columns(4)
    for i, (name, val) in enumerate(k.items()):
        cols[i % 4].metric(name, val)
    labels = {"shipment_health_summary": "Shipment health", "at_risk_containers": "At-risk containers", "critical_containers": "Critical containers",
              "market_price_comparison": "Market prices", "market_margins_top": "Market margins", "reroute_opportunities": "Rerouting opportunities", "route_recommendations": "Route changes"}
    tabs = st.tabs(list(labels.values()))
    for tab, key in zip(tabs, labels):
        with tab:
            df = rep.tables[key]
            st.caption(f"Label: {df['report_label'].iloc[0] if len(df) else 'n/a'}")
            st.dataframe(df.drop(columns=["report_label"]), use_container_width=True) if len(df) else st.write("None.")
    c1, c2 = st.columns(2)
    c1.download_button("Download CSV bundle (zip)", csv_bundle_zip(rep), "atmosync_report_csv.zip", "application/zip")
    c2.download_button("Download PDF report", build_pdf_bytes(rep, cfg), "atmosync_executive_report.pdf", "application/pdf")
