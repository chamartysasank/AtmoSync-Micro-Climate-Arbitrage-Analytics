# Feature changelog — Phase 2

Phase 1 (107 files, 39 tests) is preserved: no Phase 1 file was deleted; 10 Phase 1 files were modified (listed below); all 39 Phase 1 tests are unchanged and still pass.

## Summary of modified existing files

| File | Batch | Change |
|---|---|---|
| `analytics/pipeline.py` | 01 | `run_pipeline` additionally returns the raw events (`raw`) |
| `app/streamlit_app.py` | 01 | sidebar navigation built from `app/views/*.py` |
| `common/config.py` | 01 | `load_settings()` merges `config/features/*.yaml` |
| `analytics/engine.py` | 03 | extracted `risk_score`, `risk_category`, `burn_rate_at` from `container_status` |
| `common/store.py` | 06 | all-null object columns are stored as VARCHAR (needed for alert rows before acknowledgement) |
| `analytics/pipeline.py` | 07 | `run_pipeline` additionally returns `quality` (QualityReport) |
| `requirements.txt` | 09 | adds `reportlab>=4.0` |
| `.gitignore` | 10 | ignores generated Phase 2 outputs |
| `README.md` | 10 | rewritten for the complete project |
| `common/store.py` | 10 | default database honours `ATMOSYNC_DUCKDB` |
| `docs/setup/github_upload_guide.md` | 10 | pointer to the Phase 2 batch guide |
| `run_local.py` | 10 | monitored steps, `--skip-phase2/--report/--no-monitor` flags (dbt-failure stop unchanged) |
| `tests/conftest.py` | 10 | tests use a temporary ops database |

## 01 — Sensor Anomaly Detection

Detects missing, invalid, out-of-threshold, statistically unusual, fast-changing, stuck-sensor and reporting-gap readings; WARNING/CRITICAL severity; plain-English reason for every flag. Also converts the Phase 1 single-page app into a registry-based 12-slot navigation (Overview and Shipment Monitoring keep all Phase 1 content).

- **New files (10):** `analytics/anomaly.py`, `app/context.py`, `app/views/__init__.py`, `app/views/anomaly.py`, `app/views/monitoring.py`, `app/views/overview.py`, `config/features/anomaly.yaml`, `docs/features/01_anomaly_detection.md`, `tests/test_anomaly.py`, `tests/test_app_navigation.py`
- **Modified:** `analytics/pipeline.py`, `app/streamlit_app.py`, `common/config.py`
- **Tests:** tests/test_anomaly.py (14), tests/test_app_navigation.py (4: registry + 3 pages)
- **Docs:** docs/features/01_anomaly_detection.md
- **Limitations:** thresholds are heuristics; z-score misses slow drifts (threshold check covers them).

## 02 — Shipment Health Scoring

0–100 condition score (Healthy/Warning/At Risk/Critical) from temperature, humidity and vibration with a failure cap, explanation text and hourly history persisted in DuckDB (`ops.health_history`). Introduces the reusable `common/store.py`.

- **New files (6):** `analytics/health.py`, `app/views/health.py`, `common/store.py`, `config/features/health.yaml`, `docs/features/02_shipment_health.md`, `tests/test_health_store.py`
- **Modified:** none
- **Tests:** tests/test_health_store.py (17); navigation test gains one page
- **Docs:** docs/features/02_shipment_health.md
- **Limitations:** weights and penalty scales are assumptions; condition score, not a spoilage prediction.

## 03 — Spoilage Risk Forecasting

Heuristic risk forecast at +6/12/24/48 h under hold / trend / pessimistic scenarios, with explicit HEURISTIC (not validated) labelling and an assumptions table. Refactors Phase 1 scoring arithmetic into reusable helpers (behaviour unchanged, dbt parity tests still pass).

- **New files (5):** `analytics/forecast.py`, `app/views/forecast.py`, `config/features/forecast.yaml`, `docs/features/03_risk_forecasting.md`, `tests/test_forecast.py`
- **Modified:** `analytics/engine.py`
- **Tests:** tests/test_forecast.py (9); navigation +1
- **Docs:** docs/features/03_risk_forecasting.md
- **Limitations:** linear extrapolation; scenarios are what-ifs, not probabilities; unvalidated.

## 04 — Route Comparison Engine

Compares destination × route-profile options (distance, time, transport cost, illustrative exposure, vibration, rerouting cost) with explained recommendations; reroute only when the current route would degrade the fruit. Uses clearly labelled SAMPLE route profiles.

- **New files (6):** `analytics/routes.py`, `app/views/routes.py`, `config/features/routes.yaml`, `data/sample/route_profiles.csv`, `docs/features/04_route_comparison.md`, `tests/test_routes.py`
- **Modified:** none
- **Tests:** tests/test_routes.py (8); navigation +1
- **Docs:** docs/features/04_route_comparison.md
- **Limitations:** route profiles and exposure effects are illustrative; no live traffic/weather.

## 05 — Market Price Intelligence

