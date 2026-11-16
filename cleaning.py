"""Validation + cleaning of raw sensor events (pandas)."""
from __future__ import annotations
import pandas as pd
import numpy as np
from common.config import get_logger

log = get_logger(__name__)
REQUIRED = ["event_id", "container_id", "sensor_id", "shipment_id", "reading_ts",
            "temperature_c", "humidity_pct", "vibration_g"]
SENTINELS = (-999.0, -9999.0)


def clean_sensor_events(raw: pd.DataFrame, cfg: dict, impute_gaps: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Return (clean, rejected, stats).

    Steps: required columns -> UTC timestamps -> numeric coercion -> sentinel to NaN ->
    range validation -> duplicate removal -> optional short-gap interpolation.
    SQL staging (dbt) mirrors this EXCEPT imputation (never imputed in SQL).
    """
    missing_cols = [c for c in REQUIRED if c not in raw.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")
    th = cfg["thresholds"]
    df = raw.copy()
    stats = {"input_rows": len(df)}

    df["reading_ts"] = pd.to_datetime(df["reading_ts"], utc=True, errors="coerce").dt.tz_localize(None)
    for c in ("temperature_c", "humidity_pct", "vibration_g", "latitude", "longitude"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ("temperature_c", "humidity_pct"):
        df.loc[df[c].isin(SENTINELS), c] = np.nan

    reasons = pd.Series("", index=df.index)
    reasons[df["reading_ts"].isna()] += "bad_timestamp;"
    reasons[df[["container_id", "sensor_id", "shipment_id"]].isna().any(axis=1)] += "missing_id;"
    t_lo, t_hi = th["valid_temp_range_c"]; r_lo, r_hi = th["valid_rh_range_pct"]; v_lo, v_hi = th["valid_vibration_range_g"]
    reasons[df["temperature_c"].isna()] += "null_temperature;"
    reasons[df["humidity_pct"].isna()] += "null_humidity;"
    reasons[df["temperature_c"].notna() & ~df["temperature_c"].between(t_lo, t_hi)] += "temp_out_of_range;"
    reasons[df["humidity_pct"].notna() & ~df["humidity_pct"].between(r_lo, r_hi)] += "rh_out_of_range;"
    reasons[df["vibration_g"].notna() & ~df["vibration_g"].between(v_lo, v_hi)] += "vibration_out_of_range;"

    rejected = df[reasons != ""].assign(reject_reason=reasons[reasons != ""])
    good = df[reasons == ""].copy()

    before = len(good)
    good = good.sort_values("reading_ts").drop_duplicates(["container_id", "sensor_id", "reading_ts"], keep="last")
    stats["duplicates_removed"] = before - len(good)

    if impute_gaps:  # optional, off by default so SQL and pandas stay in parity
        good = good.set_index("reading_ts").groupby("container_id", group_keys=False).apply(
            lambda g: g.interpolate(limit=2, limit_area="inside")).reset_index()
    stats.update(rejected_rows=len(rejected), clean_rows=len(good))
    log.info("Cleaning stats: %s", stats)
    return good.sort_values(["container_id", "reading_ts"]).reset_index(drop=True), rejected, stats
