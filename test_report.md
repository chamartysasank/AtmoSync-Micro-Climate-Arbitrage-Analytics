# Test report (build environment: Linux, Python 3.12, pandas 3.0, DuckDB 2.0, dbt-core 1.12 + dbt-duckdb)

| Component | How tested | Result |
|---|---|---|
| Python imports / startup | `python run_local.py`, pytest | PASS |
| Simulator (12 containers, 6 scenarios, reproducible, fault injection toggle) | `tests/test_simulator_replay.py` | PASS |
| Cleaning (sentinels, ranges, bad timestamps, duplicates, missing columns) | `tests/test_cleaning.py`; sample: 819 in → 804 clean (8 duplicates, 7 rejected) | PASS |
| Historical replay | `tests/test_simulator_replay.py` (time-ordered, limit) | PASS |
| Analytics (burn rate, Q10, chill floor, humidity, gap cap, risk, REROUTE rule, KPIs) | `tests/test_engine.py` | PASS |
| Kafka **logic** (validation, consumer-side DLQ forwarding with original payload + reasons, no DLQ subscription, DLQ flush before offset commit, no commit if DLQ delivery fails) | `tests/test_streaming.py` with in-memory sinks and a fake `confluent_kafka` | PASS |
| `run_local.py` stops with exit code 1 and a clear error when `dbt build` fails or `dbt` is missing; no Tableau export/alerts afterwards | `tests/test_run_local.py` | PASS |
| Kafka **broker** integration | — | **NOT TESTED** (no broker) |
| dbt models on DuckDB | `dbt build --target duckdb`: 52/52 (7 tables, 10 views, 35 tests) | PASS |
| dbt ↔ pandas parity (risk, windows, recommendations, KPIs) | `tests/test_dbt_parity.py` | PASS |
| dbt vars ↔ settings.yaml | `tests/test_alerts_config.py` | PASS |
| Snowflake SQL / dbt-snowflake / SnowflakeSink | — | **NOT TESTED** (no account; SQL not engine-checked) |
| Alerts (message building, dry run) | `tests/test_alerts_config.py` | PASS; Slack/SMTP sending **NOT TESTED** |
| Tableau CSV export | `tests/test_app_and_exports.py` | PASS |
| Tableau workbook | — | **NOT CREATED / NOT TESTED** |
| Streamlit app | `streamlit.testing.AppTest` (renders, 6 metrics, no exception) | PASS (not viewed in a browser) |
| HAB price adapter | hand-made 3-row fixture only | PASS (logic only; real file not inspected) |

Total: 39 pytest tests passed. Clean-copy check: extracted project re-ran `run_local.py --regenerate` and pytest with identical KPI output.
