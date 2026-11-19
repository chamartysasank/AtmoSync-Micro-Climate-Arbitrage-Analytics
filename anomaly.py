"""Sensor anomaly detection (Feature 1).

Works on RAW events (before cleaning) so missing / invalid readings are visible.
Every flagged reading carries a human-readable `reason`. Methods: configurable thresholds, rolling z-score,
rate of change, reporting gaps, stuck-sensor detection. Thresholds are heuristics (see config/features/anomaly.yaml).

    from analytics.anomaly import detect_anomalies
    anomalies = detect_anomalies(raw_events_df, cfg)
"""
from __future__ import annotations
import numpy as np
import pandas as pd

SENTINELS = (-999.0, -9999.0)
SEVERITY_ORDER = {"WARNING": 1, "CRITICAL": 2}
METRICS = {"temperature_c": ("Temperature", "°C"), "humidity_pct": ("Humidity", "%"), "vibration_g": ("Vibration", "g")}
COLUMNS = ["anomaly_id", "event_id", "container_id", "shipment_id", "reading_ts", "metric", "value", "anomaly_type",
           "severity", "reason", "limit", "z_score", "rate_per_hour"]


def _limits(cfg: dict) -> dict:
    a, t = cfg["anomaly"], cfg["thresholds"]
    pick = lambda v, d: d if v is None else v
    return {"temperature_c": (pick(a["temp_warn_min_c"], t["temp_min_c"]), pick(a["temp_warn_max_c"], t["temp_max_c"]), a["temp_critical_margin_c"]),
            "humidity_pct": (pick(a["rh_warn_min_pct"], t["rh_min_pct"]), pick(a["rh_warn_max_pct"], t["rh_max_pct"]), a["rh_critical_margin_pct"]),
            "vibration_g": (None, a["vibration_warn_g"], a["vibration_critical_g"] - a["vibration_warn_g"])}


def _plausible(cfg: dict) -> dict:
    t = cfg["thresholds"]
    return {"temperature_c": tuple(t["valid_temp_range_c"]), "humidity_pct": tuple(t["valid_rh_range_pct"]),
            "vibration_g": tuple(t["valid_vibration_range_g"])}


def _row(r, metric, atype, severity, reason, value=np.nan, limit=None, z=np.nan, rate=np.nan):
    return dict(anomaly_id=f"{r['event_id']}|{metric}|{atype}", event_id=r["event_id"], container_id=r["container_id"],
                shipment_id=r.get("shipment_id"), reading_ts=r["reading_ts"], metric=metric, value=value, anomaly_type=atype,
                severity=severity, reason=reason, limit=limit, z_score=z, rate_per_hour=rate)


