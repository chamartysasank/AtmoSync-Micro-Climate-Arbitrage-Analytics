"""Route comparison engine (Feature 4).

For each container it evaluates every (destination market x route profile) combination from the container's CURRENT
position and compares it with the baseline = original destination on the baseline (DIRECT) profile.
Profiles in data/sample/route_profiles.csv are SAMPLE/ILLUSTRATIVE (no real routing data was available).
With the DIRECT profile the numbers equal the Phase 1 arbitrage options exactly (tested).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from analytics.geo import haversine_km
from analytics.engine import latest_market_prices
from common.config import abs_path


def load_profiles(cfg: dict, path: str | None = None) -> pd.DataFrame:
    return pd.read_csv(path or abs_path(cfg["routes"]["profiles_file"]))


def compare_routes(status: pd.DataFrame, locations: pd.DataFrame, profiles: pd.DataFrame, prices: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    q, a, sim, r = cfg["quality_model"], cfg["arbitrage"], cfg["simulator"], cfg["routes"]
    latest = latest_market_prices(prices)
    mk = locations[locations["is_market"]].set_index("location_id")
    rows = []
    for _, c in status.iterrows():
        for _, p in latest[latest["commodity_id"] == c["commodity_id"]].iterrows():
            m = mk.loc[p["market_id"]]
            base_km = float(haversine_km(c["last_latitude"], c["last_longitude"], m["latitude"], m["longitude"])) * sim["road_factor"]
            for _, pr in profiles.iterrows():
                km = base_km * pr["distance_multiplier"]
                hours = km / pr["speed_kmph"]
                burn_mult = 1 + r["exposure_sensitivity"] * (pr["ambient_exposure_index"] - r["baseline_exposure_index"])
                eff_rate = c["recent_burn_rate"] * burn_mult
                rem = c["remaining_life_hours"] - hours * eff_rate
                haircut = r["vibration_haircut_max"] * max(pr["vibration_index"] - r["baseline_vibration_index"], 0)
                mult = q["salvage_value_fraction"] + (1 - q["salvage_value_fraction"]) * float(np.clip(rem / q["required_retail_shelf_hours"], 0, 1))
                mult = max(mult - haircut, 0.0)
                is_orig = p["market_id"] == c["planned_destination_id"]
                gross = p["price_modal_usd_kg"] * c["quantity_kg"]
                transport = km * c["quantity_kg"] / 1000.0 * a["transport_usd_per_tonne_km"] * pr["cost_multiplier"]
                handling = c["quantity_kg"] * a["handling_usd_per_kg"]
                fee = 0.0 if is_orig else a["reroute_fixed_fee_usd"]
                rows.append(dict(container_id=c["container_id"], shipment_id=c["shipment_id"], market_id=p["market_id"], profile_id=pr["profile_id"],
                                 is_original_destination=bool(is_orig), is_baseline=bool(is_orig and pr["profile_id"] == r["baseline_profile"]),
                                 distance_km=km, travel_hours=hours, price_modal_usd_kg=p["price_modal_usd_kg"], exposure_index=pr["ambient_exposure_index"],
                                 effective_burn_rate=eff_rate, remaining_life_at_arrival_h=rem,
                                 arrival_status=("Fresh enough" if rem >= q["required_retail_shelf_hours"] else "Degraded" if rem > 0 else "Spoiled"),
                                 quality_multiplier=mult, expected_value_usd=gross * mult, transport_cost_usd=transport,
                                 handling_cost_usd=handling, reroute_fee_usd=fee, net_value_usd=gross * mult - transport - handling - fee))
    df = pd.DataFrame(rows)
    base = df[df["is_baseline"]].set_index("container_id")[["net_value_usd", "transport_cost_usd", "remaining_life_at_arrival_h"]]
    base.columns = ["baseline_net_usd", "baseline_transport_usd", "baseline_remaining_h"]
    df = df.join(base, on="container_id")
    df["benefit_vs_baseline_usd"] = df["net_value_usd"] - df["baseline_net_usd"]
    df["rerouting_cost_usd"] = df["reroute_fee_usd"] + (df["transport_cost_usd"] - df["baseline_transport_usd"])   # fee + incremental transport
    return df


def _money(x: float) -> str:
    return f"-${abs(x):,.0f}" if x < 0 else f"${x:,.0f}"


def _explain(best: pd.Series, base: pd.Series, changed: bool, none_ok: bool) -> str:
    if not changed:
        if base["arrival_status"] == "Fresh enough":
            return (f"Keep the current route ({base['market_id']} via {base['profile_id']}): it arrives with {base['remaining_life_at_arrival_h']:.0f} h of shelf life "
                    f"(enough), so a higher price elsewhere alone does not justify rerouting (see Market Analytics for price-only margins).")
        return (f"Keep the current route ({base['market_id']} via {base['profile_id']}): no alternative beats it by the required margin"
                f"{'' if base['arrival_status'] == 'Fresh enough' else ', although this route arrives ' + base['arrival_status'].lower()}. "
                f"Arrival life {base['remaining_life_at_arrival_h']:.0f} h, net ${base['net_value_usd']:,.0f}.")
    txt = (f"Switch to {best['market_id']} via {best['profile_id']}: arrives in {best['travel_hours']:.1f} h with {best['remaining_life_at_arrival_h']:.0f} h of shelf life "
           f"({best['arrival_status'].lower()}) versus {base['remaining_life_at_arrival_h']:.0f} h on the current route ({base['arrival_status'].lower()}). "
           f"Net value {_money(best['net_value_usd'])} vs {_money(base['net_value_usd'])} ({_money(best['benefit_vs_baseline_usd'])} better); "
           f"rerouting cost vs the current route (fee + incremental transport) {_money(best['rerouting_cost_usd'])}; "
           f"corridor exposure index {best['exposure_index']:.2f} (illustrative).")
    return txt + ("" if none_ok else " No option arrives fresh enough; this is the least-bad choice.")


def recommend_routes(options: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """One recommendation per container with an explanation. Prefers options that arrive with enough shelf life."""
    a, q = cfg["arbitrage"], cfg["quality_model"]
    out = []
    for cid, g in options.groupby("container_id"):
        base = g[g["is_baseline"]].iloc[0]
        ok = g[g["remaining_life_at_arrival_h"] >= q["required_retail_shelf_hours"]]
        pool = ok if len(ok) else g
        best = pool.sort_values(["net_value_usd", "market_id", "profile_id"], ascending=[False, True, True]).iloc[0]
        threshold = max(a["min_benefit_usd"], a["min_benefit_pct"] * abs(base["net_value_usd"]))
        # same rule as Phase 1: only change when the CURRENT route would degrade the fruit; a higher price alone never triggers it
        degrading = base["remaining_life_at_arrival_h"] < q["required_retail_shelf_hours"]
        changed = degrading and (not best["is_baseline"]) and best["benefit_vs_baseline_usd"] >= threshold
        chosen = best if changed else base
        out.append(dict(container_id=cid, shipment_id=base["shipment_id"], recommendation="REROUTE / CHANGE ROUTE" if changed else "KEEP CURRENT ROUTE",
                        recommended_market=chosen["market_id"], recommended_profile=chosen["profile_id"], net_value_usd=chosen["net_value_usd"],
                        baseline_net_value_usd=base["net_value_usd"], benefit_usd=chosen["net_value_usd"] - base["net_value_usd"],
                        rerouting_cost_usd=chosen["rerouting_cost_usd"], arrival_life_hours=chosen["remaining_life_at_arrival_h"],
                        baseline_arrival_life_hours=base["remaining_life_at_arrival_h"], benefit_threshold_usd=threshold,
                        explanation=_explain(best, base, changed, len(ok) > 0)))
    return pd.DataFrame(out).sort_values("benefit_usd", ascending=False).reset_index(drop=True)


if __name__ == "__main__":
    from analytics.pipeline import run_pipeline
    from common.config import load_settings
    cfg = load_settings(); r = run_pipeline(cfg)
    rec = recommend_routes(compare_routes(r["status"], r["locations"], load_profiles(cfg), pd.read_csv(abs_path(cfg["paths"]["sample_dir"]) / "market_prices.csv"), cfg), cfg)
    print(rec[["container_id", "recommendation", "recommended_market", "recommended_profile", "benefit_usd"]].to_string(index=False)); print(rec.iloc[0]["explanation"])
