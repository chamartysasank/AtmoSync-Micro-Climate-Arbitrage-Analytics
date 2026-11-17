import pandas as pd
from ingestion.cleaning import clean_sensor_events
import pytest


def _row(**kw):
    base = dict(event_id="e1", container_id="C1", sensor_id="S1", shipment_id="SH1", reading_ts="2026-01-01T00:00:00Z",
                temperature_c=7.0, humidity_pct=90.0, vibration_g=0.2)
    base.update(kw); return base


def test_duplicates_sentinels_and_ranges(cfg):
    raw = pd.DataFrame([_row(), _row(), _row(event_id="e2", reading_ts="2026-01-01T00:15:00Z", temperature_c=-999),
                        _row(event_id="e3", reading_ts="2026-01-01T00:30:00Z", humidity_pct=140),
                        _row(event_id="e4", reading_ts="not-a-date")])
    clean, rej, st = clean_sensor_events(raw, cfg)
    assert len(clean) == 1 and st["duplicates_removed"] == 1 and len(rej) == 3
    assert clean["reading_ts"].dt.tz is None


def test_missing_required_column(cfg):
    with pytest.raises(ValueError):
        clean_sensor_events(pd.DataFrame([{"container_id": "C"}]), cfg)


def test_sample_data_cleaning(results):
    assert results["cleaning_stats"].iloc[0]["clean_rows"] > 700
    assert results["clean"].duplicated(["container_id", "sensor_id", "reading_ts"]).sum() == 0
