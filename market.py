"""Agricultural market price intelligence (Feature 5).

Datasets are loaded together with an explicit TYPE (SIMULATED | HISTORICAL_DERIVED | ...) that is carried into every
output so results can never be mistaken for real market data.  Margins use the Phase 1 cost assumptions
(settings.yaml -> arbitrage).  Market-to-market "price arbitrage" here is a PRICE-DIFFERENCE view for traders; the spoilage-driven
reroute logic stays in analytics/engine.py and analytics/routes.py.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from analytics.geo import haversine_km
from common.config import abs_path

REQUIRED = ["price_date", "market_id", "commodity_id", "price_modal_usd_kg"]


def validate_price_dataset(df: pd.DataFrame) -> None:
    miss = [c for c in REQUIRED if c not in df.columns]
    if miss:
        raise ValueError(f"price dataset is missing columns: {miss}")
    if df["price_modal_usd_kg"].isna().any() or (df["price_modal_usd_kg"] <= 0).any():
        raise ValueError("price_modal_usd_kg must be positive and non-null")


def load_price_datasets(cfg: dict) -> dict[str, pd.DataFrame]:
    """id -> DataFrame (+ dataset_id, dataset_type, dataset_description columns). Optional missing files are skipped."""
    out = {}
    for d in cfg["market"]["datasets"]:
        p = abs_path(d["path"])
        if not p.exists():
            if d.get("optional"):
                continue
            raise FileNotFoundError(p)
        df = pd.read_csv(p)
        validate_price_dataset(df)
        df["price_date"] = pd.to_datetime(df["price_date"])
        out[d["id"]] = df.assign(dataset_id=d["id"], dataset_type=d["type"], dataset_description=d["description"])
    return out


def dataset_catalog(datasets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return pd.DataFrame([dict(dataset_id=k, dataset_type=v["dataset_type"].iloc[0], rows=len(v), markets=v["market_id"].nunique(),
                              date_from=v["price_date"].min().date(), date_to=v["price_date"].max().date(),
                              row_labels=", ".join(sorted(v["data_origin"].astype(str).unique())) if "data_origin" in v else "n/a",
                              description=v["dataset_description"].iloc[0]) for k, v in datasets.items()])


def simulate_price_series(market_offsets: dict[str, float], cfg: dict, end_date: str = "2026-11-10", seed: int | None = None) -> pd.DataFrame:
    """Reproducible random-walk wholesale prices (USD/kg) for what-if analysis. Always labelled SIMULATED."""
    s = cfg["market"]["simulation"]
    rng = np.random.default_rng(s["seed"] if seed is None else seed)
    days = pd.date_range(end=pd.Timestamp(end_date), periods=s["days"], freq="D")
    rows = []
    for m, off in market_offsets.items():
        walk = np.cumsum(rng.normal(0, s["daily_volatility"], len(days)))
        p = np.maximum(s["base_price_usd_kg"] + off + walk, 0.5).round(2)
        rows += [dict(price_date=d, market_id=m, commodity_id="avocado_hass", price_modal_usd_kg=v, data_origin="SIMULATED (scenario)") for d, v in zip(days, p)]
    return pd.DataFrame(rows)


def price_trends(prices: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Latest price, N-day changes, moving average, volatility, slope and a trend label per market/commodity."""
    m = cfg["market"]; rows = []
    for (cid, mk), g in prices.sort_values("price_date").groupby(["commodity_id", "market_id"]):
        s = g.set_index("price_date")["price_modal_usd_kg"]
        last = float(s.iloc[-1]); row = dict(commodity_id=cid, market_id=mk, latest_date=s.index[-1].date(), latest_price_usd_kg=last)
        for w in m["trend_windows_days"]:
            prev = s[s.index <= s.index[-1] - pd.Timedelta(days=w)]
            row[f"change_{w}d_pct"] = round(100 * (last / float(prev.iloc[-1]) - 1), 2) if len(prev) else np.nan
        row["moving_avg_7d"] = round(float(s.tail(7).mean()), 3)
        ret = s.pct_change().dropna().tail(m["volatility_window_days"])
        row["volatility_pct"] = round(100 * float(ret.std()), 2) if len(ret) > 1 else np.nan
        tail = s.tail(30)
        row["slope_usd_per_day"] = round(float(np.polyfit(np.arange(len(tail)), tail.to_numpy(), 1)[0]), 4) if len(tail) >= 5 else np.nan
        ch = row.get("change_7d_pct", np.nan)
        row["trend"] = "n/a" if pd.isna(ch) else "Stable" if abs(ch) < m["stable_band_pct"] else "Rising" if ch > 0 else "Falling"
        row["dataset_type"] = g["dataset_type"].iloc[0] if "dataset_type" in g else "UNKNOWN"
        rows.append(row)
    return pd.DataFrame(rows).sort_values("latest_price_usd_kg", ascending=False).reset_index(drop=True)


