# ATMOSYNC — MICRO-CLIMATE ARBITRAGE CONTROL CENTER (Tableau build guide)

> **No Tableau workbook is included.** Tableau Desktop is not available in the build environment, so a .twb/.twbx was **not generated or tested**. This guide + the CSVs let you build it in ~1–2 hours. Tableau Public or Desktop both work with CSVs; the live Snowflake connection needs Desktop/Cloud.
> **Mentor approval required**: the original project specifies Apache Superset (see `docs/setup/superset_alternative.md`).

## 0. Data sources (`tableau/data_sources/`, produced by `python run_local.py`)
| File | Grain | Used for |
|---|---|---|
| executive_kpis.csv | 1 row | KPI tiles |
| container_health.csv | container | status, map, risk |
| shipment_risk.csv | shipment | ranking |
| sensor_readings.csv | reading (15 min) | trend lines, excursions |
| sensor_hourly.csv | container-hour | light-weight trends |
| arbitrage_options.csv | container × market | alternatives comparison |
| arbitrage_recommendations.csv | container | suggested actions |
| market_prices.csv | market-day | price trends |
| locations.csv | location | map |
**Relationships** (Data ▸ Relationships): container_health `container_id` ↔ sensor_readings, sensor_hourly, arbitrage_options, arbitrage_recommendations, shipment_risk; arbitrage_options `market_id` ↔ locations `location_id` ↔ market_prices `market_id`. Keep executive_kpis separate.
**Snowflake (Mode B):** Connect ▸ Snowflake ▸ server `<account>.snowflakecomputing.com`, warehouse ATMOSYNC_WH, role ATMOSYNC_VIEWER, schema ANALYTICS; tables `MART_*` have the same columns (upper-case). Use a live connection or extract.
Create the calculated fields in `calculated_fields/calculated_fields.md` first.

## A. Executive Overview (dashboard `1 Executive`)
1. Six BANs from executive_kpis: total_containers, healthy_containers, at_risk_containers, critical_alerts, arbitrage_opportunities, estimated_benefit_usd (format `$#,##0`).
2. Bar: container_id (rows) × risk_score (columns), colour = risk_category (CRITICAL dark red, HIGH orange, MEDIUM yellow, LOW green).
3. Map: container_health `last_longitude`/`last_latitude`, size = quantity_kg, colour = risk_category; add destination markers from locations (dual axis).
4. Action: click a container → filters all other dashboards (Dashboard ▸ Actions ▸ Filter, Select).

## B. Container Monitoring (`2 Containers`)
* Line: reading_ts (continuous) × temperature_c, colour = container_id; reference band 5–13 °C (Analytics ▸ Reference Band, constants 5 and 13).
* Line: humidity_pct with band 85–95. Line: vibration_g.
* Small multiples: container_id on Rows, temperature_c as the line.
* Excursions: bar of `Excursion %` by container; colour = `Temp Out Of Range` on a scatter of temperature vs time.
* Filters: container_id (multi), reading_ts (range), risk_category. Tooltip: container, time, temp, RH, burn_rate.

## C. Shipment Risk Analysis (`3 Shipments`)
* Table sorted by risk_rank: shipment_id, origin_id, planned_destination_id, risk_category, quality_window_hours, hours_to_destination, slack_hours (colour = `Quality Window Status`).
* Bar of count of containers by risk_category; bullet/dumbbell: quality_window_hours vs hours_to_destination per shipment.
* Drill-down: click a shipment → container line charts from dashboard B (Go to Sheet / Filter action).

## D. Market Intelligence (`4 Markets`)
* Lines: market_prices price_date × price_modal_usd_kg, colour = market_id; add `modal_7d_avg` as a second measure.
* Bar: latest-day price by market (filter price_date = {FIXED : MAX(price_date)} — create `Latest Day` calc: `[price_date] = {MAX([price_date])}`).
* Heat map: market_id × week of price_date, colour = premium_vs_all_markets.
* Alternatives: from arbitrage_options for a selected container: bar of distance_km and price by market_id.

## E. Arbitrage Analysis (`5 Arbitrage`)
* Table (arbitrage_recommendations): container, risk_category, original_destination, best_alternative, `Suggested Action Label`, best_benefit_usd; filter by parameter Min Benefit.
* Waterfall-style bars for a selected container (arbitrage_options): expected_gross_value_usd → minus `Value Lost To Quality` → minus transport_cost_usd → minus handling_cost_usd → minus reroute_fee_usd = net_value_usd (Measure Names/Values).
* Bar: `Reroute Benefit (only REROUTE rows)` by container; text label in USD.
* Notes box: "REROUTE requires quality-adjusted benefit ≥ threshold AND degrading original route. Heuristic model — see docs/methodology."

## Theme & polish
Dark navy header, font Tableau Book/Segoe UI, risk palette above, title "ATMOSYNC — MICRO-CLIMATE ARBITRAGE CONTROL CENTER", add a navigation row of buttons (Dashboard ▸ Objects ▸ Navigation). Add a footer text: "Sample data is SIMULATED".
## Verification checklist
After building, compare: KPI tiles vs `executive_kpis.csv` (expected from the shipped sample: 12 / 9 / 3 / 1 / 1 / $56,685); CNT-009 should be CRITICAL with REROUTE CHICAGO→DENVER.
Save as `.twbx` (File ▸ Save As ▸ Packaged Workbook) and put it in `tableau/dashboard_assets/`; add screenshots there too.
