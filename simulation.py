"""Simulation Lab page (Feature 8): scenario builder, historical replay, container comparison. All data SIMULATED."""
import pandas as pd
import streamlit as st
from common.config import abs_path
from simulator.lab import resolve_params, compare_scenarios, replay_status_at, replay_timeline, compare_containers

TITLE, ORDER = "Simulation Lab", 100


@st.cache_data(show_spinner="Simulating...")
def _compare(_loc, _key, preset_n, preset_a, overrides):
    from common.config import load_settings
    cfg = load_settings()
    return compare_scenarios(resolve_params(preset_n, cfg, **overrides[0]), resolve_params(preset_a, cfg, **overrides[1]), _loc, cfg)


@st.cache_data(show_spinner="Replaying...")
def _timeline(_readings, _ship, _loc, _key):
    from common.config import load_settings
    return replay_timeline(_readings, _ship, _loc, load_settings(), 2.0)


def render(ctx):
    r, cfg = ctx["r"], ctx["cfg"]; lab = cfg["simulation_lab"]
    st.caption("Everything on this page is SIMULATED. Presets live in config/features/simulation.yaml; fault shapes are illustrative.")
    t1, t2, t3 = st.tabs(["Scenario builder", "Historical replay", "Compare containers"])
    with t1:
        locs = sorted(r["locations"]["location_id"]); presets = list(lab["presets"])
        c1, c2, c3 = st.columns(3)
        origin = c1.selectbox("Origin", [x for x in locs if lab["defaults"]["origin_id"] == x or x in ("PHARR_TX", "OTAY_MESA_CA")], key="sim_o")
        dest = c2.selectbox("Destination", [x for x in locs if x not in ("PHARR_TX", "OTAY_MESA_CA")], index=[x for x in locs if x not in ("PHARR_TX", "OTAY_MESA_CA")].index("CHICAGO"), key="sim_d")
        abn = c3.selectbox("Abnormal scenario", [p for p in presets if p != "normal"], index=2, key="sim_a")
        st.write(f"**{abn}** - {lab['presets'][abn]['description']}")
        c4, c5, c6 = st.columns(3)
        prog = c4.slider("Route progress", 0.2, 0.9, float(lab["defaults"]["progress"]), 0.05, key="sim_p")
        pre = c5.slider("Shelf life already used at loading", 0.0, 0.9, float(lab["defaults"]["pre_loading_consumed"]), 0.05, key="sim_pre")
        seed = c6.number_input("Random seed", 0, 9999, int(lab["defaults"]["seed"]), key="sim_seed")
        common = dict(origin_id=origin, destination_id=dest, progress=prog, pre_loading_consumed=pre, seed=int(seed))
        ov_a = dict(common)
        p = lab["presets"][abn]
        if p.get("spikes"):
            sp = p["spikes"][0]
            mag = st.slider("Spike magnitude (°C)", 1.0, 20.0, float(sp["magnitude_c"]), key="sim_mag"); dur = st.slider("Spike duration (h)", 0.25, 6.0, float(sp["duration_h"]), key="sim_dur")
            ov_a["spikes"] = [{**sp, "magnitude_c": mag, "duration_h": dur}]
        if p.get("drift"):
            dr = p["drift"]; rate = st.slider("Drift rate (°C/h)", 0.1, 2.0, float(dr["rate_c_per_h"]), key="sim_rate"); ov_a["drift"] = {**dr, "rate_c_per_h": rate}
        if p.get("vibration_bursts"):
            vb = p["vibration_bursts"][0]; mult = st.slider("Vibration multiplier", 1.5, 8.0, float(vb["multiplier"]), key="sim_vm"); ov_a["vibration_bursts"] = [{**vb, "multiplier": mult}]
        if p["humidity"]["fluctuation_amp_pct"] or p["humidity"]["drop_rate_pct_per_h"]:
            h = p["humidity"]; amp = st.slider("Humidity swing amplitude (%)", 0.0, 20.0, float(h["fluctuation_amp_pct"]), key="sim_amp")
            drop = st.slider("Humidity loss (%/h)", 0.0, 3.0, float(h["drop_rate_pct_per_h"]), key="sim_drop"); ov_a["humidity"] = {**h, "fluctuation_amp_pct": amp, "drop_rate_pct_per_h": drop}
        res = _compare(r["locations"], str(cfg["simulation_lab"]) + str(cfg["quality_model"]), "normal", abn, (common, ov_a))
        n, a = res["normal"]["readings"], res["abnormal"]["readings"]
        for col, lab_ in [("temperature_c", "Temperature (°C)"), ("humidity_pct", "Humidity (%)"), ("vibration_g", "Vibration (g)")]:
            st.subheader(lab_)
            st.line_chart(pd.DataFrame({"normal": n.set_index("reading_ts")[col], "abnormal": a.set_index("reading_ts")[col]}))
        st.subheader("Normal vs abnormal"); st.dataframe(res["table"].round(3), use_container_width=True)
        st.dataframe(res["abnormal"]["anomalies"][["reading_ts", "metric", "anomaly_type", "severity", "reason"]].head(50), use_container_width=True)
    with t2:
        ship = pd.read_csv(abs_path(cfg["paths"]["sample_dir"]) / "shipments.csv")
        rd = r["readings"]; lo, hi = rd["reading_ts"].min().to_pydatetime(), rd["reading_ts"].max().to_pydatetime()
        t = st.slider("Replay position (what did the system know at this time?)", lo, hi, hi, key="rp_t")
        st_at = replay_status_at(rd, ship, r["locations"], cfg, t)
        if st_at.empty:
            st.info("No readings before this time.")
        else:
            st.dataframe(st_at[["container_id", "risk_score", "risk_category", "slack_hours", "quality_window_hours", "life_consumed_fraction"]].round(2), use_container_width=True)
        tl = _timeline(rd, ship, r["locations"], "tl")
        ids = st.multiselect("Containers", sorted(tl["container_id"].unique()), default=["CNT-009", "CNT-007"], key="rp_ids")
        if ids:
            st.subheader("Risk score over replay time"); st.line_chart(tl[tl["container_id"].isin(ids)].pivot_table(index="replay_ts", columns="container_id", values="risk_score"))
        st.caption("For live-style streaming of the same data use `python -m streaming.producer --speedup 600` (needs Kafka) or ingestion/replay.py with a speedup factor.")
    with t3:
        rd = r["readings"]; ids = sorted(rd["container_id"].unique())
        a, b = st.columns(2); ca = a.selectbox("Container A", ids, index=0, key="cc_a"); cb = b.selectbox("Container B", ids, index=ids.index("CNT-009") if "CNT-009" in ids else 1, key="cc_b")
        st.dataframe(compare_containers(rd, r["status"], ca, cb).round(3), use_container_width=True)
        d = rd[rd["container_id"].isin([ca, cb])]
        st.line_chart(d.pivot_table(index="reading_ts", columns="container_id", values="temperature_c"))