Typed price datasets (SIMULATED / HISTORICAL_DERIVED), market comparison, trends, volatility, gross and net market-to-market margins after transport and handling, simulated what-if series.

- **New files (5):** `analytics/market.py`, `app/views/market.py`, `config/features/market.yaml`, `docs/features/05_market_intelligence.md`, `tests/test_market.py`
- **Modified:** none
- **Tests:** tests/test_market.py (9); navigation +1
- **Docs:** docs/features/05_market_intelligence.md
- **Limitations:** no real wholesale series bundled; margins ignore spoilage.

## 06 — Alert Management Centre

WARNING/CRITICAL alerts from risk, health, anomaly, forecast and arbitrage results; timestamps, categories, acknowledgement/resolution, escalation/reopen logic, full history, filters by shipment/container/date/severity/status/category; persisted in DuckDB (`ops.alerts`, `ops.alert_events`).

- **New files (5):** `analytics/alert_center.py`, `app/views/alerts.py`, `config/features/alerts.yaml`, `docs/features/06_alert_centre.md`, `tests/test_alert_center.py`
- **Modified:** `common/store.py`
- **Tests:** tests/test_alert_center.py (12); navigation +1
- **Docs:** docs/features/06_alert_centre.md
- **Limitations:** single-user local store; actor is free text; Slack/e-mail not wired to the centre.

## 07 — Data Quality Monitoring

Missing/duplicate/invalid/out-of-range detection reusing the Phase 1 cleaning rules, completeness/validity/uniqueness/timeliness/overall scores, per-container and per-field tables, Markdown report, alert candidates, stored history. Integrated into `run_pipeline`.

- **New files (6):** `app/views/quality.py`, `config/features/quality.yaml`, `docs/features/07_data_quality.md`, `ingestion/quality.py`, `reports/data_quality/example_data_quality_report_sample_data.md`, `tests/test_quality.py`
- **Modified:** `analytics/pipeline.py`
- **Tests:** tests/test_quality.py (10); navigation +1
- **Docs:** docs/features/07_data_quality.md
- **Limitations:** weights/thresholds are assumptions; expected-readings assumes a fixed interval.

## 08 — Shipment Replay and Simulation

Eight configurable scenario presets (spike, drift, compressor failure, humidity swings/loss, vibration bursts, combined), normal-vs-abnormal comparison on identical noise, historical replay 'as of time T', container-vs-container comparison, Simulation Lab page.

- **New files (5):** `app/views/simulation.py`, `config/features/simulation.yaml`, `docs/features/08_simulation_replay.md`, `simulator/lab.py`, `tests/test_simulation_lab.py`
- **Modified:** none
- **Tests:** tests/test_simulation_lab.py (10); navigation +1
- **Docs:** docs/features/08_simulation_replay.md
- **Limitations:** single-container scenarios; fault shapes not calibrated.

## 09 — Executive Analytics and Reporting

Executive KPIs, health/at-risk/critical/market/reroute/route tables, CSV bundle and PDF export, every output labelled SIMULATED and HEURISTIC. New dependency: reportlab.

- **New files (7):** `analytics/reporting.py`, `app/views/reports.py`, `config/features/reporting.yaml`, `docs/features/09_executive_reporting.md`, `reports/exports/example_executive_report_sample_data.pdf`, `reports/exports/example_kpis_sample_data.csv`, `tests/test_reporting.py`
- **Modified:** `requirements.txt`
- **Tests:** tests/test_reporting.py (8); navigation +1
- **Docs:** docs/features/09_executive_reporting.md
- **Limitations:** plain tabular PDF; first N rows per table in the PDF.

## 10 — System Monitoring and Documentation

Pipeline run/step/log/ingestion-statistics recording, health indicators, error summary, integration configuration status, monitored `run_local.py` with Phase 2 persistence steps; generated Python-API and configuration references, Phase 2 architecture, demonstration guide, README, changelog, upload guide, test report.

- **New files (14):** `BATCH_UPLOAD_GUIDE.md`, `FEATURE_CHANGELOG.md`, `TEST_REPORT.md`, `app/views/system.py`, `common/monitoring.py`, `config/features/monitoring.yaml`, `docs/DEMO_GUIDE.md`, `docs/architecture/phase2_architecture.md`, `docs/features/10_system_monitoring.md`, `docs/reference/configuration.md`, `docs/reference/python_api.md`, `scripts/gen_api_docs.py`, `scripts/gen_config_reference.py`, `tests/test_monitoring.py`
- **Modified:** `.gitignore`, `README.md`, `common/store.py`, `docs/setup/github_upload_guide.md`, `run_local.py`, `tests/conftest.py`
- **Tests:** tests/test_monitoring.py (12); navigation +1
- **Docs:** docs/features/10_system_monitoring.md, docs/reference/*, docs/architecture/phase2_architecture.md, docs/DEMO_GUIDE.md, FEATURE_CHANGELOG.md, BATCH_UPLOAD_GUIDE.md, TEST_REPORT.md
- **Limitations:** single local database; integration status is configuration presence only.
