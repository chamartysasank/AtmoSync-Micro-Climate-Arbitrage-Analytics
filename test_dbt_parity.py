"""Checks that dbt (DuckDB) results equal the pandas reference. Needs `dbt` + dbt-duckdb installed."""
import shutil, subprocess, sys
import duckdb, pandas as pd, pytest
from pathlib import Path
from common.config import ROOT
from ingestion.local_warehouse import load_local_warehouse

pytestmark = pytest.mark.skipif(shutil.which("dbt") is None, reason="dbt not installed")


@pytest.fixture(scope="module")
def dbt_db(tmp_path_factory, cfg):
    db = tmp_path_factory.mktemp("w") / "parity.duckdb"
    load_local_warehouse(cfg, db_file=db)
    env = {**__import__("os").environ, "ATMOSYNC_DUCKDB": str(db)}
    r = subprocess.run(["dbt", "build", "--profiles-dir", ".", "--target", "duckdb"], cwd=ROOT / "dbt_project", env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-2000:]
    con = duckdb.connect(str(db), read_only=True); yield con; con.close()


def test_container_status_parity(dbt_db, results):
    sql = dbt_db.execute("select * from analytics.mart_container_health order by container_id").df().set_index("container_id")
    pdf = results["status"].sort_values("container_id").set_index("container_id")
    for col in ["life_consumed_fraction", "recent_burn_rate", "quality_window_hours", "hours_to_destination", "slack_hours", "risk_score", "avg_temp_c"]:
        pd.testing.assert_series_equal(sql[col].astype(float), pdf[col].astype(float), check_names=False, rtol=1e-6, atol=1e-6)
    assert (sql["risk_category"] == pdf["risk_category"]).all()


def test_recommendation_parity(dbt_db, results):
    sql = dbt_db.execute("select * from analytics.mart_arbitrage_recommendations order by container_id").df().set_index("container_id")
    pdf = results["recs"].sort_values("container_id").set_index("container_id")
    assert (sql["recommended_action"] == pdf["recommended_action"]).all()
    assert (sql["best_alternative"] == pdf["best_alternative"]).all()
    pd.testing.assert_series_equal(sql["best_benefit_usd"].astype(float), pdf["best_benefit_usd"].astype(float), check_names=False, rtol=1e-6)


def test_kpi_parity(dbt_db, results):
    sql = dbt_db.execute("select * from analytics.mart_executive_kpis").df().iloc[0]
    k = results["kpis"].iloc[0]
    for c in ["total_containers", "healthy_containers", "at_risk_containers", "critical_alerts", "arbitrage_opportunities"]:
        assert int(sql[c]) == int(k[c])
    assert abs(float(sql["estimated_benefit_usd"]) - float(k["estimated_benefit_usd"])) < 0.01
