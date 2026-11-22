"""Shipment replay and simulation controls (Feature 8). All generated data is SIMULATED.

* resolve_params()      : preset + overrides -> scenario parameters (presets live in config/features/simulation.yaml)
* simulate_container()  : raw telemetry for ONE container; same schema as the Phase 1 simulator output
* run_scenario()        : simulated telemetry -> existing cleaning / engine / health / anomaly / forecast modules
* compare_scenarios()   : normal vs abnormal on identical random noise (differences come only from the injected fault)
* replay_status_at(), replay_timeline() : historical replay - what did the system know at time T?
* compare_containers()  : side-by-side metrics for two containers of an existing dataset
"""
from __future__ import annotations
import copy
import numpy as np
import pandas as pd
from analytics import engine as E
from analytics.anomaly import detect_anomalies
from analytics.forecast import forecast_risk
from analytics.geo import haversine_km
from analytics.health import health_timeline, current_health
from ingestion.cleaning import clean_sensor_events


def resolve_params(preset: str, cfg: dict, **overrides) -> dict:
    lab = cfg["simulation_lab"]
    if preset not in lab["presets"]:
        raise KeyError(f"unknown preset {preset!r}; choose from {sorted(lab['presets'])}")
    p = copy.deepcopy({**lab["defaults"], **lab["presets"][preset]})
    for k, v in overrides.items():
        if k not in p and k not in ("spikes", "drift", "humidity", "vibration_bursts"):
            raise KeyError(f"unknown parameter {k!r}")
        p[k] = v
    p["preset"] = preset
    return p


def _bump(t: np.ndarray, start: float, duration: float, magnitude: float) -> np.ndarray:
    """Smooth pulse: Gaussian with full-width-at-half-maximum = duration, centred in the interval."""
    centre, sigma = start + duration / 2.0, max(duration, 1e-6) / 2.355
    return magnitude * np.exp(-((t - centre) ** 2) / (2 * sigma ** 2))


