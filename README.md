# AtmoSync — Micro-Climate Arbitrage Analytics (Phase 2)
Streaming IoT cold-chain analytics for Hass avocado shipments: **Python simulator → Kafka → Snowflake → dbt → Tableau**, plus a supporting **Streamlit** application with ten Phase 2 features (anomaly detection, shipment health, risk forecasting, route comparison, market intelligence, alert centre, data quality, simulation lab, executive reports, system monitoring).
Internship project (Infotact Solutions). **Primary BI dashboard: Tableau (requested). The original brief specifies Apache Superset — replacing it needs mentor approval** (`docs/setup/superset_alternative.md`). Streamlit is a supporting app and does not replace Tableau.

> **Honesty box.** All sensor, price and route data in this ZIP is **SIMULATED / SAMPLE**. Risk, health, forecast and arbitrage numbers are **heuristic estimates**, not validated spoilage predictions. Kafka, Snowflake and Tableau parts are written but **not tested against live services**; **no Tableau workbook is included**. See `docs/limitations/limitations.md` and `TEST_REPORT.md`.

## Quick start (local mode — no cloud accounts needed)
```bash
python -m venv .venv && source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_local.py --report        # pipeline -> DuckDB -> dbt build -> Tableau CSVs -> Phase 2 persistence -> CSV/PDF report
python -m pytest -q                 # full test suite
streamlit run app/streamlit_app.py  # 12-page supporting app
```
`run_local.py` flags: `--skip-dbt`, `--regenerate` (rebuild sample data), `--skip-phase2`, `--report`, `--no-monitor`. If `dbt build` fails the run stops with exit code 1 (no Tableau export / alerts afterwards).

## Streamlit pages
Overview · Shipment Monitoring · Anomaly Detection · Shipment Health · Risk Forecasting · Route Intelligence · Market Analytics · Alert Centre · Data Quality · Simulation Lab · Reports · System Monitoring (`app/views/*.py`; a page is added by dropping one module into that folder).

## Phase 2 features
| # | Feature | Module | Doc |
|---|---|---|---|
| 1 | Sensor anomaly detection | `analytics/anomaly.py` | `docs/features/01_anomaly_detection.md` |
| 2 | Shipment health scoring | `analytics/health.py`, `common/store.py` | `…/02_shipment_health.md` |
| 3 | Spoilage-risk forecasting (heuristic) | `analytics/forecast.py` | `…/03_risk_forecasting.md` |
| 4 | Route comparison engine | `analytics/routes.py` | `…/04_route_comparison.md` |
| 5 | Market price intelligence | `analytics/market.py` | `…/05_market_intelligence.md` |
| 6 | Alert management centre | `analytics/alert_center.py` | `…/06_alert_centre.md` |
| 7 | Data quality monitoring | `ingestion/quality.py` | `…/07_data_quality.md` |
| 8 | Replay and simulation controls | `simulator/lab.py` | `…/08_simulation_replay.md` |
| 9 | Executive analytics and reporting | `analytics/reporting.py` | `…/09_executive_reporting.md` |
| 10 | System monitoring and documentation | `common/monitoring.py` | `…/10_system_monitoring.md` |
Change summary: `FEATURE_CHANGELOG.md` · upload plan: `BATCH_UPLOAD_GUIDE.md` · results: `TEST_REPORT.md` · demo script: `docs/DEMO_GUIDE.md` · references: `docs/reference/` (Python API, configuration).

## Folder map
| Path | Purpose |
|---|---|
| `config/` | `settings.yaml`, `commodities.yaml`, **`features/*.yaml`** (one file per Phase 2 feature, merged automatically) |
| `common/` | config loader, **`store.py`** (DuckDB `ops` tables), **`monitoring.py`** |
| `simulator/`, `scripts/` | Phase 1 fleet simulator, **`lab.py`**; sample-data generator, dataset helper, Snowflake loader, doc generators |
| `ingestion/` | cleaning, replay, local warehouse, HAB adapter, **`quality.py`** |
| `streaming/` | Kafka producer/consumer (with consumer-side DLQ), sinks, benchmark, docker-compose |
| `snowflake/sql/`, `dbt_project/` | warehouse scripts; dbt staging → intermediate → marts (52 checks) — unchanged in Phase 2 |
| `analytics/` | Phase 1 engine/alerts/export + Phase 2 feature modules |
| `app/` | Streamlit entry point, `context.py`, `views/` |
| `tableau/` | data sources, calculated fields, build guide (primary BI tool) |
| `data/sample/` | simulated sample data (+ `route_profiles.csv`) |
| `docs/`, `reports/` | documentation; example outputs |
| `batch_upload/` | ready-to-copy folders for the 10 manual GitHub uploads |

## Modes
* **A – Local:** everything runs offline; DuckDB stands in for Snowflake and runs the *same* dbt models.
* **B – Full:** `docs/setup/full_integration.md` (Kafka via Docker, Snowflake, dbt-snowflake, Tableau live connection). Untested against live services.
Secrets: never commit `.env`; credentials are read from environment variables only (`.env.example`).
