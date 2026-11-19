"""Executive analytics and reporting (Feature 9): KPIs, summary tables, CSV bundle, PDF report.

Every table carries a `report_label`; every export states which values are SIMULATED and which are HEURISTIC estimates.
No new calculations are introduced here: the report assembles Phase 1 and Batch 01-07 results.
"""
from __future__ import annotations
import io, zipfile
from dataclasses import dataclass
from pathlib import Path
import pandas as pd
from common.config import abs_path

HEURISTIC_NOTE = ("Risk scores, health scores, forecasts and arbitrage values are HEURISTIC ESTIMATES produced by transparent project models; "
                  "they are not scientifically validated spoilage predictions.")


@dataclass
class ReportData:
    title: str
    as_of: str
    kpis: pd.DataFrame            # columns: kpi, value, note
    tables: dict                  # name -> DataFrame (each has report_label)
    labels: list                  # disclaimer lines


def _data_labels(r: dict, price_type: str) -> list:
    src = sorted(r["raw"]["source"].astype(str).unique()) if "source" in r["raw"].columns else ["UNKNOWN"]
    lines = [f"Sensor data source: {', '.join(src)}.", f"Market price dataset type: {price_type}.", HEURISTIC_NOTE]
    if any("SIMULATED" in s for s in src) or price_type == "SIMULATED":
        lines.insert(0, "SIMULATED DATA: values in this report come from simulated sample data and are for demonstration only.")
    return lines


def build_report(r: dict, cfg: dict, price_dataset: str = "sample_simulated") -> ReportData:
    from analytics.anomaly import detect_anomalies
    from analytics.forecast import forecast_risk
    from analytics.health import health_timeline, current_health, health_summary
    from analytics.market import load_price_datasets, latest_comparison, arbitrage_margins
    from analytics.routes import compare_routes, recommend_routes, load_profiles
    rp = cfg["reporting"]; status = r["status"]
    health = current_health(health_timeline(r["readings"], cfg)); hs = health_summary(health)
    anomalies = detect_anomalies(r["raw"], cfg)
    fc = forecast_risk(r["readings"], status, cfg)
    fx = fc[(fc["scenario"] == rp["forecast_scenario"]) & (fc["horizon_h"] == 0)]
    soon = int(((fx["hours_until_threshold"] > 0) & (fx["hours_until_threshold"] <= rp["forecast_window_hours"])).sum())
    ds = load_price_datasets(cfg)[price_dataset]; ptype = ds["dataset_type"].iloc[0]
    lc = latest_comparison(ds); margins = arbitrage_margins(ds, r["locations"], cfg)
    routes = recommend_routes(compare_routes(status, r["locations"], load_profiles(cfg), ds, cfg), cfg)
    k = r["kpis"].iloc[0]; q = r["quality"].summary
    kpis = pd.DataFrame([
        ("Total containers", int(k["total_containers"]), "Phase 1"),
        ("Healthy (risk LOW)", int(k["healthy_containers"]), "Phase 1 risk category"),
        ("At risk (risk MEDIUM/HIGH/CRITICAL)", int(k["at_risk_containers"]), "Phase 1 risk category"),
        ("Critical containers", int(k["critical_alerts"]), "Phase 1 risk category"),
        ("Average shipment health score", hs["average_score"], "0-100, heuristic"),
        ("Shipments Critical / At Risk by health", f"{hs['Critical']} / {hs['At Risk']}", "health classes"),
        ("Sensor anomalies (critical)", f"{len(anomalies)} ({int((anomalies['severity'] == 'CRITICAL').sum())})", "anomaly detection"),
        (f"Containers expected below quality threshold within {rp['forecast_window_hours']} h", soon, "HEURISTIC forecast"),
        ("Reroute opportunities (Phase 1 arbitrage)", int(k["arbitrage_opportunities"]), "heuristic, simulated prices"),
        ("Estimated reroute benefit (USD)", round(float(k["estimated_benefit_usd"]), 0), "heuristic, simulated prices"),
        ("Best market price margin (net USD/kg)", round(float(margins.iloc[0]["net_margin_usd_kg"]), 3) if len(margins) else float("nan"), f"{ptype} prices"),
        ("Data quality score", round(q["overall_score"], 1), f"status {q['status']}"),
    ], columns=["kpi", "value", "note"])
    lab = lambda df, text: df.assign(report_label=text)
    risk_cols = ["container_id", "shipment_id", "risk_score", "risk_category", "quality_window_hours", "hours_to_destination", "slack_hours"]
    atrisk = status[status["risk_category"].isin(["MEDIUM", "HIGH", "CRITICAL"])][risk_cols].sort_values("risk_score", ascending=False)
    tables = {
        "shipment_health_summary": lab(health[["container_id", "shipment_id", "health_score", "category", "main_driver"]], "HEURISTIC health score; SIMULATED data"),
        "at_risk_containers": lab(atrisk, "HEURISTIC risk; SIMULATED data"),
        "critical_containers": lab(atrisk[atrisk["risk_category"] == "CRITICAL"], "HEURISTIC risk; SIMULATED data"),
        "market_price_comparison": lab(lc[["rank", "market_id", "price_date", "price_modal_usd_kg", "premium_vs_avg_usd_kg"]], f"{ptype} prices"),
        "market_margins_top": lab(margins.head(10)[["buy_market", "sell_market", "distance_km", "gross_margin_usd_kg", "net_margin_usd_kg", "net_margin_usd"]], f"{ptype} prices; assumed costs"),
        "reroute_opportunities": lab(r["recs"][r["recs"]["recommended_action"] == "REROUTE"][["container_id", "original_destination", "best_alternative", "best_benefit_usd"]], "HEURISTIC estimate; SIMULATED prices"),
        "route_recommendations": lab(routes[routes["recommendation"] != "KEEP CURRENT ROUTE"][["container_id", "recommended_market", "recommended_profile", "benefit_usd", "arrival_life_hours"]], "SAMPLE route profiles; HEURISTIC"),
    }
    kpis["report_label"] = "HEURISTIC / SIMULATED (see notes)"
    return ReportData(rp["title"], str(status["as_of_ts"].max()), kpis, tables, _data_labels(r, ptype))