def detect_anomalies(raw: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Return one row per (reading, metric, anomaly type). Empty DataFrame (with columns) if nothing is flagged."""
    a = cfg["anomaly"]
    df = raw.copy()
    df["reading_ts"] = pd.to_datetime(df["reading_ts"], utc=True, errors="coerce").dt.tz_localize(None)
    for col in ("event_id", "container_id", "sensor_id", "shipment_id"):
        if col not in df.columns:
            df[col] = None
    out: list[dict] = []
    lim, plaus = _limits(cfg), _plausible(cfg)

    # ---- 1. invalid / missing readings -------------------------------------------------------------
    num, valid = {}, {}
    for m, (label, unit) in METRICS.items():
        raw_col = df[m] if m in df.columns else pd.Series(np.nan, index=df.index)
        numeric = pd.to_numeric(raw_col, errors="coerce")
        is_null = raw_col.isna()
        non_numeric = ~is_null & numeric.isna()
        sentinel = numeric.isin(SENTINELS)
        lo, hi = plaus[m]
        oor = numeric.notna() & ~sentinel & ~numeric.between(lo, hi)
        for idx in df.index[is_null]:
            out.append(_row(df.loc[idx], m, "missing_value", a["invalid_severity"], f"{label} value is missing (null)."))
        for idx in df.index[non_numeric]:
            out.append(_row(df.loc[idx], m, "invalid_reading", a["invalid_severity"], f"{label} value {raw_col[idx]!r} is not numeric."))
        for idx in df.index[sentinel]:
            out.append(_row(df.loc[idx], m, "invalid_reading", a["invalid_severity"],
                            f"{label} equals sensor error code {numeric[idx]:.0f}.", value=numeric[idx]))
        for idx in df.index[oor]:
            out.append(_row(df.loc[idx], m, "invalid_reading", a["invalid_severity"],
                            f"{label} {numeric[idx]:.2f} {unit} is outside the physically plausible range {lo} to {hi} {unit}.",
                            value=numeric[idx], limit=f"{lo}..{hi}"))
        valid[m] = numeric.notna() & ~sentinel & ~oor
        num[m] = numeric.where(valid[m])
    for idx in df.index[df["reading_ts"].isna()]:
        out.append(_row(df.loc[idx], "reading_ts", "invalid_reading", a["invalid_severity"], "Timestamp is missing or unparseable."))

    # ---- time-series checks on de-duplicated rows with a valid timestamp --------------------------
    ts_ok = df["reading_ts"].notna() & df["container_id"].notna()
    work = df[ts_ok].copy()
    for m in METRICS:
        work[m] = num[m][ts_ok]
    work = work.sort_values(["container_id", "reading_ts"]).drop_duplicates(["container_id", "sensor_id", "reading_ts"], keep="last")

    # ---- 2. threshold checks ------------------------------------------------------------------------
    for m, (label, unit) in METRICS.items():
        lo, hi, margin = lim[m]
        s = work[m]
        if m == "vibration_g":
            for idx in work.index[s > hi]:
                crit = s[idx] > hi + margin
                out.append(_row(work.loc[idx], m, "threshold", "CRITICAL" if crit else "WARNING",
                                f"{label} {s[idx]:.2f} g exceeds the {'critical' if crit else 'warning'} limit of "
                                f"{(hi + margin) if crit else hi:.2f} g.", value=s[idx], limit=hi + margin if crit else hi))
            continue
        for idx in work.index[s < lo]:
            d = lo - s[idx]; crit = d > margin
            out.append(_row(work.loc[idx], m, "threshold", "CRITICAL" if crit else "WARNING",
                            f"{label} {s[idx]:.2f} {unit} is {d:.2f} {unit} below the {lo:g} {unit} lower limit"
                            f"{' (more than the critical margin of %g)' % margin if crit else ''}.", value=s[idx], limit=lo))
        for idx in work.index[s > hi]:
            d = s[idx] - hi; crit = d > margin
            out.append(_row(work.loc[idx], m, "threshold", "CRITICAL" if crit else "WARNING",
                            f"{label} {s[idx]:.2f} {unit} is {d:.2f} {unit} above the {hi:g} {unit} upper limit"
                            f"{' (more than the critical margin of %g)' % margin if crit else ''}.", value=s[idx], limit=hi))

    # ---- 3. statistical (rolling z-score vs the previous window of the same container) --------------
    for m, (label, unit) in METRICS.items():
        g = work.groupby("container_id")[m]
        mean = g.transform(lambda x: x.rolling(a["stat_window"], min_periods=a["stat_min_periods"]).mean().shift(1))
        std = g.transform(lambda x: x.rolling(a["stat_window"], min_periods=a["stat_min_periods"]).std().shift(1))
        std = std.clip(lower=a["min_std"][m])
        z = (work[m] - mean) / std
        z_eff = z if m != "vibration_g" else z.where(z > 0)          # only unusually HIGH vibration is abnormal
        for idx in work.index[z_eff.abs() >= a["z_warn"]]:
            crit = abs(z_eff[idx]) >= a["z_critical"]
            out.append(_row(work.loc[idx], m, "statistical", "CRITICAL" if crit else "WARNING",
                            f"{label} {work.at[idx, m]:.2f} {unit} deviates {z_eff[idx]:+.1f} standard deviations from the previous "
                            f"{a['stat_window']} readings (mean {mean[idx]:.2f}).", value=work.at[idx, m], limit=a["z_critical" if crit else "z_warn"], z=z_eff[idx]))

    # ---- 4. rate of change per hour -------------------------------------------------------------------
    for m in ("temperature_c", "humidity_pct"):
        label, unit = METRICS[m]
        sub = work[work[m].notna()]
        dt_h = sub.groupby("container_id")["reading_ts"].diff().dt.total_seconds() / 3600.0
        rate = sub.groupby("container_id")[m].diff() / dt_h
        for idx in sub.index[(rate.abs() >= a["roc_warn"][m]) & (dt_h > 0)]:
            crit = abs(rate[idx]) >= a["roc_critical"][m]
            out.append(_row(sub.loc[idx], m, "rate_of_change", "CRITICAL" if crit else "WARNING",
                            f"{label} changed {rate[idx]:+.1f} {unit}/h since the previous reading "
                            f"(limit {a['roc_critical' if crit else 'roc_warn'][m]:g} {unit}/h).", value=sub.at[idx, m],
                            limit=a["roc_critical" if crit else "roc_warn"][m], rate=rate[idx]))

    # ---- 5. reporting gaps -----------------------------------------------------------------------------
    gap_min = work.groupby("container_id")["reading_ts"].diff().dt.total_seconds() / 60.0
    for idx in work.index[gap_min >= a["gap_warn_minutes"]]:
        crit = gap_min[idx] >= a["gap_critical_minutes"]
        out.append(_row(work.loc[idx], "reading_ts", "gap", "CRITICAL" if crit else "WARNING",
                        f"No readings for {gap_min[idx]:.0f} min before this reading (limit {a['gap_critical_minutes' if crit else 'gap_warn_minutes']} min).",
                        value=gap_min[idx], limit=a["gap_critical_minutes" if crit else "gap_warn_minutes"]))

    # ---- 6. stuck sensor (identical consecutive values) --------------------------------------------------
    for m in ("temperature_c", "humidity_pct"):
        label, unit = METRICS[m]
        g = work.groupby("container_id")[m]
        flat = (g.transform(lambda x: x.rolling(a["stuck_window"]).max()) == g.transform(lambda x: x.rolling(a["stuck_window"]).min()))
        flagged = work.index[flat & work[m].notna()]
        prev_flag = flat.groupby(work["container_id"]).shift(1, fill_value=False)
        for idx in flagged:
            if not prev_flag[idx]:                                          # report the first reading of a flat run only
                out.append(_row(work.loc[idx], m, "stuck_sensor", "WARNING",
                                f"{label} reported the identical value {work.at[idx, m]:.2f} {unit} for {a['stuck_window']} consecutive readings (possible stuck sensor).",
                                value=work.at[idx, m], limit=a["stuck_window"]))

    res = pd.DataFrame(out, columns=COLUMNS)
    if res.empty:
        return res
    res = res.drop_duplicates("anomaly_id").sort_values(["reading_ts", "container_id", "metric"], na_position="last").reset_index(drop=True)
    return res


def summarize_anomalies(anomalies: pd.DataFrame) -> pd.DataFrame:
    """Counts per container x severity (plus total)."""
    if anomalies.empty:
        return pd.DataFrame(columns=["container_id", "WARNING", "CRITICAL", "total"])
    p = anomalies.pivot_table(index="container_id", columns="severity", values="anomaly_id", aggfunc="count", fill_value=0)
    for c in ("WARNING", "CRITICAL"):
        if c not in p:
            p[c] = 0
    p["total"] = p["WARNING"] + p["CRITICAL"]
    return p[["WARNING", "CRITICAL", "total"]].reset_index().sort_values(["CRITICAL", "total"], ascending=False)


def anomaly_kpis(anomalies: pd.DataFrame, total_readings: int) -> dict:
    return {"total_anomalies": int(len(anomalies)), "critical": int((anomalies["severity"] == "CRITICAL").sum()),
            "warning": int((anomalies["severity"] == "WARNING").sum()),
            "containers_affected": int(anomalies["container_id"].nunique()),
            "anomaly_rate_pct": round(100 * anomalies["event_id"].nunique() / max(total_readings, 1), 2)}
