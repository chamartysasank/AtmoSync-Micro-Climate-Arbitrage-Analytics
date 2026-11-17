"""Where consumed events land: local files/DuckDB (always available) or Snowflake (optional)."""
from __future__ import annotations
import json, os
from pathlib import Path
import pandas as pd
from common.config import get_logger

log = get_logger(__name__)
PAYLOAD_KEYS = ["container_id", "sensor_id", "shipment_id", "reading_ts", "temperature_c",
                "humidity_pct", "vibration_g", "latitude", "longitude"]


class JsonlSink:
    """Append-only NDJSON file - the zero-dependency fallback."""
    def __init__(self, path: str | Path):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)

    def write_batch(self, events: list[dict]) -> int:
        with open(self.path, "a", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")
        return len(events)


class DuckDBSink:
    """Writes raw events into raw.raw_sensor_events (same shape as Snowflake RAW table)."""
    def __init__(self, db_file: str | Path):
        import duckdb
        self.con = duckdb.connect(str(db_file))
        self.con.execute("create schema if not exists raw")
        self.con.execute("""create table if not exists raw.raw_sensor_events
            (event_id varchar, event_ts timestamp, payload varchar, source varchar, ingested_at timestamp)""")

    def write_batch(self, events: list[dict]) -> int:
        rows = [(e["event_id"], pd.to_datetime(e["reading_ts"], utc=True).tz_localize(None).to_pydatetime(),
                 json.dumps({k: e.get(k) for k in PAYLOAD_KEYS}), e.get("source", "KAFKA"),
                 pd.Timestamp.now("UTC").tz_localize(None).to_pydatetime()) for e in events]
        self.con.executemany("insert into raw.raw_sensor_events values (?,?,?,?,?)", rows)
        return len(rows)


class SnowflakeSink:
    """Inserts raw JSON into RAW.RAW_SENSOR_EVENTS (VARIANT). Credentials from environment only.

    Row-by-row INSERT...SELECT is fine for demos. For production volume use the Snowflake Kafka
    Connector or Snowpipe Streaming instead (documented in docs/setup). UNTESTED here (no account).
    """
    def __init__(self):
        import snowflake.connector
        self.con = snowflake.connector.connect(
            account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"],
            password=os.environ["SNOWFLAKE_PASSWORD"], role=os.getenv("SNOWFLAKE_ROLE", "ATMOSYNC_ROLE"),
            warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "ATMOSYNC_WH"),
            database=os.getenv("SNOWFLAKE_DATABASE", "ATMOSYNC"), schema=os.getenv("SNOWFLAKE_SCHEMA", "RAW"))

    def write_batch(self, events: list[dict]) -> int:
        sql = ("insert into raw_sensor_events (event_id, event_ts, payload, source) "
               "select %s, to_timestamp_ntz(%s), parse_json(%s), %s")
        rows = [(e["event_id"], str(e["reading_ts"]).replace("T", " ").replace("Z", ""),
                 json.dumps({k: e.get(k) for k in PAYLOAD_KEYS}), e.get("source", "KAFKA")) for e in events]
        cur = self.con.cursor()
        try:
            cur.executemany(sql, rows)
        finally:
            cur.close()
        return len(rows)
