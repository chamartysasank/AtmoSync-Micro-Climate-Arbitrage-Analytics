"""Load sample dimension tables + replay raw events into Snowflake RAW. UNTESTED (needs an account).
  export SNOWFLAKE_* env vars (see .env.example), run snowflake/sql/01 and 02 first, then:
  python scripts/load_snowflake.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from common.config import load_settings, abs_path
from ingestion.replay import replay_events
from streaming.sinks import SnowflakeSink


def main():
    from snowflake.connector.pandas_tools import write_pandas
    cfg = load_settings(); d = abs_path(cfg["paths"]["sample_dir"]); sink = SnowflakeSink()
    for table, csv in [("RAW_LOCATIONS", "locations.csv"), ("RAW_CONTAINERS", "containers.csv"), ("RAW_COMMODITIES", "commodities.csv"),
                       ("RAW_SHIPMENTS", "shipments.csv"), ("RAW_MARKET_PRICES", "market_prices.csv")]:
        df = pd.read_csv(d / csv); df.columns = [c.upper() for c in df.columns]
        ok, _, n, _ = write_pandas(sink.con, df, table, auto_create_table=False, overwrite=False)
        print(table, "ok" if ok else "FAILED", n)
    events = list(replay_events(d / "raw_sensor_events.csv"))
    print("raw events written:", sink.write_batch(events))


if __name__ == "__main__":
    main()
