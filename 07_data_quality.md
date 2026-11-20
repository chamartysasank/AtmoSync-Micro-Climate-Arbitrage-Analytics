# Feature 7 — Data Quality Monitoring (Batch 07)
**Depends on:** Batch 01 (navigation, config merge); optional links to Batch 02 (`common/store.py` for history) and Batch 06 (alerts via the `extra=` hook).

**What it does.** Measures missing values, duplicates, invalid readings and out-of-range values; computes completeness, validity, uniqueness, timeliness and overall scores (0–100) overall, per container and per field; writes a quality report.

**How it works** (`ingestion/quality.py::assess_quality`)
- **Validity re-uses the Phase 1 cleaning rules** (`ingestion/cleaning.py`), so the number of rejected rows always equals what the pipeline really drops (unit-tested on the sample data: 7 rejected, 8 duplicates).
- Completeness = mean(non-null share of required fields, received ÷ expected readings per container); uniqueness = 1 − duplicates ÷ rows; timeliness = share of containers not stale; overall = weighted mean (0.4 / 0.4 / 0.1 / 0.1, configurable).
- Findings list (CRITICAL/WARNING/INFO) names the field or container affected; absent required columns are reported as CRITICAL.
**Pipeline integration (modified file):** `analytics/pipeline.py::run_pipeline` now returns `quality` next to the existing outputs.
**Configure:** `config/features/quality.yaml` (required fields, weights, alert thresholds, stale minutes, report directory).
**Run:** `python -m ingestion.quality [--source file.csv] [--save]` (writes `reports/data_quality/` and a history row in `ops.dq_reports`); UI **Data Quality** (scores, issue counts, findings filter, per-container chart, downloads, history). `quality_alert_candidates()` produces alert-centre candidates: `sync_alerts(collect_candidates(r, cfg, extra=quality_alert_candidates(r["quality"], cfg)))`.
**Example (shipped sample):** `reports/data_quality/example_data_quality_report_sample_data.md` — overall 99.3 (GOOD): 4 missing, 1 sentinel, 2 impossible RH, 8 duplicates, 12 missing readings (CNT-012 communication blackout, coverage 83 %).
**Tests:** `tests/test_quality.py` (10 tests).
**Limitations:** thresholds are assumptions; "expected readings" assumes a fixed reporting interval; DuckDB history is local only; Snowflake-side quality tests are the dbt tests from Phase 1.
