"""Data quality monitoring (Feature 7).

Re-uses the Phase 1 cleaning rules (`ingestion.cleaning.clean_sensor_events`) so quality numbers always agree with what the
pipeline actually rejects.  Scores (0-100):
  completeness = mean( field completeness [non-null share of required fields],  reading coverage [received / expected readings] )
  validity     = share of raw rows that pass the cleaning checks (not null / sentinel / out of range / bad timestamp)
  uniqueness   = 1 - duplicate rows / rows
  timeliness   = share of containers whose last reading is not stale
  overall      = weighted mean (weights in config/features/quality.yaml)
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd
from common.config import abs_path
from common.store import Store
from ingestion.cleaning import clean_sensor_events, SENTINELS

NUMERIC = ["temperature_c", "humidity_pct", "vibration_g"]
TABLE = "dq_reports"


@dataclass
class QualityReport:
    summary: dict
    by_container: pd.DataFrame
    by_field: pd.DataFrame
    issues: pd.DataFrame

    def _bc(self) -> pd.DataFrame:
        return self.by_container.round({c: 1 for c in self.by_container.select_dtypes("number").columns})

    def to_markdown(self) -> str:
        s = self.summary
        lines = ["# Data Quality Report", "", f"*Generated for data ending {s['data_end']} - rows analysed: {s['rows']}*", "",
                 f"**Overall score: {s['overall_score']:.1f}/100 ({s['status']})**", "",
                 "| Metric | Score |", "|---|---|"]
        lines += [f"| {k.capitalize()} | {s[k + '_score']:.1f} |" for k in ("completeness", "validity", "uniqueness", "timeliness")]
        lines += ["", "## Issue counts", "", f"- Missing values: {s['missing_values']}", f"- Invalid readings (sentinel / non-numeric / bad timestamp): {s['invalid_readings']}",
                  f"- Out-of-range values: {s['out_of_range']}", f"- Duplicate records: {s['duplicates']}", f"- Rows rejected by cleaning: {s['rejected_rows']}",
                  f"- Missing expected readings (gaps): {s['missing_readings']}", f"- Stale containers: {s['stale_containers']}", "", "## By field", "",
                  self.by_field.round(3).to_markdown(index=False) if _has_tabulate() else self.by_field.round(3).to_string(index=False), "", "## By container", "",
                  self._bc().to_markdown(index=False) if _has_tabulate() else self._bc().to_string(index=False), "",
                  "## Findings", ""] + [f"- **{r.severity}** {r.scope}: {r.finding}" for r in self.issues.itertuples()]
        return "\n".join(lines) + "\n"

    def save(self, out_dir: str | Path | None = None, cfg: dict | None = None) -> list[Path]:
        out = Path(out_dir) if out_dir else abs_path(cfg["data_quality"]["report_dir"]); out.mkdir(parents=True, exist_ok=True)
        paths = [out / "data_quality_report.md"]
        paths[0].write_text(self.to_markdown(), encoding="utf-8")
        for name, df in (("quality_by_container.csv", self.by_container), ("quality_by_field.csv", self.by_field), ("quality_issues.csv", self.issues)):
            df.to_csv(out / name, index=False); paths.append(out / name)
        return paths


def _has_tabulate() -> bool:
    try:
        import tabulate  # noqa: F401
        return True
    except ImportError:
        return False


def _status(score: float, cfg: dict) -> str:
    q = cfg["data_quality"]
    return "CRITICAL" if score < q["critical_below"] else "WARNING" if score < q["warning_below"] else "GOOD"


def assess_quality(raw: pd.DataFrame, cfg: dict) -> QualityReport:
    q, th = cfg["data_quality"], cfg["thresholds"]
    interval = q["expected_interval_minutes"] or cfg["simulator"]["interval_minutes"]
    df = raw.copy()
    n = len(df)
    ts = pd.to_datetime(df.get("reading_ts"), utc=True, errors="coerce").dt.tz_localize(None)
    df["_ts"] = ts
    absent = [c for c in q["required_fields"] if c not in df.columns]
    for c in absent:
        df[c] = np.nan
    plaus = {"temperature_c": th["valid_temp_range_c"], "humidity_pct": th["valid_rh_range_pct"], "vibration_g": th["valid_vibration_range_g"]}

    # ---- per-field issue counts
    frows = []
    for c in q["required_fields"]:
        missing = int(df[c].isna().sum()); invalid = out_rng = 0
        if c in NUMERIC:
            num = pd.to_numeric(df[c], errors="coerce")
            invalid = int((df[c].notna() & num.isna()).sum() + num.isin(SENTINELS).sum())
            out_rng = int((num.notna() & ~num.isin(SENTINELS) & ~num.between(*plaus[c])).sum())
        elif c == "reading_ts":
            invalid = int((df[c].notna() & df["_ts"].isna()).sum())
        frows.append(dict(field=c, missing=missing, invalid=invalid, out_of_range=out_rng,
                          completeness_pct=100 * (1 - missing / n) if n else 100.0, validity_pct=100 * (1 - (invalid + out_rng) / n) if n else 100.0))
    by_field = pd.DataFrame(frows)

    # ---- validity via the pipeline's own cleaning rules
    clean, rejected, cstats = clean_sensor_events(df.drop(columns="_ts"), cfg)
    dups = int(df.duplicated(["container_id", "sensor_id", "_ts"], keep="first").sum())
    field_complete = 100 * (1 - by_field["missing"].sum() / max(n * len(q["required_fields"]), 1))

    # ---- per container
    crows = []
    newest = df["_ts"].max()
    for cid, g in df.dropna(subset=["container_id"]).groupby("container_id"):
        g_ts = g["_ts"].dropna()
        uniq = g_ts.drop_duplicates()
        expected = int((g_ts.max() - g_ts.min()).total_seconds() // (interval * 60)) + 1 if len(g_ts) else 0
        cov = min(100 * len(uniq) / expected, 100.0) if expected else 100.0
        rej = int(rejected["container_id"].eq(cid).sum()) if len(rejected) else 0
        d = int(g.duplicated(["container_id", "sensor_id", "_ts"], keep="first").sum())
        stale = bool(len(g_ts) and (newest - g_ts.max()).total_seconds() / 60 > q["stale_minutes"])
        miss_fields = 100 * (1 - g[q["required_fields"]].isna().sum().sum() / max(len(g) * len(q["required_fields"]), 1))
        comp = (miss_fields + cov) / 2; val = 100 * (1 - rej / len(g)); uni = 100 * (1 - d / len(g))
        w = q["weights"]
        score = w["completeness"] * comp + w["validity"] * val + w["uniqueness"] * uni + w["timeliness"] * (0 if stale else 100)
        score /= sum(w.values())
        crows.append(dict(container_id=cid, rows=len(g), expected_readings=expected, unique_readings=len(uniq), coverage_pct=cov, rejected_rows=rej,
                          duplicates=d, completeness=comp, validity=val, uniqueness=uni, stale=stale, last_reading_ts=g_ts.max(), score=score))
    by_container = pd.DataFrame(crows).sort_values("score").reset_index(drop=True)

    expected_total = int(by_container["expected_readings"].sum()); got = int(by_container["unique_readings"].sum())
    cov_all = min(100 * got / expected_total, 100.0) if expected_total else 100.0
    completeness = (field_complete + cov_all) / 2
    validity = 100 * (1 - len(rejected) / n) if n else 100.0
    uniqueness = 100 * (1 - dups / n) if n else 100.0
    timeliness = 100 * (1 - by_container["stale"].mean()) if len(by_container) else 100.0
    w = q["weights"]
    overall = (w["completeness"] * completeness + w["validity"] * validity + w["uniqueness"] * uniqueness + w["timeliness"] * timeliness) / sum(w.values())
    summary = dict(rows=n, data_end=str(newest), completeness_score=completeness, validity_score=validity, uniqueness_score=uniqueness,
                   timeliness_score=timeliness, overall_score=overall, status=_status(overall, cfg), missing_values=int(by_field["missing"].sum()),
                   invalid_readings=int(by_field["invalid"].sum()), out_of_range=int(by_field["out_of_range"].sum()), duplicates=dups,
                   rejected_rows=len(rejected), missing_readings=max(expected_total - got, 0), stale_containers=int(by_container["stale"].sum()),
                   cleaning_stats=cstats)

    # ---- findings
    issues = []
    add = lambda sev, scope, txt: issues.append(dict(severity=sev, scope=scope, finding=txt))
    for c in absent: add("CRITICAL", c, "required column is absent from the data.")
    if summary["duplicates"]: add("INFO", "all", f"{dups} duplicate records ({100 * dups / n:.1f}%) - removed by cleaning.")
    if summary["rejected_rows"]: add("WARNING" if validity >= q["critical_below"] else "CRITICAL", "all", f"{len(rejected)} rows fail validation ({100 - validity:.1f}%).")
    for r in by_field.itertuples():
        if r.missing: add("WARNING", r.field, f"{r.missing} missing values.")
        if r.invalid: add("WARNING", r.field, f"{r.invalid} invalid readings (sentinel / non-numeric).")
        if r.out_of_range: add("WARNING", r.field, f"{r.out_of_range} values outside the plausible range {plaus.get(r.field, '')}.")
    for r in by_container.itertuples():
        if r.coverage_pct < 90: add("WARNING", r.container_id, f"reading coverage {r.coverage_pct:.0f}% ({r.expected_readings - r.unique_readings} expected readings missing).")
        if r.stale: add("WARNING", r.container_id, f"stale: last reading {r.last_reading_ts}.")
    return QualityReport(summary, by_container, by_field, pd.DataFrame(issues, columns=["severity", "scope", "finding"]))


def quality_alert_candidates(report: QualityReport, cfg: dict) -> pd.DataFrame:
    """Alert-centre candidates (Batch 06 format): one system-level alert and one per low-scoring container."""
    q, s = cfg["data_quality"], report.summary
    rows = []
    ev = pd.Timestamp(s["data_end"]) if s["data_end"] != "NaT" else pd.Timestamp.now("UTC").tz_localize(None)
    if s["status"] != "GOOD":
        rows.append(dict(container_id="SYSTEM", shipment_id=None, category="data_quality", severity=s["status"],
                         title=f"Data quality {s['status'].lower()} ({s['overall_score']:.0f}/100)",
                         message=f"completeness {s['completeness_score']:.0f}, validity {s['validity_score']:.0f}, uniqueness {s['uniqueness_score']:.0f}, timeliness {s['timeliness_score']:.0f}.", event_time=ev))
    for r in report.by_container.itertuples():
        st = _status(r.score, cfg)
        if st != "GOOD":
            rows.append(dict(container_id=r.container_id, shipment_id=None, category="data_quality", severity=st, title=f"Data quality {st.lower()} for {r.container_id} ({r.score:.0f}/100)",
                             message=f"coverage {r.coverage_pct:.0f}%, rejected rows {r.rejected_rows}, duplicates {r.duplicates}.", event_time=ev))
    return pd.DataFrame(rows, columns=["container_id", "shipment_id", "category", "severity", "title", "message", "event_time"])


def save_quality_summary(report: QualityReport, store: Store | None = None, run_ts=None) -> int:
    s = {k: v for k, v in report.summary.items() if k not in ("cleaning_stats",)}
    s["run_ts"] = pd.Timestamp(run_ts) if run_ts is not None else pd.Timestamp.now("UTC").tz_localize(None)
    return (store or Store()).upsert_df(TABLE, pd.DataFrame([s]), ["run_ts"])


if __name__ == "__main__":
    import argparse
    from common.config import load_settings
    ap = argparse.ArgumentParser(); ap.add_argument("--source", default=None); ap.add_argument("--save", action="store_true"); a = ap.parse_args()
    cfg = load_settings(); raw = pd.read_csv(a.source or abs_path(cfg["paths"]["sample_dir"]) / "raw_sensor_events.csv")
    rep = assess_quality(raw, cfg); print(rep.to_markdown())
    if a.save:
        print(rep.save(cfg=cfg)); print("history rows:", save_quality_summary(rep))
