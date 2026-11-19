# Batch upload guide (manual GitHub upload, 10 batches)

No GitHub operation was performed by the assistant. You upload; this guide tells you what, in which order.

## How to use
1. Your repository should already contain the **Phase 1 project** (`AtmoSync_Complete_Project.zip`, 107 files).
2. For each batch take the files from **`batch_upload/batch_NN_<name>/`** in this ZIP — *not* from the project root. Modified files have changed in later batches too, so the folder copy is the exact version that matches that batch (each one was verified by hash).
3. Copy the folder *contents* over your repository working tree keeping the paths (or upload via **Add file ▸ Upload files**, dragging the sub-folders), then commit with the suggested message. One batch per day is fine; never skip a batch (each lists the earlier batches it needs).
4. After every batch run `python -m pytest -q`; the expected cumulative result is shown below (we built and tested the repository cumulatively after each batch: 57, 75, 85, 94, 104, 117, 128, 139, 148, 161 tests passed).
5. Do not upload `.env`, `.venv/`, `__pycache__/`, `*.duckdb`, or generated files in `data/processed/`. The project-root files of this ZIP are the final integrated version (all batches); you can instead upload it once after finishing the batches to confirm nothing differs. `pytest.ini` exists only so that pytest ignores the `batch_upload/` copies inside this ZIP; you do not need to upload it (or `batch_upload/`) to GitHub.

| Batch | Feature | Needs | New | Modified | Tests after batch |
|---|---|---|---|---|---|
| 01 | Sensor Anomaly Detection | Phase 1 only | 10 | 3 | 57 passed |
| 02 | Shipment Health Scoring | Batch 01 | 6 | 0 | 75 passed |
| 03 | Spoilage Risk Forecasting | Batch 01 | 5 | 1 | 85 passed |
| 04 | Route Comparison Engine | Batch 01 | 6 | 0 | 94 passed |
| 05 | Market Price Intelligence | Batch 01 | 5 | 0 | 104 passed |
| 06 | Alert Management Centre | Batches 01, 02, 03 | 5 | 1 | 117 passed |
| 07 | Data Quality Monitoring | Batches 01, 02 | 6 | 1 | 128 passed |
| 08 | Shipment Replay and Simulation | Batches 01, 02, 03 | 5 | 0 | 139 passed |
| 09 | Executive Analytics and Reporting | Batches 01–05 and 07 | 7 | 1 | 148 passed |
| 10 | System Monitoring and Documentation | Batches 01–09 | 14 | 6 | 161 passed |

## Batch 01 — Sensor Anomaly Detection

**Folder:** `batch_upload/batch_01_sensor_anomaly_detection/`  ·  **Depends on:** Phase 1 only (this batch also adds the Streamlit navigation scaffold and the `config/features/` loader that all later batches use)

**What it adds:** Detects missing, invalid, out-of-threshold, statistically unusual, fast-changing, stuck-sensor and reporting-gap readings; WARNING/CRITICAL severity; plain-English reason for every flag. Also converts the Phase 1 single-page app into a registry-based 12-slot navigation (Overview and Shipment Monitoring keep all Phase 1 content).

**New files**
- `analytics/anomaly.py`
- `app/context.py`
- `app/views/__init__.py`
- `app/views/anomaly.py`
- `app/views/monitoring.py`
- `app/views/overview.py`
- `config/features/anomaly.yaml`
- `docs/features/01_anomaly_detection.md`
- `tests/test_anomaly.py`
- `tests/test_app_navigation.py`

**Modified existing files**
- `analytics/pipeline.py` — `run_pipeline` additionally returns the raw events (`raw`)
- `app/streamlit_app.py` — sidebar navigation built from `app/views/*.py`
- `common/config.py` — `load_settings()` merges `config/features/*.yaml`

**Tests:** tests/test_anomaly.py (14), tests/test_app_navigation.py (4: registry + 3 pages) → cumulative **57 passed** (was 39).

**Documentation:** docs/features/01_anomaly_detection.md

**Run / verify:** `python -m pytest -q  ·  streamlit run app/streamlit_app.py → Anomaly Detection`

**Known limitations:** thresholds are heuristics; z-score misses slow drifts (threshold check covers them).

**Suggested commit message:** `Add sensor anomaly detection and page navigation`

