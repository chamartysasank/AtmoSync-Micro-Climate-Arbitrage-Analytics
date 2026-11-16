"""LOCAL MODE warehouse: loads raw tables into DuckDB schema `raw` (mirrors Snowflake RAW schema)
so the very same dbt models run locally (dbt-duckdb) and in Snowflake (dbt-snowflake).

Run:  python -m ingestion.local_warehouse
"""
from __future__ import annotations
import json
from pathlib import Path
import duckdb
import pandas as pd
from common.config import load_settings, abs_path, get_logger

log = get_logger(__name__)
PAYLOAD_FIELDS = ["container_id", "sensor_id", "shipment_id", "reading_ts", "temperature_c",
                  "humidity_pct", "vibration_g", "latitude", "longitude"]


def events_to_raw_rows(events: pd.DataFrame) -> pd.DataFrame:
    """Wrap each wide event into the Snowflake-style raw record: (event_id, event_ts, payload JSON, source)."""
    def payload(r):
        d = {k: (None if pd.isna(r[k]) else (r[k].item() if hasattr(r[k], "item") else r[k])) for k in PAYLOAD_FIELDS}
        return json.dumps(d)
    out = pd.DataFrame({"event_id": events["event_id"], "event_ts": pd.to_datetime(events["reading_ts"], utc=True, errors="coerce").dt.tz_localize(None),
                        "payload": events.apply(payload, axis=1), "source": events.get("source", "SIMULATED")})
    out["ingested_at"] = pd.Timestamp.now("UTC").tz_localize(None)
    return out


def load_local_warehouse(cfg: dict | None = None, sample_dir: Path | None = None, db_file: Path | None = None) -> Path:
    cfg = cfg or load_settings()
    sample_dir = sample_dir or abs_path(cfg["paths"]["sample_dir"])
    db_file = db_file or abs_path(cfg["paths"]["duckdb_file"])
    db_file.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_file))
    con.execute("create schema if not exists raw")
    raw_events = events_to_raw_rows(pd.read_csv(sample_dir / "raw_sensor_events.csv"))
    con.register("tmp_events", raw_events)
    con.execute("create or replace table raw.raw_sensor_events as select * from tmp_events")
    for name, csv, extra in [("raw_shipments", "shipments.csv", ""), ("raw_containers", "containers.csv", ""),
                             ("raw_commodities", "commodities.csv", ""), ("raw_locations", "locations.csv", ""),
                             ("raw_market_prices", "market_prices.csv", "")]:
        con.execute(f"create or replace table raw.{name} as select * from read_csv_auto('{(sample_dir / csv).as_posix()}')")
    counts = {t: con.execute(f"select count(*) from raw.{t}").fetchone()[0] for t in
              ["raw_sensor_events", "raw_shipments", "raw_containers", "raw_commodities", "raw_locations", "raw_market_prices"]}
    con.close()
    log.info("Local warehouse ready at %s: %s", db_file, counts)
    return db_file


if __name__ == "__main__":
    load_local_warehouse()
