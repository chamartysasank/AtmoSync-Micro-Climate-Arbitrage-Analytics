"""Spoilage-risk forecasting (Feature 3).

HEURISTIC, NOT VALIDATED.  The forecast projects recent temperature/humidity trends forward (damped linear extrapolation),
converts the projected conditions into the existing shelf-life burn rate (Q10 rule, analytics/engine.py) and re-evaluates
the existing risk score at +6/12/24/48 h.  Nothing here was trained or validated against measured avocado spoilage data.

Evidence levels used in outputs:
  SOURCE-BASED  : Q10 range, storage ranges (cited in docs/dataset_research)
  ASSUMPTION    : trend damping, scenarios, weights, retail shelf-life requirement
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from analytics.engine import burn_rate_at, risk_score, risk_category

DISCLAIMER = ("HEURISTIC ESTIMATE - extrapolates recent sensor trends through the project's shelf-life budget model. "
              "It is not a scientifically validated spoilage prediction.")


def _trend(g: pd.DataFrame, col: str, f: dict) -> tuple[float, float, float]:
    """(current level, slope per hour, std) for the trailing window of one container."""
    last_ts = g["reading_ts"].max()
    w = g[g["reading_ts"] >= last_ts - pd.Timedelta(hours=f["trend_window_hours"])][["reading_ts", col]].dropna()
    level = float(g[col].dropna().tail(f["smoothing_points"]).mean())
    if len(w) < f["min_trend_points"]:
        return level, 0.0, float(w[col].std()) if len(w) > 1 else 0.0
    x = (w["reading_ts"] - last_ts).dt.total_seconds().to_numpy() / 3600.0
    slope = float(np.polyfit(x, w[col].to_numpy(), 1)[0])
    return level, slope, float(w[col].std())


def forecast_risk(readings: pd.DataFrame, status: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Long table: one row per container x scenario x horizon (horizon 0 = now)."""
    f, q = cfg["forecast"], cfg["quality_model"]
    base_h = q["base_shelf_life_days"] * 24.0
    horizons = sorted(set(f["horizons_hours"]))
    max_h = int(max(horizons))
    rows = []
    for _, s in status.iterrows():
        g = readings[readings["container_id"] == s["container_id"]].sort_values("reading_ts")
        if g.empty:
            continue
        T0, dT, sT = _trend(g, "temperature_c", f)
        R0, dR, sR = _trend(g, "humidity_pct", f)
        for name, sc in f["scenarios"].items():
            k = np.arange(0, max_h + 1)
            slope_on = 1.0 if sc["use_trend"] else 0.0
            T = np.clip(T0 + dT * f["trend_damping"] * slope_on * k + sc["sigma"] * sT, *f["temp_bounds_c"])
            R = np.clip(R0 + dR * f["trend_damping"] * slope_on * k - sc["sigma"] * sR, *f["rh_bounds_pct"])
            rate = np.asarray(burn_rate_at(T, R, cfg), dtype=float)
            cum = np.concatenate([[0.0], np.cumsum((rate[:-1] + rate[1:]) / 2.0 / base_h)])     # trapezoid, 1 h steps
            consumed = np.clip(s["life_consumed_fraction"] + cum, 0, 1)
            remaining = base_h * (1 - consumed)
            below = remaining <= q["required_retail_shelf_hours"]
            crossing = float(np.argmax(below)) if below.any() and not below[0] else (0.0 if below[0] else np.nan)
            for h in [0] + horizons:
                i = int(h)
                window = max(remaining[i] - q["required_retail_shelf_hours"], 0) / max(rate[i], 0.01)
                slack = window - max(s["hours_to_destination"] - h, 0)
                score = risk_score(rate[i], slack, s["excursion_share"], consumed[i], cfg)
                rows.append(dict(container_id=s["container_id"], shipment_id=s["shipment_id"], scenario=name, horizon_h=h,
                                 projected_temp_c=T[i], projected_rh_pct=R[i], projected_burn_rate=rate[i],
                                 life_consumed_fraction=consumed[i], remaining_life_hours=remaining[i], quality_window_hours=window,
                                 slack_hours=slack, risk_score=score, risk_category=risk_category(slack, score, cfg),
                                 below_quality_threshold=bool(below[i]), hours_until_threshold=crossing,
                                 arrived_by_horizon=bool(h >= s["hours_to_destination"]),
                                 evidence_level="HEURISTIC (not validated)"))
    return pd.DataFrame(rows)


def forecast_summary(fc: pd.DataFrame, scenario: str = "trend") -> pd.DataFrame:
    """Container x horizon matrix of risk categories for one scenario."""
    d = fc[(fc["scenario"] == scenario) & (fc["horizon_h"] > 0)]
    return d.pivot(index="container_id", columns="horizon_h", values="risk_category").rename(columns=lambda h: f"+{int(h)}h").reset_index()


def forecast_assumptions(cfg: dict) -> pd.DataFrame:
    f, q = cfg["forecast"], cfg["quality_model"]
    return pd.DataFrame([
        ("Shelf-life budget model", f"base {q['base_shelf_life_days']} d, Q10 {q['q10']}", "SOURCE-BASED ranges (WFLO 2-4 wk; UC ANR 2-3x per 10 C); point values are assumptions"),
        ("Required shelf life on arrival", f"{q['required_retail_shelf_hours']} h", "ASSUMPTION"),
        ("Trend window / damping", f"{f['trend_window_hours']} h / {f['trend_damping']}", "ASSUMPTION"),
        ("Scenarios", ", ".join(f["scenarios"]), "ASSUMPTION (what-if cases, not probabilities)"),
        ("Validation against measured spoilage", "none", "NOT VALIDATED - no public avocado transit-spoilage ground truth was used"),
    ], columns=["Item", "Value", "Evidence level"])


if __name__ == "__main__":
    from analytics.pipeline import run_pipeline
    from common.config import load_settings
    cfg = load_settings(); r = run_pipeline(cfg)
    print(DISCLAIMER); print(forecast_summary(forecast_risk(r["readings"], r["status"], cfg)).to_string(index=False))
