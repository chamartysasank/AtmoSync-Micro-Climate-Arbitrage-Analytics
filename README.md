# AtmoSync — Micro-Climate Arbitrage Analytics
Streaming IoT cold-chain analytics for Hass avocado shipments: **Python simulator → Kafka → Snowflake → dbt → Tableau**, with a transparent shelf-life heuristic and a quality-adjusted rerouting ("spoilage arbitrage") recommendation.
Internship project (Infotact Solutions). **Dashboard tool: Tableau (requested). The original brief specifies Apache Superset — replacing it needs mentor approval** (see `docs/setup/superset_alternative.md`).

> **Honesty box.** All sensor and price data in the ZIP is **SIMULATED**. The quality model is a **heuristic**, not a validated spoilage model. Kafka, Snowflake and Tableau parts are written but **not tested against live services**, and **no Tableau workbook is included** — see `docs/limitations/limitations.md`.

## Quick start (local mode, no cloud accounts)
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_local.py          # clean → analytics → DuckDB → dbt build (52 checks) → Tableau CSVs → dry-run alerts
python -m pytest -q          # 39 tests
streamlit run app/streamlit_app.py   # optional preview
```
Expected demo output: 12 containers, 9 healthy, 3 at risk, 1 critical, 1 reroute opportunity (CNT-009 Chicago → Denver). These are demonstration values from simulated data.

## Folder map
| Path | Purpose |
|---|---|
| `config/` | `settings.yaml` (all parameters, tagged SOURCE/ASSUMPTION), `commodities.yaml` |
| `simulator/`, `scripts/` | IoT simulator, sample-data generator, dataset download helper, Snowflake loader |
| `ingestion/` | cleaning/validation, historical replay, local DuckDB warehouse, HAB price adapter |
| `streaming/` | Kafka producer/consumer/sinks/benchmark/docker-compose (`kafka/` renamed to avoid shadowing the library) |
| `snowflake/sql/` | warehouse setup, raw DDL, analysis queries, clustering/MV/task |
| `dbt_project/` | staging → intermediate → marts, tests, macros, profiles (DuckDB + Snowflake) |
| `analytics/` | pandas reference engine, alerts, Tableau export |
| `tableau/` | data sources, calculated fields, `dashboard_guide.md` |
| `app/` | optional Streamlit UI |
| `docs/` | architecture, dataset research, methodology, setup, limitations, learning guide, data dictionary |
| `reports/` | `test_report.md` |

## Modes
* **A – Local:** everything above runs offline; DuckDB stands in for Snowflake and runs the *same* dbt models.
* **B – Full:** `docs/setup/full_integration.md` (Kafka via Docker, Snowflake, dbt-snowflake, Tableau live connection).
## Docs to read first
`docs/dataset_research/DATASET_RESEARCH.md` · `docs/methodology/methodology.md` · `docs/methodology/assumptions.md` · `tableau/dashboard_guide.md` · `docs/setup/learning_guide.md`
Secrets: never commit `.env`; credentials are read from environment variables only.