# ------------------------------------------------------------------------------------------- CSV
def csv_files(rep: ReportData) -> dict[str, str]:
    files = {"kpis.csv": rep.kpis.to_csv(index=False)}
    files.update({f"{k}.csv": v.to_csv(index=False) for k, v in rep.tables.items()})
    files["README_LABELS.txt"] = f"{rep.title} - data as of {rep.as_of}\n\n" + "\n".join(rep.labels) + "\n"
    return files


def export_csv_bundle(rep: ReportData, out_dir: str | Path) -> list[Path]:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, text in csv_files(rep).items():
        p = out / name; p.write_text(text, encoding="utf-8"); paths.append(p)
    return paths


def csv_bundle_zip(rep: ReportData) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in csv_files(rep).items():
            z.writestr(name, text)
    return buf.getvalue()


# ------------------------------------------------------------------------------------------- PDF
def _fmt(v) -> str:
    if isinstance(v, float):
        return "" if pd.isna(v) else f"{v:,.2f}"
    return "" if v is None or (isinstance(v, pd._libs.missing.NAType)) else str(v)


def build_pdf_bytes(rep: ReportData, cfg: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    rp = cfg["reporting"]; buf = io.BytesIO(); styles = getSampleStyleSheet()
    footer = "SIMULATED sample data - heuristic estimates, not validated predictions"

    def on_page(canvas, doc):
        canvas.saveState(); canvas.setFont("Helvetica", 7); canvas.setFillColor(colors.grey)
        canvas.drawString(1.5 * cm, 0.8 * cm, f"{rep.title} | {footer}"); canvas.drawRightString(landscape(A4)[0] - 1.5 * cm, 0.8 * cm, f"Page {doc.page}")
        canvas.restoreState()

    def tbl(df, cols=None, max_rows=None):
        d = df[cols] if cols else df.drop(columns=["report_label"], errors="ignore")
        d = d.head(max_rows or rp["top_n_rows"])
        data = [list(d.columns)] + [[_fmt(v) for v in row] for row in d.itertuples(index=False)]
        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 7),
                               ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f6fa")])]))
        return t

    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                            title=rep.title, pageCompression=1 if rp["pdf_compression"] else 0)
    s = [Paragraph(rep.title, styles["Title"]), Paragraph(f"Data as of {rep.as_of}", styles["Normal"]), Spacer(1, 6)]
    warn = "<br/>".join(rep.labels)
    s.append(Paragraph(f"<b>Data labels and limitations</b><br/>{warn}", styles["Normal"])); s.append(Spacer(1, 10))
    s += [Paragraph("Key performance indicators", styles["Heading2"]), tbl(rep.kpis, ["kpi", "value", "note"], 30), Spacer(1, 10)]
    titles = {"shipment_health_summary": "Shipment health summary", "at_risk_containers": "At-risk containers", "critical_containers": "Critical containers",
              "market_price_comparison": "Market price comparison (latest day)", "market_margins_top": "Top market-to-market margins",
              "reroute_opportunities": "Potential rerouting opportunities (spoilage arbitrage)", "route_recommendations": "Route change recommendations"}
    for key, title in titles.items():
        df = rep.tables[key]
        s.append(Paragraph(f"{title} <font size=8 color='grey'>[{df['report_label'].iloc[0] if len(df) else 'n/a'}]</font>", styles["Heading2"]))
        s.append(tbl(df) if len(df) else Paragraph("None.", styles["Normal"])); s.append(Spacer(1, 8))
    doc.build(s, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()


def export_pdf(rep: ReportData, cfg: dict, path: str | Path) -> Path:
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(build_pdf_bytes(rep, cfg)); return p


if __name__ == "__main__":
    import argparse
    from analytics.pipeline import run_pipeline
    from common.config import load_settings
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=None); a = ap.parse_args()
    cfg = load_settings(); out = Path(a.out) if a.out else abs_path(cfg["reporting"]["export_dir"])
    rep = build_report(run_pipeline(cfg), cfg)
    print([p.name for p in export_csv_bundle(rep, out)]); print(export_pdf(rep, cfg, out / "executive_report.pdf"))