def simulate_container(params: dict, locations: pd.DataFrame, cfg: dict, container_id: str = "SIM-001") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (raw events, one-row shipments frame)."""
    sim = cfg["simulator"]; loc = locations.set_index("location_id")
    o, d = loc.loc[params["origin_id"]], loc.loc[params["destination_id"]]
    km = float(haversine_km(o.latitude, o.longitude, d.latitude, d.longitude)) * sim["road_factor"]
    transit_h = km / sim["avg_speed_kmph"]
    end = pd.Timestamp(sim["end_ts"]).tz_localize(None) if pd.Timestamp(sim["end_ts"]).tzinfo else pd.Timestamp(sim["end_ts"])
    elapsed_h = params["progress"] * transit_h
    dep = end - pd.Timedelta(hours=elapsed_h)
    ts = pd.date_range(dep, end, freq=pd.Timedelta(minutes=sim["interval_minutes"]))
    t = (ts - dep).total_seconds().to_numpy() / 3600.0
    rng = np.random.default_rng(params["seed"])
    temp_noise = rng.normal(0, params["temp_noise_c"], len(t)); rh_noise = rng.normal(0, params["rh_noise_pct"], len(t))
    vib = rng.lognormal(np.log(params["vibration_median_g"]), params["vibration_sigma"], len(t))      # all noise drawn first => common random numbers
    temp = sim["setpoint_temp_c"] + 0.25 * np.sin(2 * np.pi * t / 6.0) + temp_noise
    rh = sim["setpoint_rh_pct"] + rh_noise
    for sp in params["spikes"]:
        temp = temp + _bump(t, sp["start_frac"] * elapsed_h, sp["duration_h"], sp["magnitude_c"])
    if params["drift"]:
        dr = params["drift"]; temp = temp + np.clip((t - dr["start_frac"] * elapsed_h) * dr["rate_c_per_h"], 0, dr["max_add_c"])
    h = params["humidity"]
    if h["fluctuation_amp_pct"]:
        rh = rh + h["fluctuation_amp_pct"] * np.sin(2 * np.pi * t / h["period_h"])
    if h["drop_rate_pct_per_h"]:
        rh = rh - np.clip(t - h["drop_start_frac"] * elapsed_h, 0, None) * h["drop_rate_pct_per_h"]
    for vb in params["vibration_bursts"]:
        s0 = vb["start_frac"] * elapsed_h; vib = np.where((t >= s0) & (t <= s0 + vb["duration_h"]), vib * vb["multiplier"], vib)
    frac = np.clip(t / max(elapsed_h, 1e-9), 0, 1) * params["progress"]
    sensor = f"SNS-{container_id[-3:]}"; shp = f"SHP-{container_id[-3:]}"
    iso = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    raw = pd.DataFrame(dict(event_id=[f"{container_id}|{sensor}|{x}" for x in iso], container_id=container_id, sensor_id=sensor, shipment_id=shp,
                            reading_ts=iso, temperature_c=temp.round(2), humidity_pct=np.clip(rh, 20, 100).round(1), vibration_g=vib.round(3),
                            latitude=np.round(o.latitude + (d.latitude - o.latitude) * frac, 4), longitude=np.round(o.longitude + (d.longitude - o.longitude) * frac, 4),
                            source="SIMULATED (lab)"))
    ship = pd.DataFrame([dict(shipment_id=shp, container_id=container_id, commodity_id="avocado_hass", quantity_kg=params["quantity_kg"], origin_id=params["origin_id"],
                              planned_destination_id=params["destination_id"], departure_ts=dep.strftime("%Y-%m-%dT%H:%M:%SZ"), route_km=round(km, 1),
                              pre_loading_life_consumed=params["pre_loading_consumed"], data_origin="SIMULATED (lab)")])
    return raw, ship


def run_scenario(params: dict, locations: pd.DataFrame, cfg: dict, container_id: str = "SIM-001") -> dict:
    raw, ship = simulate_container(params, locations, cfg, container_id)
    clean, rejected, _ = clean_sensor_events(raw, cfg)
    readings = E.add_reading_rates(clean, cfg)
    status = E.container_status(readings, ship, locations, cfg)
    health = current_health(health_timeline(readings, cfg))
    anomalies = detect_anomalies(raw, cfg)
    fc = forecast_risk(readings, status, cfg)
    return dict(params=params, raw=raw, shipment=ship, readings=readings, status=status, health=health, anomalies=anomalies, forecast=fc)


def scenario_metrics(res: dict) -> dict:
    s, h, a, fc = res["status"].iloc[0], res["health"].iloc[0], res["anomalies"], res["forecast"]
    f24 = fc[(fc["scenario"] == "trend") & (fc["horizon_h"] == 24)].iloc[0]
    return {"avg_temp_c": s["avg_temp_c"], "max_temp_c": s["max_temp_c"], "avg_humidity_pct": s["avg_humidity_pct"], "excursion_share": s["excursion_share"],
            "max_vibration_g": float(res["readings"]["vibration_g"].max()), "life_consumed_fraction": s["life_consumed_fraction"],
            "recent_burn_rate": s["recent_burn_rate"], "quality_window_hours": s["quality_window_hours"], "slack_hours": s["slack_hours"],
            "risk_score": s["risk_score"], "risk_category": s["risk_category"], "health_score": h["health_score"], "health_category": h["category"],
            "anomalies_total": len(a), "anomalies_critical": int((a["severity"] == "CRITICAL").sum()), "forecast_24h_category": f24["risk_category"]}


def compare_scenarios(normal: dict, abnormal: dict, locations: pd.DataFrame, cfg: dict) -> dict:
    """Both scenarios share the seed => identical noise; only the injected effects differ."""
    a = run_scenario(normal, locations, cfg, "SIM-001"); b = run_scenario(abnormal, locations, cfg, "SIM-002")
    ma, mb = scenario_metrics(a), scenario_metrics(b)
    table = pd.DataFrame({"metric": list(ma), "normal": list(ma.values()), "abnormal": list(mb.values())})
    num = table.apply(lambda r: isinstance(r["normal"], (int, float, np.floating, np.integer)), axis=1)
    table["difference"] = np.where(num, pd.to_numeric(table["abnormal"], errors="coerce") - pd.to_numeric(table["normal"], errors="coerce"), np.nan)
    return dict(normal=a, abnormal=b, table=table)


# ---------------------------------------------------------------------------------- historical replay
def replay_status_at(readings: pd.DataFrame, shipments: pd.DataFrame, locations: pd.DataFrame, cfg: dict, upto_ts) -> pd.DataFrame:
    """Container status using only readings up to `upto_ts` (what the system would have shown at that moment)."""
    sub = readings[readings["reading_ts"] <= pd.Timestamp(upto_ts)]
    return E.container_status(sub, shipments, locations, cfg) if len(sub) else pd.DataFrame()


def replay_timeline(readings: pd.DataFrame, shipments: pd.DataFrame, locations: pd.DataFrame, cfg: dict, step_hours: float = 2.0) -> pd.DataFrame:
    """Risk score/category per container at regular replay steps."""
    t0, t1 = readings["reading_ts"].min() + pd.Timedelta(hours=1), readings["reading_ts"].max()
    steps = list(pd.date_range(t0, t1, freq=pd.Timedelta(hours=step_hours))) + [t1]
    frames = []
    for t in dict.fromkeys(steps):
        st = replay_status_at(readings, shipments, locations, cfg, t)
        if len(st):
            frames.append(st[["container_id", "risk_score", "risk_category", "slack_hours", "life_consumed_fraction"]].assign(replay_ts=t))
    return pd.concat(frames, ignore_index=True)


def compare_containers(readings: pd.DataFrame, status: pd.DataFrame, a: str, b: str) -> pd.DataFrame:
    s = status.set_index("container_id"); rd = readings.set_index("container_id")
    def m(c):
        r = s.loc[c]; g = rd.loc[[c]]
        return {"avg_temp_c": r["avg_temp_c"], "max_temp_c": r["max_temp_c"], "avg_humidity_pct": r["avg_humidity_pct"], "excursion_share": r["excursion_share"],
                "max_vibration_g": float(g["vibration_g"].max()), "recent_burn_rate": r["recent_burn_rate"], "life_consumed_fraction": r["life_consumed_fraction"],
                "slack_hours": r["slack_hours"], "risk_score": r["risk_score"], "risk_category": r["risk_category"]}
    ma, mb = m(a), m(b)
    return pd.DataFrame({"metric": list(ma), a: list(ma.values()), b: list(mb.values())})


if __name__ == "__main__":
    from common.config import load_settings, abs_path
    cfg = load_settings(); loc = pd.read_csv(abs_path(cfg["paths"]["sample_dir"]) / "locations.csv")
    for name in cfg["simulation_lab"]["presets"]:
        if name == "normal": continue
        c = compare_scenarios(resolve_params("normal", cfg), resolve_params(name, cfg), loc, cfg)
        t = c["table"].set_index("metric"); print(f"{name:22s} risk {t.loc['risk_category','normal']}->{t.loc['risk_category','abnormal']}  health {t.loc['health_score','normal']:.0f}->{t.loc['health_score','abnormal']:.0f}  anomalies {t.loc['anomalies_total','normal']}->{t.loc['anomalies_total','abnormal']}")
