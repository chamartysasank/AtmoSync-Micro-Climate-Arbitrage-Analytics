"""Shipment health scoring (Feature 2) - an explainable CONDITION score, not a spoilage prediction.

For each reading a penalty (0..1) is computed per variable:
  temperature : distance outside the commodity temperature range / temp_full_penalty_c
  humidity    : distance outside the RH range / rh_full_penalty_pct
  vibration   : (vibration - vibration_ok_g) / (vibration_full_penalty_g - vibration_ok_g)
Sub-score = 100 * (1 - mean penalty over the trailing `window_hours`).  Health = weighted mean of sub-scores; if any sub-score is <= failure_floor the total is capped at failure_cap
(so one failing variable cannot be averaged away).
Difference to the Phase 1 risk score: risk looks FORWARD (shelf life vs time to destination); health describes how
well recent conditions matched the target range.
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from common.store import Store

CATEGORIES = ["Healthy", "Warning", "At Risk", "Critical"]
TABLE = "health_history"


def classify_health(score: float, cfg: dict) -> str:
    c = cfg["health"]["classes"]
    if pd.isna(score): return "Unknown"
    if score >= c["healthy"]: return "Healthy"
    if score >= c["warning"]: return "Warning"
    if score >= c["at_risk"]: return "At Risk"
    return "Critical"


def _penalties(readings: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    h, t = cfg["health"], cfg["thresholds"]
    d = readings[["container_id", "shipment_id", "reading_ts", "temperature_c", "humidity_pct", "vibration_g"]].copy() \
        if "shipment_id" in readings.columns else readings.assign(shipment_id=None)[["container_id", "shipment_id", "reading_ts", "temperature_c", "humidity_pct", "vibration_g"]].copy()
    d["temp_dev"] = np.maximum.reduce([t["temp_min_c"] - d["temperature_c"], d["temperature_c"] - t["temp_max_c"], np.zeros(len(d))])
    d["rh_dev"] = np.maximum.reduce([t["rh_min_pct"] - d["humidity_pct"], d["humidity_pct"] - t["rh_max_pct"], np.zeros(len(d))])
    d["vib_ex"] = (d["vibration_g"] - h["vibration_ok_g"]).clip(lower=0)
    d.loc[d["temperature_c"].isna(), "temp_dev"] = np.nan
    d.loc[d["humidity_pct"].isna(), "rh_dev"] = np.nan
    d.loc[d["vibration_g"].isna(), "vib_ex"] = np.nan
    d["temp_pen"] = (d["temp_dev"] / h["temp_full_penalty_c"]).clip(0, 1)
    d["rh_pen"] = (d["rh_dev"] / h["rh_full_penalty_pct"]).clip(0, 1)
    d["vib_pen"] = (d["vib_ex"] / (h["vibration_full_penalty_g"] - h["vibration_ok_g"])).clip(0, 1)
    return d.sort_values(["container_id", "reading_ts"])


def _explain(row: pd.Series, cfg: dict) -> tuple[str, str]:
    t, h = cfg["thresholds"], cfg["health"]
    parts = {"temperature": row["temperature_score"], "humidity": row["humidity_score"], "vibration": row["vibration_score"]}
    avail = {k: v for k, v in parts.items() if pd.notna(v)}
    weights = h["weights"]
    loss = {k: weights[k] * (100 - v) for k, v in avail.items()}
    driver = max(loss, key=loss.get) if loss and max(loss.values()) > 0.05 else "none"
    txt = (f"Health {row['health_score']:.0f} ({row['category']}) over the last {h['window_hours']} h: "
           f"temperature {row['temperature_score']:.0f}/100 (avg {row['mean_temp_dev_c']:.1f} °C outside {t['temp_min_c']:g}-{t['temp_max_c']:g} °C), "
           f"humidity {row['humidity_score']:.0f}/100 (avg {row['mean_rh_dev_pct']:.1f} % outside {t['rh_min_pct']:g}-{t['rh_max_pct']:g} %), "
           f"vibration {row['vibration_score']:.0f}/100. Main driver: {driver}."
           + (f" Score capped at {h['failure_cap']} because one variable is at or below {h['failure_floor']}/100." if row["capped"] else ""))
    return driver, txt


def health_timeline(readings: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Health score at EVERY reading (trailing window). Rows with fewer than min_readings in the window are dropped."""
    h = cfg["health"]
    p = _penalties(readings, cfg)
    cols = ["temp_pen", "rh_pen", "vib_pen", "temp_dev", "rh_dev", "vib_ex"]
    roll = p.groupby("container_id").rolling(f"{h['window_hours']}h", on="reading_ts", min_periods=h["min_readings"])[cols].mean()
    roll = roll.reset_index().drop(columns="level_1", errors="ignore")
    cnt = p.groupby("container_id").rolling(f"{h['window_hours']}h", on="reading_ts")["temp_dev"].count().reset_index()
    roll["window_readings"] = cnt["temp_dev"].values
    roll = roll.merge(p[["container_id", "reading_ts", "shipment_id"]].drop_duplicates(["container_id", "reading_ts"]), on=["container_id", "reading_ts"], how="left")
    roll = roll.dropna(subset=["temp_pen", "rh_pen"], how="all")
    if roll.empty:
        return pd.DataFrame(columns=["container_id", "shipment_id", "as_of_ts", "health_score", "category", "temperature_score", "humidity_score",
                                     "vibration_score", "mean_temp_dev_c", "mean_rh_dev_pct", "mean_vibration_excess_g", "window_readings",
                                     "capped", "main_driver", "explanation"])
    roll["temperature_score"] = 100 * (1 - roll["temp_pen"])
    roll["humidity_score"] = 100 * (1 - roll["rh_pen"])
    roll["vibration_score"] = 100 * (1 - roll["vib_pen"])
    w = h["weights"]
    num = sum(roll[f"{k}_score"].fillna(0) * w[k] * roll[f"{k}_score"].notna() for k in w)
    den = sum(w[k] * roll[f"{k}_score"].notna() for k in w)
    roll["health_score"] = (num / den.replace(0, np.nan)).round(2)
    # a single failing variable must not be hidden by healthy ones: cap the overall score
    worst = roll[["temperature_score", "humidity_score", "vibration_score"]].min(axis=1)
    roll["capped"] = worst <= h["failure_floor"]
    roll.loc[roll["capped"], "health_score"] = roll.loc[roll["capped"], "health_score"].clip(upper=h["failure_cap"])
    roll["category"] = roll["health_score"].map(lambda s: classify_health(s, cfg))
    roll = roll.rename(columns={"temp_dev": "mean_temp_dev_c", "rh_dev": "mean_rh_dev_pct", "vib_ex": "mean_vibration_excess_g", "reading_ts": "as_of_ts"})
    exp = roll.apply(lambda r: _explain(r, cfg), axis=1, result_type="expand")
    roll["main_driver"], roll["explanation"] = exp[0], exp[1]
    keep = ["container_id", "shipment_id", "as_of_ts", "health_score", "category", "temperature_score", "humidity_score", "vibration_score",
            "mean_temp_dev_c", "mean_rh_dev_pct", "mean_vibration_excess_g", "window_readings", "capped", "main_driver", "explanation"]
    return roll[keep].sort_values(["container_id", "as_of_ts"]).reset_index(drop=True)


