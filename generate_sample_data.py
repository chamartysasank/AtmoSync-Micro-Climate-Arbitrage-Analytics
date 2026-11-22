"""Generate the SIMULATED sample dataset into data/sample/. Reproducible (seeded).

Run:  python scripts/generate_sample_data.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
from common.config import load_settings, abs_path, get_logger
from simulator.iot_simulator import build_fleet, generate_events

log = get_logger("generate_sample_data")

# Approximate city-centre coordinates (general geographic knowledge; accurate to ~0.1 deg).
LOCATIONS = [
    # id, name, lat, lon, is_market, type
    ("PHARR_TX", "Pharr, TX (border crossing)", 26.19, -98.18, False, "origin"),
    ("OTAY_MESA_CA", "Otay Mesa, CA (border crossing)", 32.55, -117.03, False, "origin"),
    ("LOS_ANGELES", "Los Angeles", 34.05, -118.24, True, "market"),
    ("PHOENIX", "Phoenix", 33.45, -112.07, True, "market"),
    ("DENVER", "Denver", 39.74, -104.99, True, "market"),
    ("DALLAS", "Dallas", 32.78, -96.80, True, "market"),
    ("HOUSTON", "Houston", 29.76, -95.37, True, "market"),
    ("CHICAGO", "Chicago", 41.88, -87.63, True, "market"),
    ("ATLANTA", "Atlanta", 33.75, -84.39, True, "market"),
    ("NEW_YORK", "New York", 40.71, -74.01, True, "market"),
    ("SEATTLE", "Seattle", 47.61, -122.33, True, "market"),
]
# SIMULATED wholesale price offsets (USD/kg) vs a 3.50 base. Illustrative only.
OFFSETS = {"NEW_YORK": 0.55, "CHICAGO": 0.40, "SEATTLE": 0.35, "ATLANTA": 0.15, "DENVER": 0.05,
           "DALLAS": -0.10, "HOUSTON": -0.15, "PHOENIX": -0.20, "LOS_ANGELES": -0.30}


def main():
    cfg = load_settings()
    out = abs_path(cfg["paths"]["sample_dir"]); out.mkdir(parents=True, exist_ok=True)
    loc = pd.DataFrame(LOCATIONS, columns=["location_id", "name", "latitude", "longitude", "is_market", "location_type"])
    loc["data_origin"] = "ASSUMPTION (approximate coordinates)"
    plans, shipments, containers = build_fleet(loc, cfg)
    events = generate_events(plans, shipments, loc, cfg)

    rng = np.random.default_rng(cfg["simulator"]["seed"] + 7)
    end = pd.Timestamp(cfg["simulator"]["end_ts"]).normalize()
    days = pd.date_range(end - pd.Timedelta(days=89), end, freq="D")
    rows = []
    for m, off in OFFSETS.items():
        walk = np.cumsum(rng.normal(0, 0.03, len(days)))
        season = 0.15 * np.sin(2 * np.pi * np.arange(len(days)) / 30)
        modal = 3.5 + off + walk + season
        for d, p in zip(days, modal):
            p = round(max(p, 1.0), 2)
            rows.append(dict(price_date=d.date().isoformat(), market_id=m, commodity_id="avocado_hass",
                             price_min_usd_kg=round(p * 0.9, 2), price_max_usd_kg=round(p * 1.1, 2),
                             price_modal_usd_kg=p, data_origin="SIMULATED"))
    prices = pd.DataFrame(rows)
    commodities = pd.DataFrame([dict(
        commodity_id="avocado_hass", display_name="Avocado (Hass)", temp_min_c=5, temp_max_c=13, temp_best_c=7.2,
        rh_min_pct=85, rh_max_pct=95, base_shelf_life_days=cfg["quality_model"]["base_shelf_life_days"],
        source="UC Davis Postharvest; WFLO Commodity Storage Manual 2018; Produce Blue Book (see docs)")])

    loc.to_csv(out / "locations.csv", index=False)
    containers.to_csv(out / "containers.csv", index=False)
    shipments.to_csv(out / "shipments.csv", index=False)
    commodities.to_csv(out / "commodities.csv", index=False)
    prices.to_csv(out / "market_prices.csv", index=False)
    events.to_csv(out / "raw_sensor_events.csv", index=False)
    log.info("Wrote sample data: %d events, %d shipments, %d price rows", len(events), len(shipments), len(prices))


if __name__ == "__main__":
    main()
