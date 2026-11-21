"""Route Intelligence page (Feature 4)."""
import pandas as pd
import streamlit as st
from analytics.routes import compare_routes, recommend_routes, load_profiles
from common.config import abs_path

TITLE, ORDER = "Route Intelligence", 60


@st.cache_data(show_spinner=False)
def _routes(_status, _loc, _key):
    from common.config import load_settings
    cfg = load_settings()
    prices = pd.read_csv(abs_path(cfg["paths"]["sample_dir"]) / "market_prices.csv")
    opts = compare_routes(_status, _loc, load_profiles(cfg), prices, cfg)
    return opts, recommend_routes(opts, cfg)


def render(ctx):
    r, cfg = ctx["r"], ctx["cfg"]
    st.caption("Route profiles are SAMPLE / ILLUSTRATIVE data (data/sample/route_profiles.csv); exposure sensitivities are assumptions. "
               "A route change is recommended only when the current route would degrade the fruit.")
    opts, rec = _routes(r["status"], r["locations"], str(cfg["routes"]) + str(cfg["arbitrage"]) + str(cfg["quality_model"]))
    k = st.columns(3)
    k[0].metric("Containers", len(rec)); k[1].metric("Change route recommended", int((rec["recommendation"] != "KEEP CURRENT ROUTE").sum()))
    k[2].metric("Total benefit $", f"{rec.loc[rec['recommendation'] != 'KEEP CURRENT ROUTE', 'benefit_usd'].sum():,.0f}")
    only = st.checkbox("Only containers with a route-change recommendation", value=False, key="rt_only")
    show = rec[rec["recommendation"] != "KEEP CURRENT ROUTE"] if only else rec
    st.dataframe(show[["container_id", "recommendation", "recommended_market", "recommended_profile", "benefit_usd", "rerouting_cost_usd",
                       "arrival_life_hours", "baseline_arrival_life_hours"]].round(1), use_container_width=True)
    cid = st.selectbox("Container detail", list(show["container_id"]) or list(rec["container_id"]), key="rt_cid")
    st.info(rec.set_index("container_id").loc[cid, "explanation"])
    profiles = st.multiselect("Route profiles", sorted(opts["profile_id"].unique()), default=sorted(opts["profile_id"].unique()), key="rt_prof")
    d = opts[(opts["container_id"] == cid) & opts["profile_id"].isin(profiles)].sort_values("net_value_usd", ascending=False)
    st.subheader("All options (ranked by net value)")
    st.dataframe(d[["market_id", "profile_id", "is_baseline", "distance_km", "travel_hours", "remaining_life_at_arrival_h", "arrival_status",
                    "exposure_index", "expected_value_usd", "transport_cost_usd", "reroute_fee_usd", "net_value_usd", "benefit_vs_baseline_usd"]].round(1), use_container_width=True)
    top = d.head(12).assign(option=lambda x: x["market_id"] + " / " + x["profile_id"])
    st.bar_chart(top.set_index("option")["net_value_usd"])
    st.download_button("Download route options (CSV)", opts.to_csv(index=False), "route_options.csv", "text/csv")
