"""AtmoSync analytics engine (pandas reference implementation).

The same formulas are implemented in SQL in dbt_project/models (parity-tested).
Read docs/methodology/methodology.md for the reasoning. Short version:

  rate      = q10 ** ((max(T, chill_floor) - T_ref) / 10) * (1 + k * max(0, RH_min - RH) / 10)
  consumed  = sum(dt_hours * rate) / base_shelf_life_hours      (+ pre-loading consumption)
  window_h  = max(remaining_life_h - required_retail_shelf_h, 0) / recent_rate
  slack_h   = window_h - hours_to_destination
HEURISTIC, not a validated spoilage model.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from analytics.geo import haversine_km


def add_reading_rates(clean: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    q, th = cfg["quality_model"], cfg["thresholds"]
    df = clean.sort_values(["container_id", "reading_ts"]).copy()
    prev = df.groupby("container_id")["reading_ts"].shift(1)
    dt_h = (df["reading_ts"] - prev).dt.total_seconds() / 3600.0
    df["dt_hours"] = dt_h.fillna(0.0).clip(upper=q["max_gap_hours"])
    t_eff = df["temperature_c"].clip(lower=q["chill_floor_c"])
    rh_def = (th["rh_min_pct"] - df["humidity_pct"]).clip(lower=0)
    df["temp_excursion"] = ~df["temperature_c"].between(th["temp_min_c"], th["temp_max_c"])
    df["rh_excursion"] = ~df["humidity_pct"].between(th["rh_min_pct"], th["rh_max_pct"])
    df["is_excursion"] = df["temp_excursion"] | df["rh_excursion"]
    df["burn_rate"] = q["q10"] ** ((t_eff - q["reference_temp_c"]) / 10.0) * (1 + q["rh_penalty_per_10pct"] * rh_def / 10.0)
    base_h = q["base_shelf_life_days"] * 24.0
    df["life_consumed_increment"] = df["dt_hours"] * df["burn_rate"] / base_h
    return df


def risk_score(rate_recent: float, slack_h: float, excursion_share: float, consumed: float, cfg: dict) -> float:
    """0-100 ranking score (weights in settings.yaml -> risk.weights). Shared with analytics/forecast.py."""
    q, r = cfg["quality_model"], cfg["risk"]; w = r["weights"]
    burn_c = float(np.clip((rate_recent - 1) / (q["rate_cap"] - 1), 0, 1))
    margin_c = float(np.clip(1 - slack_h / r["slack_scale_hours"], 0, 1))
    return 100 * (w["burn"] * burn_c + w["margin"] * margin_c + w["excursion"] * excursion_share + w["consumed"] * consumed)


def risk_category(slack_h: float, score: float, cfg: dict) -> str:
    r = cfg["risk"]
    if slack_h <= 0: return "CRITICAL"
    if slack_h < r["high_slack_hours"]: return "HIGH"
    if score >= r["medium_score"]: return "MEDIUM"
    return "LOW"


def burn_rate_at(temp_c, rh_pct, cfg: dict):
    """Shelf-life burn rate for given conditions (same formula as add_reading_rates). Works on scalars or arrays."""
    q, th = cfg["quality_model"], cfg["thresholds"]
    t_eff = np.maximum(temp_c, q["chill_floor_c"])
    rh_def = np.maximum(th["rh_min_pct"] - rh_pct, 0)
    return q["q10"] ** ((t_eff - q["reference_temp_c"]) / 10.0) * (1 + q["rh_penalty_per_10pct"] * rh_def / 10.0)


def container_status(readings: pd.DataFrame, shipments: pd.DataFrame, locations: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    q, r, sim = cfg["quality_model"], cfg["risk"], cfg["simulator"]
    base_h = q["base_shelf_life_days"] * 24.0
    as_of = readings["reading_ts"].max()
    loc = locations.set_index("location_id")
    rows = []
    for cid, g in readings.groupby("container_id"):
        last = g.iloc[-1]
        recent = g[g["reading_ts"] >= last["reading_ts"] - pd.Timedelta(minutes=q["recent_window_minutes"])]
        s = shipments.set_index("container_id").loc[cid]
        consumed = float(min(max(s["pre_loading_life_consumed"] + g["life_consumed_increment"].sum(), 0), 1))
        rate_recent = float(recent["burn_rate"].mean())
        remaining_h = base_h * (1 - consumed)
        window_h = max(remaining_h - q["required_retail_shelf_hours"], 0.0) / max(rate_recent, 0.01)
        d = loc.loc[s["planned_destination_id"]]
        dist_km = float(haversine_km(last["latitude"], last["longitude"], d["latitude"], d["longitude"])) * sim["road_factor"]
        hours_to_dest = dist_km / sim["avg_speed_kmph"]
        slack_h = window_h - hours_to_dest
        score = risk_score(rate_recent, slack_h, float(g["is_excursion"].mean()), consumed, cfg)
        exc_share = float(g["is_excursion"].mean())
        cat = risk_category(slack_h, score, cfg)
        rows.append(dict(
            container_id=cid, shipment_id=s["shipment_id"], commodity_id=s["commodity_id"], quantity_kg=s["quantity_kg"],
            planned_destination_id=s["planned_destination_id"], as_of_ts=as_of, last_reading_ts=last["reading_ts"],
            minutes_since_last_reading=(as_of - last["reading_ts"]).total_seconds() / 60.0,
            reading_count=len(g), avg_temp_c=g["temperature_c"].mean(), max_temp_c=g["temperature_c"].max(),
            avg_humidity_pct=g["humidity_pct"].mean(), temp_excursion_count=int(g["temp_excursion"].sum()),
            rh_excursion_count=int(g["rh_excursion"].sum()), excursion_share=exc_share,
            life_consumed_fraction=consumed, remaining_life_hours=remaining_h, recent_burn_rate=rate_recent,
            quality_window_hours=window_h, distance_to_destination_km=dist_km, hours_to_destination=hours_to_dest,
            slack_hours=slack_h, risk_score=score, risk_category=cat,
            last_latitude=last["latitude"], last_longitude=last["longitude"]))
    return pd.DataFrame(rows).sort_values("risk_score", ascending=False).reset_index(drop=True)


def latest_market_prices(prices: pd.DataFrame) -> pd.DataFrame:
    p = prices.sort_values("price_date")
    return p.groupby(["commodity_id", "market_id"], as_index=False).last()


def arbitrage_options(status: pd.DataFrame, prices: pd.DataFrame, locations: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """One row per (container, candidate market) with quality-adjusted net value."""
    q, a, sim = cfg["quality_model"], cfg["arbitrage"], cfg["simulator"]
    latest = latest_market_prices(prices)
    mk = locations[locations["is_market"]].set_index("location_id")
    out = []
    for _, c in status.iterrows():
        cand = latest[latest["commodity_id"] == c["commodity_id"]]
        for _, p in cand.iterrows():
            m = mk.loc[p["market_id"]]
            dist = float(haversine_km(c["last_latitude"], c["last_longitude"], m["latitude"], m["longitude"])) * sim["road_factor"]
            transit_h = dist / sim["avg_speed_kmph"]
            rem_arr = c["remaining_life_hours"] - transit_h * c["recent_burn_rate"]
            mult = q["salvage_value_fraction"] + (1 - q["salvage_value_fraction"]) * float(np.clip(rem_arr / q["required_retail_shelf_hours"], 0, 1))
            is_orig = p["market_id"] == c["planned_destination_id"]
            gross = p["price_modal_usd_kg"] * c["quantity_kg"]
            value = gross * mult
            transport = dist * c["quantity_kg"] / 1000.0 * a["transport_usd_per_tonne_km"]
            handling = c["quantity_kg"] * a["handling_usd_per_kg"]
            fee = 0.0 if is_orig else a["reroute_fixed_fee_usd"]
            out.append(dict(container_id=c["container_id"], market_id=p["market_id"], is_original_destination=bool(is_orig),
                            price_modal_usd_kg=p["price_modal_usd_kg"], distance_km=dist, transit_hours=transit_h,
                            remaining_life_at_arrival_h=rem_arr, quality_multiplier=mult, expected_gross_value_usd=gross,
                            expected_quality_adjusted_value_usd=value, transport_cost_usd=transport,
                            handling_cost_usd=handling, reroute_fee_usd=fee,
                            net_value_usd=value - transport - handling - fee))
    opt = pd.DataFrame(out)
    base = opt[opt["is_original_destination"]].set_index("container_id")["net_value_usd"].rename("original_net_value_usd")
    opt = opt.join(base, on="container_id")
    opt["benefit_vs_original_usd"] = opt["net_value_usd"] - opt["original_net_value_usd"]
    return opt


def arbitrage_recommendations(status: pd.DataFrame, options: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    a = cfg["arbitrage"]
    rows = []
    for _, c in status.iterrows():
        o = options[options["container_id"] == c["container_id"]]
        orig = o[o["is_original_destination"]].iloc[0]
        alts = o[~o["is_original_destination"]].sort_values(["benefit_vs_original_usd", "market_id"], ascending=[False, True])
        best = alts.iloc[0]
        threshold = max(a["min_benefit_usd"], a["min_benefit_pct"] * abs(orig["original_net_value_usd"]))
        degrading = orig["quality_multiplier"] < 1.0
        if best["benefit_vs_original_usd"] >= threshold and degrading:
            action = "REROUTE"
        elif c["risk_category"] in ("MEDIUM", "HIGH", "CRITICAL"):
            action = "MONITOR"
        else:
            action = "NO_ACTION"
        rows.append(dict(container_id=c["container_id"], shipment_id=c["shipment_id"], risk_category=c["risk_category"],
                         original_destination=orig["market_id"], original_quality_multiplier=orig["quality_multiplier"],
                         original_net_value_usd=orig["original_net_value_usd"], best_alternative=best["market_id"],
                         best_alt_net_value_usd=best["net_value_usd"], best_benefit_usd=best["benefit_vs_original_usd"],
                         benefit_threshold_usd=threshold, recommended_action=action))
    return pd.DataFrame(rows)


def executive_kpis(status: pd.DataFrame, recs: pd.DataFrame) -> pd.DataFrame:
    rr = recs[recs["recommended_action"] == "REROUTE"]
    return pd.DataFrame([dict(
        total_containers=len(status),
        healthy_containers=int((status["risk_category"] == "LOW").sum()),
        at_risk_containers=int(status["risk_category"].isin(["MEDIUM", "HIGH", "CRITICAL"]).sum()),
        critical_alerts=int((status["risk_category"] == "CRITICAL").sum()),
        arbitrage_opportunities=len(rr), estimated_benefit_usd=float(rr["best_benefit_usd"].sum()))])


def hourly_series(readings: pd.DataFrame) -> pd.DataFrame:
    h = readings.assign(hour_ts=readings["reading_ts"].dt.floor("h"))
    return h.groupby(["container_id", "hour_ts"], as_index=False).agg(
        avg_temp_c=("temperature_c", "mean"), max_temp_c=("temperature_c", "max"),
        avg_humidity_pct=("humidity_pct", "mean"), avg_vibration_g=("vibration_g", "mean"),
        excursion_readings=("is_excursion", "sum"), reading_count=("event_id", "count"))
