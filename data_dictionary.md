# Data dictionary

## raw_sensor_events (CSV / Kafka message)
| Column | Type | Description |
|---|---|---|
| event_id | text | `container|sensor|timestamp`; used for duplicate detection |
| container_id, sensor_id, shipment_id | text | identifiers |
| reading_ts | ISO-8601 UTC text | reading time |
| temperature_c | float | air temperature, °C (`-999` = sensor error sentinel) |
| humidity_pct | float | relative humidity, % |
| vibration_g | float | vibration magnitude in g (illustrative; not used in scoring) |
| latitude, longitude | float | GPS position (extra field added by the simulator) |
| source | text | SIMULATED |
Snowflake/DuckDB RAW table: `(event_id, event_ts, payload VARIANT/JSON, source, ingested_at)`.

## Dimension tables
* **shipments**: shipment_id, container_id, commodity_id, quantity_kg, origin_id, planned_destination_id, departure_ts, planned_arrival_ts, route_km, pre_loading_life_consumed (assumption, 0–1), data_origin.
* **containers**: container_id, sensor_id, container_type, setpoint_temp_c. **commodities**: storage ranges + base_shelf_life_days. **locations**: location_id, name, latitude, longitude, is_market, location_type.
* **market_prices**: price_date, market_id, commodity_id, price_min/max/modal_usd_kg, data_origin.

## Marts (dbt ANALYTICS schema == Tableau CSVs)
| Model | Grain | Key columns |
|---|---|---|
| mart_container_health | container | life_consumed_fraction, recent_burn_rate, remaining_life_hours, quality_window_hours, hours_to_destination, slack_hours, risk_score (0–100), risk_category, excursion counts, last position |
| mart_shipment_risk | shipment | risk_rank + above |
| mart_sensor_hourly | container-hour | avg/max temp, avg RH, avg vibration, excursion_readings |
| mart_market_comparison | market-day | modal_7d_avg, premium_vs_all_markets, price_rank |
| mart_arbitrage_options | container × market | distance_km, transit_hours, remaining_life_at_arrival_h, quality_multiplier, costs, net_value_usd, benefit_vs_original_usd |
| mart_arbitrage_recommendations | container | best_alternative, best_benefit_usd, benefit_threshold_usd, recommended_action (REROUTE / MONITOR / NO_ACTION) |
| mart_executive_kpis | 1 row | total/healthy/at-risk containers, critical_alerts, arbitrage_opportunities, estimated_benefit_usd |
