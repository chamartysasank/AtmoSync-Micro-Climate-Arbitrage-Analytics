"""Risk Forecasting page (Feature 3)."""
import streamlit as st
from analytics.forecast import forecast_risk, forecast_summary, forecast_assumptions, DISCLAIMER

TITLE, ORDER = "Risk Forecasting", 50


@st.cache_data(show_spinner=False)
def _fc(_readings, _status, _key):
    from common.config import load_settings
    return forecast_risk(_readings, _status, load_settings())


def render(ctx):
    r, cfg = ctx["r"], ctx["cfg"]
    st.warning(DISCLAIMER)
    fc = _fc(r["readings"], r["status"], str(cfg["forecast"]) + str(cfg["quality_model"]) + str(cfg["risk"]))
    c1, c2 = st.columns(2)
    scen = c1.radio("Scenario", list(cfg["forecast"]["scenarios"]), index=1, horizontal=True, key="fc_scen")
    sev = c2.multiselect("Risk category at any horizon", ["CRITICAL", "HIGH", "MEDIUM", "LOW"], default=["CRITICAL", "HIGH", "MEDIUM", "LOW"], key="fc_sev")
    keep = fc[(fc["scenario"] == scen) & fc["risk_category"].isin(sev)]["container_id"].unique()
    d = fc[(fc["scenario"] == scen) & fc["container_id"].isin(keep)]
    cols = st.columns(len(cfg["forecast"]["horizons_hours"]))
    for col, h in zip(cols, cfg["forecast"]["horizons_hours"]):
        x = d[d["horizon_h"] == h]
        col.metric(f"At risk at +{h} h", int(x["risk_category"].isin(["HIGH", "CRITICAL"]).sum()), help="HIGH or CRITICAL under the selected scenario")
    st.subheader("Risk category by horizon")
    st.dataframe(forecast_summary(fc, scen).query("container_id in @keep"), use_container_width=True)
    ids = st.multiselect("Containers for charts", sorted(keep), default=list(sorted(keep))[:4], key="fc_ids")
    if ids:
        x = d[d["container_id"].isin(ids)]
        st.subheader("Risk score vs horizon"); st.line_chart(x.pivot_table(index="horizon_h", columns="container_id", values="risk_score"))
        st.subheader("Projected temperature (°C)"); st.line_chart(x.pivot_table(index="horizon_h", columns="container_id", values="projected_temp_c"))
        st.subheader("Remaining shelf life (h)"); st.line_chart(x.pivot_table(index="horizon_h", columns="container_id", values="remaining_life_hours"))
    with st.expander("Assumptions and evidence level"):
        st.dataframe(forecast_assumptions(cfg), use_container_width=True)
    st.download_button("Download forecast (CSV)", fc.to_csv(index=False), "risk_forecast.csv", "text/csv")
