"""Alert management centre (Feature 6): generation, de-duplication, lifecycle, history, filtering.

Persistence: local DuckDB (schema ops, tables `alerts` and `alert_events`) via common/store.py.
One ACTIVE alert exists per (container, category); re-detection updates it (and escalates severity if needed),
re-detection after RESOLVED re-opens it.  Lifecycle: OPEN -> ACKNOWLEDGED -> RESOLVED (resolve is also allowed from OPEN).
Every change is written to `alert_events` (the alert history).
"""
from __future__ import annotations
import hashlib
import pandas as pd
from common.store import Store

SEVERITIES = ["WARNING", "CRITICAL"]
STATUSES = ["OPEN", "ACKNOWLEDGED", "RESOLVED"]
CATEGORIES = ["risk", "health", "anomaly", "forecast", "arbitrage", "data_quality", "system"]
CANDIDATE_COLS = ["container_id", "shipment_id", "category", "severity", "title", "message", "event_time"]
_RANK = {"WARNING": 1, "CRITICAL": 2}


def alert_id_for(container_id: str, category: str) -> str:
    return "AL-" + hashlib.sha1(f"{container_id}|{category}".encode()).hexdigest()[:10].upper()


# --------------------------------------------------------------------------- candidate generation
def collect_candidates(r: dict, cfg: dict, anomalies: pd.DataFrame | None = None, forecast: pd.DataFrame | None = None,
                       health: pd.DataFrame | None = None, extra: pd.DataFrame | None = None) -> pd.DataFrame:
    """Turn analytics results into alert candidates. Pre-computed pieces can be passed in; otherwise they are computed."""
    c = cfg["alert_center"]; rows = []
    status = r["status"]; ev = status["as_of_ts"].max()
    add = lambda cont, ship, cat, sev, title, msg: rows.append(dict(container_id=cont, shipment_id=ship, category=cat, severity=sev, title=title, message=msg, event_time=ev))

    for _, s in status.iterrows():                                                    # Phase 1 risk
        sev = "CRITICAL" if s["risk_category"] in c["risk"]["critical_categories"] else "WARNING" if s["risk_category"] in c["risk"]["warning_categories"] else None
        if sev:
            add(s["container_id"], s["shipment_id"], "risk", sev, f"Spoilage risk {s['risk_category']}",
                f"Risk score {s['risk_score']:.0f}; quality window {s['quality_window_hours']:.0f} h vs {s['hours_to_destination']:.0f} h to destination (slack {s['slack_hours']:.0f} h).")
    if health is None:
        from analytics.health import health_timeline, current_health
        health = current_health(health_timeline(r["readings"], cfg))
    for _, h in health.iterrows():                                                    # Feature 2
        sev = "CRITICAL" if h["health_score"] < c["health"]["critical_below"] else "WARNING" if h["health_score"] < c["health"]["warning_below"] else None
        if sev:
            add(h["container_id"], h["shipment_id"], "health", sev, f"Shipment health {h['category']} ({h['health_score']:.0f}/100)", h["explanation"])
    if anomalies is None:
        from analytics.anomaly import detect_anomalies
        anomalies = detect_anomalies(r["raw"], cfg)
    a = c["anomaly"]
    if not anomalies.empty:                                                           # Feature 1
        recent = anomalies[anomalies["reading_ts"] >= anomalies["reading_ts"].max() - pd.Timedelta(hours=a["lookback_hours"])]
        ship = status.set_index("container_id")["shipment_id"]
        for cont, g in recent.dropna(subset=["container_id"]).groupby("container_id"):
            n_crit = int((g["severity"] == "CRITICAL").sum())
            sev = "CRITICAL" if n_crit >= a["critical_count"] else "WARNING" if len(g) >= a["warning_count"] else None
            if sev:
                top = g.sort_values("severity", ascending=False).iloc[0]
                add(cont, ship.get(cont), "anomaly", sev, f"{len(g)} sensor anomalies in the last {a['lookback_hours']} h ({n_crit} critical)", f"Example: {top['reason']}")
    if forecast is None:
        from analytics.forecast import forecast_risk
        forecast = forecast_risk(r["readings"], status, cfg)
    f = c["forecast"]
    fx = forecast[(forecast["scenario"] == f["scenario"]) & (forecast["horizon_h"] == 0)]
    for _, x in fx.iterrows():                                                        # Feature 3 (heuristic)
        t = x["hours_until_threshold"]
        if pd.notna(t) and t > 0:
            sev = "CRITICAL" if t <= f["critical_within_hours"] else "WARNING" if t <= f["warning_within_hours"] else None
            if sev:
                add(x["container_id"], x["shipment_id"], "forecast", sev, f"Quality threshold expected in ~{t:.0f} h (heuristic)",
                    f"Under the '{f['scenario']}' scenario remaining shelf life falls to the required retail minimum in about {t:.0f} h. HEURISTIC estimate, not validated.")
    if c["arbitrage"]["enabled"]:
        for _, x in r["recs"][r["recs"]["recommended_action"] == "REROUTE"].iterrows():   # Phase 1 arbitrage
            add(x["container_id"], x["shipment_id"], "arbitrage", "WARNING", f"Reroute opportunity {x['original_destination']} -> {x['best_alternative']}",
                f"Estimated quality-adjusted benefit ${x['best_benefit_usd']:,.0f} (heuristic; simulated prices).")
    out = pd.DataFrame(rows, columns=CANDIDATE_COLS)
    if extra is not None and not extra.empty:                                         # e.g. data-quality alerts (Batch 07)
        out = pd.concat([out, extra.reindex(columns=CANDIDATE_COLS)], ignore_index=True)
    return out