**Upload sequence:** (1) code and config files, (2) tests, (3) docs/data — any order works inside the batch because it is one commit.

---

## Batch 02 — Shipment Health Scoring

**Folder:** `batch_upload/batch_02_shipment_health_scoring/`  ·  **Depends on:** Batch 01

**What it adds:** 0–100 condition score (Healthy/Warning/At Risk/Critical) from temperature, humidity and vibration with a failure cap, explanation text and hourly history persisted in DuckDB (`ops.health_history`). Introduces the reusable `common/store.py`.

**New files**
- `analytics/health.py`
- `app/views/health.py`
- `common/store.py`
- `config/features/health.yaml`
- `docs/features/02_shipment_health.md`
- `tests/test_health_store.py`

**Modified existing files**
- (none)

**Tests:** tests/test_health_store.py (17); navigation test gains one page → cumulative **75 passed** (was 57).

**Documentation:** docs/features/02_shipment_health.md

**Run / verify:** `python -m analytics.health`

**Known limitations:** weights and penalty scales are assumptions; condition score, not a spoilage prediction.

**Suggested commit message:** `Add shipment health scoring and local history store`

**Upload sequence:** (1) code and config files, (2) tests, (3) docs/data — any order works inside the batch because it is one commit.

---

## Batch 03 — Spoilage Risk Forecasting

**Folder:** `batch_upload/batch_03_spoilage_risk_forecasting/`  ·  **Depends on:** Batch 01

**What it adds:** Heuristic risk forecast at +6/12/24/48 h under hold / trend / pessimistic scenarios, with explicit HEURISTIC (not validated) labelling and an assumptions table. Refactors Phase 1 scoring arithmetic into reusable helpers (behaviour unchanged, dbt parity tests still pass).

**New files**
- `analytics/forecast.py`
- `app/views/forecast.py`
- `config/features/forecast.yaml`
- `docs/features/03_risk_forecasting.md`
- `tests/test_forecast.py`

**Modified existing files**
- `analytics/engine.py` — extracted `risk_score`, `risk_category`, `burn_rate_at` from `container_status`

**Tests:** tests/test_forecast.py (9); navigation +1 → cumulative **85 passed** (was 75).

**Documentation:** docs/features/03_risk_forecasting.md

**Run / verify:** `python -m analytics.forecast`

**Known limitations:** linear extrapolation; scenarios are what-ifs, not probabilities; unvalidated.

**Suggested commit message:** `Add heuristic spoilage risk forecasting`

**Upload sequence:** (1) code and config files, (2) tests, (3) docs/data — any order works inside the batch because it is one commit.

---

## Batch 04 — Route Comparison Engine

**Folder:** `batch_upload/batch_04_route_comparison_engine/`  ·  **Depends on:** Batch 01

**What it adds:** Compares destination × route-profile options (distance, time, transport cost, illustrative exposure, vibration, rerouting cost) with explained recommendations; reroute only when the current route would degrade the fruit. Uses clearly labelled SAMPLE route profiles.

**New files**
- `analytics/routes.py`
- `app/views/routes.py`
- `config/features/routes.yaml`
- `data/sample/route_profiles.csv`
- `docs/features/04_route_comparison.md`
- `tests/test_routes.py`

**Modified existing files**
- (none)

**Tests:** tests/test_routes.py (8); navigation +1 → cumulative **94 passed** (was 85).

**Documentation:** docs/features/04_route_comparison.md

**Run / verify:** `python -m analytics.routes`

**Known limitations:** route profiles and exposure effects are illustrative; no live traffic/weather.

**Suggested commit message:** `Add route comparison engine with sample route profiles`

**Upload sequence:** (1) code and config files, (2) tests, (3) docs/data — any order works inside the batch because it is one commit.

---

## Batch 05 — Market Price Intelligence

**Folder:** `batch_upload/batch_05_market_price_intelligence/`  ·  **Depends on:** Batch 01

**What it adds:** Typed price datasets (SIMULATED / HISTORICAL_DERIVED), market comparison, trends, volatility, gross and net market-to-market margins after transport and handling, simulated what-if series.

**New files**
- `analytics/market.py`
- `app/views/market.py`
- `config/features/market.yaml`
- `docs/features/05_market_intelligence.md`
- `tests/test_market.py`

