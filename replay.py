"""Historical replay: turn a CSV/JSONL of past readings into a (time-scaled) event stream."""
from __future__ import annotations
import json, math, time
from pathlib import Path
from typing import Iterator
import pandas as pd


def replay_events(path: str | Path, speedup: float = 0.0, limit: int | None = None) -> Iterator[dict]:
    """Yield events in timestamp order.

    speedup = 0  -> as fast as possible (tests, bulk loads)
    speedup = 60 -> 60 simulated seconds per real second (demo streaming)
    """
    path = Path(path)
    df = pd.read_json(path, lines=True) if path.suffix == ".jsonl" else pd.read_csv(path)
    df["_ts"] = pd.to_datetime(df["reading_ts"], utc=True, errors="coerce")
    df = df.sort_values("_ts", kind="stable")
    prev = None
    for i, rec in enumerate(df.drop(columns="_ts").to_dict("records")):
        if limit is not None and i >= limit:
            return
        ts = df["_ts"].iloc[i]
        if speedup > 0 and prev is not None and pd.notna(ts) and pd.notna(prev):
            wait = (ts - prev).total_seconds() / speedup
            if wait > 0:
                time.sleep(wait)
        prev = ts
        yield {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in rec.items()}
