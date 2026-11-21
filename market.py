"""Market Analytics page (Feature 5)."""
import pandas as pd
import streamlit as st
from analytics.market import (load_price_datasets, dataset_catalog, price_trends, latest_comparison, arbitrage_margins, margin_history)

TITLE, ORDER = "Market Analytics", 70


@st.cache_data(show_spinner=False)
def _datasets(_key):
    from common.config import load_settings
    return load_price_datasets(load_settings())


def render(ctx):
    cfg, loc = ctx["cfg"], ctx["r"]["locations"]
    ds = _datasets(str(cfg["market"]["datasets"]))
    ids = list(ds)
    pick = st.selectbox("Price dataset", ids, key="mk_ds")
    d = ds[pick]
    kind = d["dataset_type"].iloc[0]
    (st.warning if kind == "SIMULATED" else st.info)(f"Dataset type: **{kind}** — {d['dataset_description'].iloc[0]}")
    c1, c2 = st.columns(2)
    markets = c1.multiselect("Markets", sorted(d["market_id"].unique()), default=sorted(d["market_id"].unique()), key="mk_mk")
    lo, hi = d["price_date"].min().to_pydatetime(), d["price_date"].max().to_pydatetime()
    rng = c2.slider("Date range", lo, hi, (lo, hi), key="mk_rng")
    f = d[d["market_id"].isin(markets) & d["price_date"].between(*[pd.Timestamp(x) for x in rng])]
    if f.empty:
        st.info("No data for this selection."); return
    t1, t2, t3, t4 = st.tabs(["Prices & trends", "Market comparison", "Arbitrage margins", "Dataset catalog"])
    with t1:
        st.line_chart(f.pivot_table(index="price_date", columns="market_id", values="price_modal_usd_kg"))
        st.dataframe(price_trends(f, cfg).drop(columns=["commodity_id"]).round(3), use_container_width=True)
    with t2:
        lc = latest_comparison(f)
        st.bar_chart(lc.set_index("market_id")["price_modal_usd_kg"])
        st.dataframe(lc[["rank", "market_id", "price_date", "price_modal_usd_kg", "premium_vs_avg_usd_kg"]].round({"price_modal_usd_kg": 3, "premium_vs_avg_usd_kg": 3}), use_container_width=True)
    with t3:
        q = st.number_input("Quantity (kg)", 1000, 100000, int(cfg["market"]["default_quantity_kg"]), 1000, key="mk_q")
        m = arbitrage_margins(f, loc, cfg, quantity_kg=q)
        st.caption("Gross = sell price − buy price. Net also subtracts transport (Phase 1 cost assumptions) and handling. Price-difference view only; it ignores spoilage.")
        only = st.checkbox("Profitable only", True, key="mk_prof")
        show = m[m["profitable"]] if only else m
        st.dataframe(show[["buy_market", "sell_market", "distance_km", "gross_margin_usd_kg", "transport_usd_kg", "net_margin_usd_kg", "net_margin_pct", "net_margin_usd", "dataset_type"]].round(2).head(50), use_container_width=True)
        if len(m):
            a, b = st.columns(2)
            buy = a.selectbox("Buy market", sorted(f["market_id"].unique()), key="mk_buy")
            sell = b.selectbox("Sell market", [x for x in sorted(f["market_id"].unique()) if x != buy], key="mk_sell")
            st.line_chart(margin_history(f, loc, cfg, buy, sell).set_index("price_date"))
    with t4:
        st.dataframe(dataset_catalog(ds), use_container_width=True)
