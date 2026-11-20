# Learning guide — explain AtmoSync in an interview

**30-second pitch:** "Reefer containers stream temperature/humidity/vibration. I ingest events with Kafka, land raw JSON in Snowflake, model it with dbt, and compute how fast each shipment is using up its shelf life. If a container will miss its quality window, the model compares the quality-adjusted net value of rerouting to nearby markets against the original destination and recommends an action. Tableau shows it."

| Topic | Where to read | Be ready to explain |
|---|---|---|
| Event simulation | `simulator/iot_simulator.py` | scenarios, seeding for reproducibility, why faults are injected |
| Data cleaning | `ingestion/cleaning.py`, `tests/test_cleaning.py` | sentinels, range checks, dedupe keys, why no imputation by default |
| Heuristic model | `docs/methodology/methodology.md`, `analytics/engine.py` | Q10 rule, shelf-life budget, why it is *not* a validated ML model |
| Kafka | `streaming/` | topics, partition key = container_id, DLQ, at-least-once + dedupe, consumer groups, offsets/commit |
| Snowflake | `snowflake/sql/` | VARIANT for JSON, warehouses, roles, clustering keys, materialized view limits |
| dbt | `dbt_project/` | sources/staging/intermediate/marts, `ref()`, tests, macros + `adapter.dispatch`, vars, why DuckDB locally |
| SQL concepts | `models/intermediate/*.sql`, `snowflake/sql/03_*.sql` | window functions (lag, row_number, rolling avg), joins, CTEs |
| Arbitrage | `mart_arbitrage_*.sql` | cost model, quality multiplier, "benefit AND degradation" rule |
| Tableau | `tableau/dashboard_guide.md` | relationships vs joins, calculated fields, actions, reference bands |

**Likely questions:** *Why is a higher price not enough to reroute?* (transport + fee + quality loss; test proves it.) *How do you know the thresholds are right?* (cited ranges; heuristics tagged ASSUMPTION; needs validation with real quality data.) *What is not tested?* (live Kafka/Snowflake/Tableau — see limitations.) *How would you scale?* (Snowpipe Streaming/Kafka connector, incremental dbt models, partition by time.)
**Practice:** change `q10` in `config/settings.yaml` **and** `dbt_project/dbt_project.yml`, rerun `python run_local.py`, watch which containers change category; the vars-sync test will fail if you change only one.
