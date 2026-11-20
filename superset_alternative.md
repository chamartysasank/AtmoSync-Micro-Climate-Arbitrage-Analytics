# Apache Superset alternative (the ORIGINAL project requirement)

The project PDF specifies **Apache Superset**. This build uses **Tableau** as requested; **replacing Superset needs mentor approval**, and Tableau does not by itself satisfy the original Superset wording. If approval is refused, use this path (same data, same marts):

1. Install: `pip install apache-superset` is fragile on Windows → use Docker: follow the official Superset "Docker Compose" quick-start (check the current docs), create an admin user.
2. Add a database: **Snowflake** (`pip install snowflake-sqlalchemy` in the Superset image; URI `snowflake://USER:PASS@ACCOUNT/ATMOSYNC/ANALYTICS?warehouse=ATMOSYNC_WH&role=ATMOSYNC_VIEWER`) or, locally, **DuckDB** (`duckdb-engine`; URI `duckdb:////path/to/data/processed/atmosync.duckdb`).
3. Add datasets: `mart_container_health`, `mart_shipment_risk`, `mart_sensor_hourly`, `mart_market_comparison`, `mart_arbitrage_options`, `mart_arbitrage_recommendations`, `mart_executive_kpis`.
4. Charts (map from the Tableau views): Big Number ×6 from `mart_executive_kpis`; Time-series line of `avg_temp_c` by `container_id` from `mart_sensor_hourly`; Table of `mart_shipment_risk` ordered by `risk_rank`; Bar of `best_benefit_usd` by container from `mart_arbitrage_recommendations`; Line of `price_modal_usd_kg` by `market_id`.
5. Roles (week 1): create a read-only `Gamma`-based role limited to those datasets. Alerts & Reports (week 4) need Superset's alerts feature + SMTP/Slack config.
Status: **instructions only, not built or tested.**