# --------------------------------------------------------------------------- lifecycle
def _event(alert_id, action, actor, note, severity, ts):
    return dict(event_id=f"{alert_id}-{int(pd.Timestamp(ts).timestamp() * 1e6)}-{action}", alert_id=alert_id, event_ts=ts, action=action,
                actor=actor, note=note, severity=severity)


def sync_alerts(candidates: pd.DataFrame, store: Store | None = None, now: pd.Timestamp | None = None, actor: str = "system") -> dict:
    """Create / update / escalate / reopen alerts from candidates and mark alerts whose condition disappeared."""
    store = store or Store()
    now = pd.Timestamp(now) if now is not None else pd.Timestamp.now("UTC").tz_localize(None)
    existing = store.read_table("alerts")
    ex = existing.set_index("alert_id") if not existing.empty else pd.DataFrame()
    stats = dict(created=0, updated=0, escalated=0, reopened=0, cleared=0)
    new_rows, events, seen = [], [], set()
    for _, c in candidates.iterrows():
        aid = alert_id_for(c["container_id"], c["category"]); seen.add(aid)
        if aid not in ex.index:
            new_rows.append(dict(alert_id=aid, created_at=now, last_seen_at=now, event_time=c["event_time"], container_id=c["container_id"], shipment_id=c["shipment_id"],
                                 category=c["category"], severity=c["severity"], title=c["title"], message=c["message"], status="OPEN",
                                 acknowledged_at=pd.NaT, acknowledged_by=None, resolved_at=pd.NaT, resolved_by=None, resolution_note=None, occurrences=1, condition_active=True))
            events.append(_event(aid, "CREATED", actor, c["title"], c["severity"], now)); stats["created"] += 1
            continue
        old = ex.loc[aid]; upd = dict(last_seen_at=now, event_time=c["event_time"], title=c["title"], message=c["message"], condition_active=True, occurrences=int(old["occurrences"]) + 1)
        if old["status"] == "RESOLVED":
            upd.update(status="OPEN", severity=c["severity"], acknowledged_at=pd.NaT, acknowledged_by=None, resolved_at=pd.NaT, resolved_by=None, resolution_note=None)
            events.append(_event(aid, "REOPENED", actor, "condition detected again", c["severity"], now)); stats["reopened"] += 1
        elif _RANK[c["severity"]] > _RANK[old["severity"]]:
            upd.update(severity=c["severity"], status="OPEN", acknowledged_at=pd.NaT, acknowledged_by=None)
            events.append(_event(aid, "ESCALATED", actor, f"{old['severity']} -> {c['severity']}", c["severity"], now)); stats["escalated"] += 1
        else:
            stats["updated"] += 1
        new_rows.append({**old.to_dict(), "alert_id": aid, **upd})
    if not ex.empty:
        for aid, old in ex.iterrows():
            if aid not in seen and old["status"] != "RESOLVED" and bool(old["condition_active"]):
                new_rows.append({**old.to_dict(), "alert_id": aid, "condition_active": False})
                events.append(_event(aid, "CONDITION_CLEARED", actor, "no longer detected (still needs resolution)", old["severity"], now)); stats["cleared"] += 1
    if new_rows:
        store.upsert_df("alerts", pd.DataFrame(new_rows), ["alert_id"])
    if events:
        store.append_df("alert_events", pd.DataFrame(events))
    return stats