def latest_comparison(prices: pd.DataFrame) -> pd.DataFrame:
    d = prices[prices["price_date"] == prices["price_date"].max()].copy()
    d["rank"] = d.groupby("commodity_id")["price_modal_usd_kg"].rank(ascending=False, method="min").astype(int)
    d["premium_vs_avg_usd_kg"] = d["price_modal_usd_kg"] - d.groupby("commodity_id")["price_modal_usd_kg"].transform("mean")
    return d.sort_values("rank").reset_index(drop=True)


def arbitrage_margins(prices: pd.DataFrame, locations: pd.DataFrame, cfg: dict, quantity_kg: float | None = None, as_of=None) -> pd.DataFrame:
    """Buy in market A, sell in market B on one date: gross and net margin after transport and handling.
    gross = pB - pA; net = gross - transport(A->B) - handling.  Rows with gross <= 0 are kept (net < 0) but flagged."""
    a, q = cfg["arbitrage"], quantity_kg or cfg["market"]["default_quantity_kg"]
    day = pd.Timestamp(as_of) if as_of is not None else prices["price_date"].max()
    d = prices[prices["price_date"] == day]
    loc = locations.set_index("location_id")
    rows = []
    for cid, g in d.groupby("commodity_id"):
        for _, b in g.iterrows():
            for _, s in g.iterrows():
                if b["market_id"] == s["market_id"]:
                    continue
                km = float(haversine_km(loc.at[b["market_id"], "latitude"], loc.at[b["market_id"], "longitude"],
                                        loc.at[s["market_id"], "latitude"], loc.at[s["market_id"], "longitude"])) * cfg["simulator"]["road_factor"]
                gross = s["price_modal_usd_kg"] - b["price_modal_usd_kg"]
                transport = km / 1000.0 * a["transport_usd_per_tonne_km"]
                net = gross - transport - a["handling_usd_per_kg"]
                rows.append(dict(price_date=day.date(), commodity_id=cid, buy_market=b["market_id"], sell_market=s["market_id"], distance_km=km,
                                 buy_price_usd_kg=b["price_modal_usd_kg"], sell_price_usd_kg=s["price_modal_usd_kg"], gross_margin_usd_kg=gross,
                                 transport_usd_kg=transport, handling_usd_kg=a["handling_usd_per_kg"], net_margin_usd_kg=net,
                                 net_margin_pct=100 * net / b["price_modal_usd_kg"], quantity_kg=q, gross_margin_usd=gross * q, net_margin_usd=net * q,
                                 profitable=bool(net > 0), dataset_type=g["dataset_type"].iloc[0] if "dataset_type" in g else "UNKNOWN"))
    return pd.DataFrame(rows).sort_values("net_margin_usd", ascending=False).reset_index(drop=True)


def margin_history(prices: pd.DataFrame, locations: pd.DataFrame, cfg: dict, buy: str, sell: str) -> pd.DataFrame:
    """Daily net margin (USD/kg) for one market pair."""
    pv = prices.pivot_table(index="price_date", columns="market_id", values="price_modal_usd_kg")
    km = arbitrage_margins(prices, locations, cfg, as_of=prices["price_date"].max())
    dist = float(km[(km.buy_market == buy) & (km.sell_market == sell)]["distance_km"].iloc[0])
    gross = pv[sell] - pv[buy]
    net = gross - dist / 1000.0 * cfg["arbitrage"]["transport_usd_per_tonne_km"] - cfg["arbitrage"]["handling_usd_per_kg"]
    return pd.DataFrame({"gross_margin_usd_kg": gross, "net_margin_usd_kg": net}).reset_index()


if __name__ == "__main__":
    from common.config import load_settings
    cfg = load_settings(); ds = load_price_datasets(cfg); loc = pd.read_csv(abs_path(cfg["paths"]["sample_dir"]) / "locations.csv")
    print(dataset_catalog(ds).to_string(index=False)); p = ds["sample_simulated"]
    print(price_trends(p, cfg).head(4).to_string(index=False)); print(arbitrage_margins(p, loc, cfg).head(3).to_string(index=False))