**Modified existing files**
- (none)

**Tests:** tests/test_market.py (9); navigation +1 → cumulative **104 passed** (was 94).

**Documentation:** docs/features/05_market_intelligence.md

**Run / verify:** `python -m analytics.market`

**Known limitations:** no real wholesale series bundled; margins ignore spoilage.

**Suggested commit message:** `Add market price intelligence`

**Upload sequence:** (1) code and config files, (2) tests, (3) docs/data — any order works inside the batch because it is one commit.

---

## Batch 06 — Alert Management Centre

**Folder:** `batch_upload/batch_06_alert_management_centre/`  ·  **Depends on:** Batches 01, 02, 03 (uses `common/store.py`, anomalies, health, forecast)

**What it adds:** WARNING/CRITICAL alerts from risk, health, anomaly, forecast and arbitrage results; timestamps, categories, acknowledgement/resolution, escalation/reopen logic, full history, filters by shipment/container/date/severity/status/category; persisted in DuckDB (`ops.alerts`, `ops.alert_events`).

**New files**
- `analytics/alert_center.py`
- `app/views/alerts.py`
- `config/features/alerts.yaml`
- `docs/features/06_alert_centre.md`
- `tests/test_alert_center.py`

**Modified existing files**
- `common/store.py` — all-null object columns are stored as VARCHAR (needed for alert rows before acknowledgement)

**Tests:** tests/test_alert_center.py (12); navigation +1 → cumulative **117 passed** (was 104).

**Documentation:** docs/features/06_alert_centre.md

**Run / verify:** `python -m analytics.alert_center --sync`

**Known limitations:** single-user local store; actor is free text; Slack/e-mail not wired to the centre.

**Suggested commit message:** `Add alert management centre`

**Upload sequence:** (1) code and config files, (2) tests, (3) docs/data — any order works inside the batch because it is one commit.

---

## Batch 07 — Data Quality Monitoring

**Folder:** `batch_upload/batch_07_data_quality_monitoring/`  ·  **Depends on:** Batches 01, 02 (imports `common/store.py`); the alert hook uses Batch 06 only when you pass candidates in

**What it adds:** Missing/duplicate/invalid/out-of-range detection reusing the Phase 1 cleaning rules, completeness/validity/uniqueness/timeliness/overall scores, per-container and per-field tables, Markdown report, alert candidates, stored history. Integrated into `run_pipeline`.

**New files**
- `app/views/quality.py`
- `config/features/quality.yaml`
- `docs/features/07_data_quality.md`
- `ingestion/quality.py`
- `reports/data_quality/example_data_quality_report_sample_data.md`
- `tests/test_quality.py`

**Modified existing files**
- `analytics/pipeline.py` — `run_pipeline` additionally returns `quality` (QualityReport)

**Tests:** tests/test_quality.py (10); navigation +1 → cumulative **128 passed** (was 117).

**Documentation:** docs/features/07_data_quality.md

**Run / verify:** `python -m ingestion.quality --save`

**Known limitations:** weights/thresholds are assumptions; expected-readings assumes a fixed interval.

**Suggested commit message:** `Add data quality monitoring`

**Upload sequence:** (1) code and config files, (2) tests, (3) docs/data — any order works inside the batch because it is one commit.

---

## Batch 08 — Shipment Replay and Simulation

**Folder:** `batch_upload/batch_08_shipment_replay_simulation/`  ·  **Depends on:** Batches 01, 02, 03 (anomalies, health, forecast)

**What it adds:** Eight configurable scenario presets (spike, drift, compressor failure, humidity swings/loss, vibration bursts, combined), normal-vs-abnormal comparison on identical noise, historical replay 'as of time T', container-vs-container comparison, Simulation Lab page.

**New files**
- `app/views/simulation.py`
- `config/features/simulation.yaml`
- `docs/features/08_simulation_replay.md`
- `simulator/lab.py`
- `tests/test_simulation_lab.py`

**Modified existing files**
- (none)

**Tests:** tests/test_simulation_lab.py (10); navigation +1 → cumulative **139 passed** (was 128).

**Documentation:** docs/features/08_simulation_replay.md

**Run / verify:** `python -m simulator.lab`

**Known limitations:** single-container scenarios; fault shapes not calibrated.

**Suggested commit message:** `Add simulation lab and historical replay`

