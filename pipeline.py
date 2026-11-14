"""End-to-end local pipeline (pandas reference path). Used by run_local.py, the app and tests."""
from __future__ import annotations
from pathlib import Path
import pandas as pd
from common.config import load_settings, abs_path, get_logger
from ingestion.cleaning import clean_sensor_events
from analytics import engine as E

log = get_logger(__name__)


def run_pipeline(cfg: dict | None = None, sample_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    cfg = cfg or load_settings()
    d = Path(sample_dir) if sample_dir else abs_path(cfg["paths"]["sample_dir"])
    raw = pd.read_csv(d / "raw_sensor_events.csv")
    loc, ship = pd.read_csv(d / "locations.csv"), pd.read_csv(d / "shipments.csv")
    prices = pd.read_csv(d / "market_prices.csv")
    clean, rejected, stats = clean_sensor_events(raw, cfg)
    readings = E.add_reading_rates(clean, cfg)
    status = E.container_status(readings, ship, loc, cfg)
    options = E.arbitrage_options(status, prices, loc, cfg)
    recs = E.arbitrage_recommendations(status, options, cfg)
    shipment_risk = status.merge(ship[["shipment_id", "origin_id", "planned_arrival_ts"]], on="shipment_id")
    shipment_risk.insert(0, "risk_rank", shipment_risk["risk_score"].rank(ascending=False, method="min").astype(int))
    p = prices.sort_values(["market_id", "price_date"]).copy()
    p["modal_7d_avg"] = p.groupby(["market_id", "commodity_id"])["price_modal_usd_kg"].transform(lambda s: s.rolling(7, min_periods=1).mean())
    p["premium_vs_all_markets"] = p["price_modal_usd_kg"] - p.groupby(["commodity_id", "price_date"])["price_modal_usd_kg"].transform("mean")
    p["price_rank"] = p.groupby(["commodity_id", "price_date"])["price_modal_usd_kg"].rank(ascending=False, method="min").astype(int)
    return dict(clean=clean, rejected=rejected, readings=readings, status=status, options=options, recs=recs,
                kpis=E.executive_kpis(status, recs), hourly=E.hourly_series(readings), shipment_risk=shipment_risk,
                market_comparison=p, locations=loc, cleaning_stats=pd.DataFrame([stats]))
