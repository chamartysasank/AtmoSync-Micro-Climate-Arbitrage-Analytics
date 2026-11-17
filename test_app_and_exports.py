import pandas as pd
from pathlib import Path
from analytics.export_tableau import export


def test_tableau_exports(tmp_path, cfg):
    paths = export(cfg, tmp_path)
    names = {p.name for p in paths}
    assert {"container_health.csv", "arbitrage_recommendations.csv", "executive_kpis.csv", "sensor_hourly.csv"} <= names
    kp = pd.read_csv(tmp_path / "executive_kpis.csv")
    assert kp.shape == (1, 6)


def test_streamlit_app_runs():
    from streamlit.testing.v1 import AppTest
    from common.config import ROOT
    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=60).run()
    assert not at.exception
    assert len(at.metric) == 6