**Upload sequence:** (1) code and config files, (2) tests, (3) docs/data — any order works inside the batch because it is one commit.

---

## Batch 09 — Executive Analytics and Reporting

**Folder:** `batch_upload/batch_09_executive_analytics_reporting/`  ·  **Depends on:** Batches 01–05 and 07 (assembles their results)

**What it adds:** Executive KPIs, health/at-risk/critical/market/reroute/route tables, CSV bundle and PDF export, every output labelled SIMULATED and HEURISTIC. New dependency: reportlab.

**New files**
- `analytics/reporting.py`
- `app/views/reports.py`
- `config/features/reporting.yaml`
- `docs/features/09_executive_reporting.md`
- `reports/exports/example_executive_report_sample_data.pdf`
- `reports/exports/example_kpis_sample_data.csv`
- `tests/test_reporting.py`

**Modified existing files**
- `requirements.txt` — adds `reportlab>=4.0`

**Tests:** tests/test_reporting.py (8); navigation +1 → cumulative **148 passed** (was 139).

**Documentation:** docs/features/09_executive_reporting.md

**Run / verify:** `python -m analytics.reporting`

**Known limitations:** plain tabular PDF; first N rows per table in the PDF.

**Suggested commit message:** `Add executive reporting with CSV and PDF export`

**Upload sequence:** (1) code and config files, (2) tests, (3) docs/data — any order works inside the batch because it is one commit.

---

## Batch 10 — System Monitoring and Documentation

**Folder:** `batch_upload/batch_10_system_monitoring_documentation/`  ·  **Depends on:** Batches 01–09

**What it adds:** Pipeline run/step/log/ingestion-statistics recording, health indicators, error summary, integration configuration status, monitored `run_local.py` with Phase 2 persistence steps; generated Python-API and configuration references, Phase 2 architecture, demonstration guide, README, changelog, upload guide, test report.

**New files**
- `BATCH_UPLOAD_GUIDE.md`
- `FEATURE_CHANGELOG.md`
- `TEST_REPORT.md`
- `app/views/system.py`
- `common/monitoring.py`
- `config/features/monitoring.yaml`
- `docs/DEMO_GUIDE.md`
- `docs/architecture/phase2_architecture.md`
- `docs/features/10_system_monitoring.md`
- `docs/reference/configuration.md`
- `docs/reference/python_api.md`
- `scripts/gen_api_docs.py`
- `scripts/gen_config_reference.py`
- `tests/test_monitoring.py`

**Modified existing files**
- `.gitignore` — ignores generated Phase 2 outputs
- `README.md` — rewritten for the complete project
- `common/store.py` — default database honours `ATMOSYNC_DUCKDB`
- `docs/setup/github_upload_guide.md` — pointer to the Phase 2 batch guide
- `run_local.py` — monitored steps, `--skip-phase2/--report/--no-monitor` flags (dbt-failure stop unchanged)
- `tests/conftest.py` — tests use a temporary ops database

**Tests:** tests/test_monitoring.py (12); navigation +1 → cumulative **161 passed** (was 148).

**Documentation:** docs/features/10_system_monitoring.md, docs/reference/*, docs/architecture/phase2_architecture.md, docs/DEMO_GUIDE.md, FEATURE_CHANGELOG.md, BATCH_UPLOAD_GUIDE.md, TEST_REPORT.md

**Run / verify:** `python run_local.py --report`

**Known limitations:** single local database; integration status is configuration presence only.

**Suggested commit message:** `Add system monitoring, documentation and project reports`

**Upload sequence:** (1) code and config files, (2) tests, (3) docs/data — any order works inside the batch because it is one commit.

---

## Suggested 10-day schedule

Day 1 → Batch 01 · Day 2 → 02 · Day 3 → 03 · Day 4 → 04 · Day 5 → 05 · Day 6 → 06 · Day 7 → 07 · Day 8 → 08 · Day 9 → 09 · Day 10 → 10 (after which your repository equals the project root of this ZIP).

## Dependency graph

`01` ← `02`,`03`,`04`,`05` · `02`+`03` ← `06`,`08` · `02` ← `07` · `01–05`+`07` ← `09` · `01–09` ← `10`. Batches 02–05 are independent of each other (you may reorder them), but 06–10 must follow their dependencies.
