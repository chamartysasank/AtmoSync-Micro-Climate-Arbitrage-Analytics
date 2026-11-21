import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from common.config import load_settings


@pytest.fixture(scope="session")
def cfg():
    return load_settings()


@pytest.fixture(scope="session")
def results(cfg):
    from analytics.pipeline import run_pipeline
    return run_pipeline(cfg)


@pytest.fixture(autouse=True)
def _isolated_ops_database(tmp_path, monkeypatch):
    """Phase 2: app tables (alerts, history, pipeline logs) never touch the real data/processed database during tests."""
    monkeypatch.setenv("ATMOSYNC_DUCKDB", str(tmp_path / "ops_test.duckdb"))
