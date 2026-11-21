import io, zipfile
import pandas as pd
import pytest
from analytics import reporting as R


@pytest.fixture(scope="module")
def rep(cfg, results):
    return R.build_report(results, cfg)


def test_kpis_match_phase1_and_modules(rep, results):
    k = rep.kpis.set_index("kpi")["value"]; p1 = results["kpis"].iloc[0]
    assert k["Total containers"] == 12 == p1["total_containers"] and k["Critical containers"] == p1["critical_alerts"]
    assert k["Reroute opportunities (Phase 1 arbitrage)"] == p1["arbitrage_opportunities"]
    assert k["Estimated reroute benefit (USD)"] == pytest.approx(round(p1["estimated_benefit_usd"]))
    assert k["Data quality score"] == pytest.approx(round(results["quality"].summary["overall_score"], 1))
    assert k["Containers expected below quality threshold within 24 h"] == 3
    assert k["Sensor anomalies (critical)"] == "138 (46)"


def test_every_table_and_kpi_is_labelled(rep):
    assert all("report_label" in t.columns for t in rep.tables.values()) and rep.kpis["report_label"].str.contains("HEURISTIC").all()
    assert rep.labels[0].startswith("SIMULATED DATA") and any("HEURISTIC ESTIMATES" in l for l in rep.labels)
    assert rep.tables["market_price_comparison"]["report_label"].str.contains("SIMULATED").all()


def test_table_contents(rep):
    assert list(rep.tables["critical_containers"]["container_id"]) == ["CNT-009"]
    assert set(rep.tables["at_risk_containers"]["container_id"]) == {"CNT-009", "CNT-007", "CNT-008"}
    assert list(rep.tables["reroute_opportunities"]["best_alternative"]) == ["DENVER"]
    assert len(rep.tables["shipment_health_summary"]) == 12 and len(rep.tables["market_price_comparison"]) == 9


def test_csv_bundle_files_and_zip(rep, tmp_path):
    paths = R.export_csv_bundle(rep, tmp_path)
    names = {p.name for p in paths}
    assert {"kpis.csv", "at_risk_containers.csv", "README_LABELS.txt", "reroute_opportunities.csv"} <= names
    df = pd.read_csv(tmp_path / "shipment_health_summary.csv")
    assert len(df) == 12 and df["report_label"].str.contains("SIMULATED").all()
    z = zipfile.ZipFile(io.BytesIO(R.csv_bundle_zip(rep)))
    assert set(z.namelist()) == names and "SIMULATED DATA" in z.read("README_LABELS.txt").decode()


def test_pdf_is_valid_and_labelled(rep, cfg, tmp_path):
    p = R.export_pdf(rep, cfg, tmp_path / "r.pdf"); b = p.read_bytes()
    assert b.startswith(b"%PDF") and b.rstrip().endswith(b"%%EOF") and len(b) > 5000
    for needle in (b"AtmoSync Executive Report", b"SIMULATED DATA", b"HEURISTIC ESTIMATES", b"Key performance indicators", b"Potential rerouting opportunities",
                   b"Shipment health summary", b"CNT-009", b"Page 1"):
        assert needle in b, needle
    import re
    assert len(re.findall(rb"/Type /Page[^s]", b)) >= 2                      # several pages (sections flow across pages)


def test_pdf_respects_row_limit_and_handles_empty_tables(rep, cfg, results):
    small = {**cfg, "reporting": {**cfg["reporting"], "top_n_rows": 2}}
    assert len(R.build_pdf_bytes(rep, small)) < len(R.build_pdf_bytes(rep, cfg))        # fewer rows => smaller document
    r2 = dict(results); r2["recs"] = results["recs"].assign(recommended_action="NO_ACTION")
    rep2 = R.build_report(r2, cfg)
    assert rep2.tables["reroute_opportunities"].empty and b"None." in R.build_pdf_bytes(rep2, cfg)


def test_pdf_compression_toggle(rep, cfg):
    comp = {**cfg, "reporting": {**cfg["reporting"], "pdf_compression": True}}
    b = R.build_pdf_bytes(rep, comp)
    assert b.startswith(b"%PDF") and b"SIMULATED DATA" not in b


def test_unknown_dataset_label_is_reported(results):
    assert R._data_labels(results, "HISTORICAL_DERIVED")[-2].endswith("HISTORICAL_DERIVED.")