def current_health(timeline: pd.DataFrame) -> pd.DataFrame:
    """Latest score per container (worst first)."""
    return timeline.sort_values("as_of_ts").groupby("container_id", as_index=False).last().sort_values("health_score").reset_index(drop=True)


def health_history(timeline: pd.DataFrame) -> pd.DataFrame:
    """One score per container per hour (the last reading of each hour) - what is persisted."""
    t = timeline.assign(hour=timeline["as_of_ts"].dt.floor("h"))
    return t.sort_values("as_of_ts").groupby(["container_id", "hour"], as_index=False).last().drop(columns="hour")


def save_health_history(timeline: pd.DataFrame, store: Store | None = None) -> int:
    store = store or Store()
    h = health_history(timeline).assign(computed_at=pd.Timestamp.now("UTC").tz_localize(None))
    return store.upsert_df(TABLE, h, ["container_id", "as_of_ts"])


def load_health_history(store: Store | None = None, containers: list[str] | None = None) -> pd.DataFrame:
    df = (store or Store()).read_table(TABLE)
    if containers and not df.empty:
        df = df[df["container_id"].isin(containers)]
    return df


def health_summary(current: pd.DataFrame) -> dict:
    counts = current["category"].value_counts()
    out = {c: int(counts.get(c, 0)) for c in CATEGORIES}
    out["average_score"] = round(float(current["health_score"].mean()), 1) if len(current) else float("nan")
    return out


if __name__ == "__main__":      # python -m analytics.health  -> compute + persist hourly history for the sample data
    from analytics.pipeline import run_pipeline
    from common.config import load_settings
    cfg = load_settings(); r = run_pipeline(cfg)
    tl = health_timeline(r["readings"], cfg)
    print("rows persisted:", save_health_history(tl))
    print(current_health(tl)[["container_id", "health_score", "category", "main_driver"]].to_string(index=False))
