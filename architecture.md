# Architecture

```
            MODE A (local, runs on any laptop)                       MODE B (full integration)
 ┌──────────────────────────────┐                         ┌──────────────────────────────────────────┐
 │ simulator/ + data/sample CSV │                         │ simulator / replay → Kafka topic          │
 │ ingestion/replay.py          │                         │   atmosync.sensor.events (+ .dlq)         │
 └──────────────┬───────────────┘                         │ streaming/consumer.py → Snowflake RAW     │
                ▼                                         └─────────────────────┬────────────────────┘
 ingestion/cleaning.py (pandas)                                                   ▼
 analytics/engine.py (reference)             dbt models (same SQL both modes)  staging → intermediate → marts
 ingestion/local_warehouse.py → DuckDB  ───► dbt-duckdb target                 dbt-snowflake target
                │                                                                 │
                ▼                                                                 ▼
 tableau/data_sources/*.csv  ◄──── analytics/export_tableau.py          Tableau live connection to ANALYTICS schema
 app/streamlit_app.py (optional preview)                                alerts: analytics/alerts.py (Slack/e-mail)
```

| Layer | Folder | Notes |
|---|---|---|
| Simulation | `simulator/` | 12-container fleet, 6 scenarios, seeded |
| Cleaning/validation | `ingestion/` | required cols, UTC timestamps, sentinels, ranges, de-dup, optional gap interpolation |
| Streaming | `streaming/` (renamed from `kafka/` so it never shadows the `kafka` library) | producer, consumer, sinks, DLQ, benchmark, docker-compose |
| Warehouse | `snowflake/sql/` | setup, raw DDL, analysis queries, clustering/MV/task |
| Transform | `dbt_project/` | 6 staging, 3 intermediate, 7 marts, 35 tests |
| Analytics | `analytics/` | pandas reference engine, alerts, Tableau export |
| BI | `tableau/` | data sources, calculated fields, build guide |
| UI (optional) | `app/` | Streamlit |

**Why DuckDB locally?** It lets the *identical* dbt models run and be tested without cloud credentials. SQL is kept ANSI-portable; only JSON parsing differs and is isolated in `dbt_project/macros/helpers.sql` (`json_val`).
**Kafka design:** key = `container_id` (per-container ordering), 3 partitions, JSON values, invalid events go to the `.dlq` topic, manual commits after the sink succeeds (at-least-once; duplicates are removed by staging).