def _transition(alert_id: str, store: Store, new_status: str, actor: str, note: str, now) -> None:
    now = pd.Timestamp(now) if now is not None else pd.Timestamp.now("UTC").tz_localize(None)
    df = store.read_table("alerts")
    row = df[df["alert_id"] == alert_id] if not df.empty else df
    if row.empty:
        raise KeyError(f"unknown alert {alert_id}")
    cur = row.iloc[0]
    allowed = {"ACKNOWLEDGED": ["OPEN"], "RESOLVED": ["OPEN", "ACKNOWLEDGED"]}[new_status]
    if cur["status"] not in allowed:
        raise ValueError(f"cannot move alert {alert_id} from {cur['status']} to {new_status}")
    upd = row.copy(); upd["status"] = new_status
    if new_status == "ACKNOWLEDGED":
        upd["acknowledged_at"], upd["acknowledged_by"] = now, actor
    else:
        upd["resolved_at"], upd["resolved_by"], upd["resolution_note"] = now, actor, note
    store.upsert_df("alerts", upd, ["alert_id"])
    store.append_df("alert_events", pd.DataFrame([_event(alert_id, new_status, actor, note, cur["severity"], now)]))


def acknowledge(alert_id: str, store: Store | None = None, actor: str = "operator", note: str = "", now=None) -> None:
    _transition(alert_id, store or Store(), "ACKNOWLEDGED", actor, note, now)


def resolve(alert_id: str, store: Store | None = None, actor: str = "operator", note: str = "", now=None) -> None:
    _transition(alert_id, store or Store(), "RESOLVED", actor, note, now)


# --------------------------------------------------------------------------- queries
def query_alerts(store: Store | None = None, containers=None, shipments=None, severities=None, statuses=None, categories=None,
                 date_from=None, date_to=None) -> pd.DataFrame:
    """Filter stored alerts (by container, shipment, severity, status, category and event-time range). Newest/most severe first."""
    df = (store or Store()).read_table("alerts")
    if df.empty:
        return df
    for col, vals in (("container_id", containers), ("shipment_id", shipments), ("severity", severities), ("status", statuses), ("category", categories)):
        if vals:
            df = df[df[col].isin(vals)]
    if date_from is not None:
        df = df[df["event_time"] >= pd.Timestamp(date_from)]
    if date_to is not None:
        df = df[df["event_time"] <= pd.Timestamp(date_to)]
    df = df.assign(_r=df["severity"].map(_RANK)).sort_values(["_r", "event_time"], ascending=[False, False]).drop(columns="_r")
    return df.reset_index(drop=True)


def alert_history(store: Store | None = None, alert_id: str | None = None) -> pd.DataFrame:
    ev = (store or Store()).read_table("alert_events")
    if ev.empty:
        return ev
    if alert_id:
        ev = ev[ev["alert_id"] == alert_id]
    return ev.sort_values("event_ts").reset_index(drop=True)


def alert_counts(store: Store | None = None) -> dict:
    df = (store or Store()).read_table("alerts")
    g = lambda **kw: int(len(df[(df[list(kw)] == pd.Series(kw)).all(axis=1)])) if not df.empty else 0
    return dict(open_critical=g(status="OPEN", severity="CRITICAL"), open_warning=g(status="OPEN", severity="WARNING"),
                acknowledged=int((df["status"] == "ACKNOWLEDGED").sum()) if not df.empty else 0,
                resolved=int((df["status"] == "RESOLVED").sum()) if not df.empty else 0, total=len(df))


if __name__ == "__main__":
    import argparse
    from analytics.pipeline import run_pipeline
    from common.config import load_settings
    ap = argparse.ArgumentParser(); ap.add_argument("--sync", action="store_true"); ap.add_argument("--list", action="store_true"); a = ap.parse_args()
    cfg = load_settings()
    if a.sync:
        print(sync_alerts(collect_candidates(run_pipeline(cfg), cfg)))
    if a.list or not a.sync:
        print(query_alerts()[["alert_id", "container_id", "category", "severity", "status", "title"]].to_string(index=False))
