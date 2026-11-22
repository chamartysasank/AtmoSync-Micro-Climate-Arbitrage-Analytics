"""IoT simulator for refrigerated containers carrying Hass avocados.

EVERYTHING produced here is SIMULATED. Setpoints come from cited storage guidance
(see config/settings.yaml); fault patterns (drift, door-open, ...) are illustrative.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

from analytics.geo import haversine_km

SCENARIOS = ["normal", "cooling_drift", "compressor_failure", "low_humidity",
             "door_open", "sensor_dropout"]


@dataclass
class ContainerPlan:
    container_id: str
    shipment_id: str
    origin_id: str
    destination_id: str
    scenario: str
    progress: float            # fraction of the route completed at 'end_ts'
    quantity_kg: float
    pre_loading_life_consumed: float


# Fixed demo fleet: (scenario, origin, destination, progress)
DEFAULT_FLEET = [
    ("normal", "PHARR_TX", "CHICAGO", 0.55), ("normal", "PHARR_TX", "ATLANTA", 0.50),
    ("normal", "OTAY_MESA_CA", "DENVER", 0.60), ("normal", "OTAY_MESA_CA", "SEATTLE", 0.45),
    ("normal", "PHARR_TX", "NEW_YORK", 0.40), ("normal", "OTAY_MESA_CA", "DALLAS", 0.50),
    ("cooling_drift", "PHARR_TX", "NEW_YORK", 0.50), ("cooling_drift", "PHARR_TX", "CHICAGO", 0.45),
    ("compressor_failure", "OTAY_MESA_CA", "CHICAGO", 0.40),
    ("low_humidity", "PHARR_TX", "ATLANTA", 0.55),
    ("door_open", "OTAY_MESA_CA", "DENVER", 0.50),
    ("sensor_dropout", "PHARR_TX", "CHICAGO", 0.50),
]


# SIMULATED assumption: share of shelf life already used before loading (harvest-to-loading delay,
# fruit maturity). Faulty containers carry fruit that is further along so that quality windows
# become short enough for the demo to show at-risk shipments. Real data would replace this.
PRE_LOADING_RANGE = {"normal": (0.03, 0.12), "cooling_drift": (0.60, 0.70), "compressor_failure": (0.68, 0.76),
                     "low_humidity": (0.62, 0.70), "door_open": (0.66, 0.74), "sensor_dropout": (0.45, 0.55)}


def build_fleet(locations: pd.DataFrame, cfg: dict) -> tuple[list[ContainerPlan], pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(cfg["simulator"]["seed"])
    loc = locations.set_index("location_id")
    plans, ship_rows, cont_rows = [], [], []
    end_ts = pd.Timestamp(cfg["simulator"]["end_ts"])
    for i, (scen, o, d, prog) in enumerate(DEFAULT_FLEET, start=1):
        cid, sid = f"CNT-{i:03d}", f"SHP-{i:03d}"
        km = haversine_km(loc.loc[o, "latitude"], loc.loc[o, "longitude"],
                          loc.loc[d, "latitude"], loc.loc[d, "longitude"]) * cfg["simulator"]["road_factor"]
        transit_h = km / cfg["simulator"]["avg_speed_kmph"]
        depart = end_ts - pd.Timedelta(hours=prog * transit_h)
        qty = float(rng.choice([18000, 20000, 22000]))
        lo, hi = PRE_LOADING_RANGE[scen]
        pre = float(round(rng.uniform(lo, hi), 3))
        plans.append(ContainerPlan(cid, sid, o, d, scen, prog, qty, pre))
        ship_rows.append(dict(
            shipment_id=sid, container_id=cid, commodity_id="avocado_hass", quantity_kg=qty,
            origin_id=o, planned_destination_id=d,
            departure_ts=depart.strftime("%Y-%m-%dT%H:%M:%SZ"),
            planned_arrival_ts=(depart + pd.Timedelta(hours=transit_h)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            route_km=round(km, 1), pre_loading_life_consumed=pre, data_origin="SIMULATED"))
        cont_rows.append(dict(container_id=cid, sensor_id=f"SNS-{i:03d}", container_type="40ft reefer",
                              setpoint_temp_c=cfg["simulator"]["setpoint_temp_c"], data_origin="SIMULATED"))
    return plans, pd.DataFrame(ship_rows), pd.DataFrame(cont_rows)


def _temp_profile(scen: str, t_h: np.ndarray, base: float, rng) -> np.ndarray:
    n = len(t_h)
    temp = base + 0.25 * np.sin(2 * math.pi * t_h / 6.0) + rng.normal(0, 0.15, n)
    T = t_h[-1] if n else 0
    if scen == "cooling_drift":            # slow loss of cooling capacity in last 60% of trip
        start = 0.4 * T; temp += np.clip(t_h - start, 0, None) * 0.7
    elif scen == "compressor_failure":     # fast warm-up
        start = 0.2 * T; temp += np.clip((t_h - start) * 1.2, 0, 16)
    elif scen == "door_open":              # two short warm spikes
        for c in (0.35 * T, 0.7 * T):
            temp += 6.0 * np.exp(-((t_h - c) ** 2) / (2 * 0.6 ** 2))
    return temp


def _rh_profile(scen: str, t_h: np.ndarray, base: float, rng) -> np.ndarray:
    n = len(t_h)
    rh = base + rng.normal(0, 1.2, n)
    if scen == "low_humidity":
        rh -= np.clip(t_h - 0.3 * t_h[-1], 0, None) * 0.9
    elif scen in ("cooling_drift", "compressor_failure"):
        rh -= np.clip(t_h - 0.4 * t_h[-1], 0, None) * 0.25
    return np.clip(rh, 20, 100)


def generate_events(plans: list[ContainerPlan], shipments: pd.DataFrame, locations: pd.DataFrame,
                    cfg: dict) -> pd.DataFrame:
    """Return raw telemetry events (one row per reading) for every container."""
    sim = cfg["simulator"]
    rng = np.random.default_rng(sim["seed"] + 1)
    loc = locations.set_index("location_id")
    end_ts = pd.Timestamp(sim["end_ts"])
    interval = pd.Timedelta(minutes=sim["interval_minutes"])
    ship = shipments.set_index("container_id")
    frames = []
    for p in plans:
        dep = pd.Timestamp(ship.loc[p.container_id, "departure_ts"])
        ts = pd.date_range(dep, end_ts, freq=interval)
        if len(ts) < 2:
            continue
        t_h = (ts - dep).total_seconds().values / 3600.0
        temp = _temp_profile(p.scenario, t_h, sim["setpoint_temp_c"], rng)
        rh = _rh_profile(p.scenario, t_h, sim["setpoint_rh_pct"], rng)
        vib = np.abs(rng.lognormal(mean=-1.4, sigma=0.35, size=len(ts)))
        if p.scenario == "door_open":
            vib *= 1.0
        frac = (t_h / (t_h[-1] / max(p.progress, 1e-9))).clip(0, 1)   # route progress at each tick
        o, d = loc.loc[p.origin_id], loc.loc[p.destination_id]
        lat = o.latitude + (d.latitude - o.latitude) * frac
        lon = o.longitude + (d.longitude - o.longitude) * frac
        df = pd.DataFrame(dict(
            container_id=p.container_id, sensor_id=f"SNS-{p.container_id[-3:]}", shipment_id=p.shipment_id,
            reading_ts=ts.strftime("%Y-%m-%dT%H:%M:%SZ"), temperature_c=temp.round(2),
            humidity_pct=rh.round(1), vibration_g=vib.round(3),
            latitude=np.round(lat, 4), longitude=np.round(lon, 4), source="SIMULATED"))
        if p.scenario == "sensor_dropout":   # a 3-hour comms blackout + a few nulls
            cut = (t_h > 0.5 * t_h[-1]) & (t_h < 0.5 * t_h[-1] + 3)
            df = df[~cut].copy()
            idx = rng.choice(df.index, size=4, replace=False)
            df.loc[idx, "temperature_c"] = np.nan
        frames.append(df)
    ev = pd.concat(frames, ignore_index=True)
    if sim.get("inject_faults", True):
        ev = _inject_faults(ev, rng)
    ev.insert(0, "event_id", ev["container_id"] + "|" + ev["sensor_id"] + "|" + ev["reading_ts"])
    return ev.sort_values(["reading_ts", "container_id"]).reset_index(drop=True)


def _inject_faults(ev: pd.DataFrame, rng) -> pd.DataFrame:
    """Add realistic data-quality problems so the cleaning layer has something to do."""
    ev = ev.copy()
    n = len(ev)
    dup = ev.sample(frac=0.01, random_state=int(rng.integers(1_000_000)))          # duplicates
    bad_idx = rng.choice(ev.index, size=max(3, n // 400), replace=False)
    ev.loc[bad_idx[: len(bad_idx) // 2], "temperature_c"] = -999.0                 # sensor sentinel
    ev.loc[bad_idx[len(bad_idx) // 2:], "humidity_pct"] = 140.0                    # impossible RH
    return pd.concat([ev, dup], ignore_index=True)


def stream_events(plans, shipments, locations, cfg):
    """Yield events as dicts in time order (feed to Kafka producer or a local sink)."""
    ev = generate_events(plans, shipments, locations, cfg)
    for rec in ev.to_dict(orient="records"):
        yield {k: (None if (isinstance(v, float) and math.isnan(v)) else v) for k, v in rec.items()}
