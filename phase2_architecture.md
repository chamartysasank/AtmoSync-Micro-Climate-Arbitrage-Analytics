# Phase 2 architecture

Phase 1 architecture (`docs/architecture/architecture.md`) is unchanged: simulator/replay → Kafka → Snowflake → dbt → Tableau, with a local DuckDB equivalent. Phase 2 adds an **analytics and operations layer** on top of the same data; Tableau stays the primary BI dashboard.

```
 raw events ──► ingestion/cleaning ──► analytics/engine (burn rate, risk, arbitrage)      [Phase 1, unchanged logic]
     │                │                         │
     │                ├─► ingestion/quality (B07)     data-quality scores, report, alert candidates
     │                └─► analytics/anomaly (B01)     explained WARNING/CRITICAL flags
     │                                  analytics/health (B02) ─► ops.health_history
     │                                  analytics/forecast (B03)   +6/12/24/48 h heuristic risk
     │                                  analytics/routes (B04)  ◄─ data/sample/route_profiles.csv
     │                                  analytics/market (B05)  ◄─ price datasets (typed SIMULATED / HISTORICAL_DERIVED)
     │                                  analytics/alert_center (B06) ─► ops.alerts, ops.alert_events
     │                                  simulator/lab (B08)        scenarios, replay, comparison
     │                                  analytics/reporting (B09)  KPIs ─► CSV bundle / PDF
     └──────────── run_local.py ─► common/monitoring (B10) ─► ops.pipeline_runs/steps/logs, ops.ingestion_stats
 Streamlit: app/streamlit_app.py builds the sidebar from app/views/*.py (12 pages); all pages read cached results from app/context.py
```
**Persistence.** `common/store.py` (DuckDB, schema `ops`) in the existing `data/processed/atmosync.duckdb`; dbt owns schema `analytics` and the loader owns schema `raw`, so they never collide. In full-integration mode the same ops tables could be created in Snowflake; only the local implementation exists and is tested.
**Configuration.** `config/settings.yaml` (Phase 1) + one file per feature in `config/features/` merged by `load_settings()`; see `docs/reference/configuration.md`.
**Navigation.** Adding a page = adding one module with `TITLE`, `ORDER`, `render(ctx)` to `app/views/`; `tests/test_app_navigation.py` renders every registered page.
**Unchanged:** dbt project and tests, Snowflake SQL, Kafka modules, Tableau data sources and guide, Phase 1 tests (all still pass).
**Reuse rules.** Phase 2 modules call Phase 1 functions instead of re-implementing them: `engine.risk_score/risk_category/burn_rate_at` (extracted from `container_status`, parity-tested against dbt), `clean_sensor_events` (quality), `latest_market_prices` (routes, market), `haversine_km`.
