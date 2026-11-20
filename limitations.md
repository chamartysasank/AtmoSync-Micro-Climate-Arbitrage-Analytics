# Limitations and honesty notes

**Tested in the build environment (Linux sandbox):** Python imports, simulator, cleaning, replay, analytics, DuckDB loader, dbt build on **dbt-duckdb** (52/52 passing), dbt-vs-pandas parity, Kafka *message processing logic* with mocks, JSONL/DuckDB sinks, alert text generation (dry-run), Tableau CSV export, Streamlit app startup (Streamlit AppTest). 39 pytest tests pass.

**NOT tested (no access):**
* A live Kafka broker (producer/consumer/benchmark/docker-compose are untested; no throughput numbers exist).
* Snowflake (SQL scripts, `SnowflakeSink`, `load_snowflake.py`, dbt-snowflake, clustering, MV, task). Snowflake SQL was not syntax-checked by an engine; the dbt models were only executed on DuckDB.
* Tableau: **no .twb/.twbx exists**. Only data sources, calculated fields and a build guide are provided.
* Slack/e-mail sending, Superset, Windows-specific behaviour (commands are standard, but run them once and report issues).
* Real datasets: not downloadable here; row counts/columns come from dataset pages and papers.

**Scientific limits:** the quality model is a heuristic; shelf-life consumption is not a validated predictor of avocado ripeness/spoilage; avocado quality also depends on maturity, ethylene, atmosphere and chilling injury (not modelled). Vibration is not used in scoring. Fault patterns and prices are simulated.
**Data limits:** the sample is 12 containers over ≈40 h; the demo fleet is deliberately constructed so some shipments are at risk, so KPI values are **demonstration values, not findings**.
**Streaming limits:** `SnowflakeSink` inserts row-by-row (demo scale). Production volume needs the Snowflake Kafka connector / Snowpipe Streaming.
