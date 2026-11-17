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
