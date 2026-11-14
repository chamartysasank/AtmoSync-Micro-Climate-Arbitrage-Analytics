"""Write Tableau-ready CSVs to tableau/data_sources/. In full mode, connect Tableau to the Snowflake
ANALYTICS marts directly instead (same column names)."""
from __future__ import annotations
from pathlib import Path
from common.config import load_settings, abs_path, get_logger
from analytics.pipeline import run_pipeline

log = get_logger(__name__)


def export(cfg=None, out_dir: Path | None = None) -> list[Path]:
    cfg = cfg or load_settings()
    out = Path(out_dir) if out_dir else abs_path(cfg["paths"]["tableau_dir"]); out.mkdir(parents=True, exist_ok=True)
    r = run_pipeline(cfg)
    files = {"container_health.csv": r["status"], "shipment_risk.csv": r["shipment_risk"],
             "sensor_readings.csv": r["readings"][["event_id", "container_id", "shipment_id", "reading_ts", "temperature_c", "humidity_pct",
                                                    "vibration_g", "latitude", "longitude", "burn_rate", "temp_excursion", "rh_excursion", "is_excursion"]],
             "sensor_hourly.csv": r["hourly"], "arbitrage_options.csv": r["options"],
             "arbitrage_recommendations.csv": r["recs"], "market_prices.csv": r["market_comparison"],
             "executive_kpis.csv": r["kpis"], "locations.csv": r["locations"]}
    paths = []
    for name, df in files.items():
        p = out / name; df.to_csv(p, index=False); paths.append(p)
    log.info("Exported %d Tableau data sources to %s", len(paths), out)
    return paths


if __name__ == "__main__":
    export()
