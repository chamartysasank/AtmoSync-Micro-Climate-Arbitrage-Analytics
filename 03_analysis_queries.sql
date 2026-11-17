-- Hand-written analysis queries (run after `dbt build --target snowflake`). They demonstrate the SQL concepts
-- asked for in the brief: cleaning, aggregation, joins, window functions, monitoring, risk, market comparison.
USE ROLE ATMOSYNC_ROLE; USE WAREHOUSE ATMOSYNC_WH; USE SCHEMA ATMOSYNC.ANALYTICS;

-- 1. DATA CLEANING: how many raw events were dropped by staging, and why (parse payload directly from RAW).
SELECT COUNT(*) AS raw_events,
       COUNT_IF(PAYLOAD:temperature_c IS NULL OR PAYLOAD:temperature_c::FLOAT IN (-999, -9999)) AS bad_temperature,
       COUNT_IF(PAYLOAD:humidity_pct::FLOAT NOT BETWEEN 0 AND 100) AS bad_humidity,
       (SELECT COUNT(*) FROM STG_SENSOR_EVENTS) AS clean_events
FROM ATMOSYNC.RAW.RAW_SENSOR_EVENTS;

-- 2. AGGREGATION: per-container temperature statistics and excursion share.
SELECT container_id, COUNT(*) AS readings, ROUND(AVG(temperature_c),2) AS avg_temp_c, MAX(temperature_c) AS max_temp_c,
       ROUND(AVG(IFF(is_excursion,1,0)),3) AS excursion_share
FROM INT_READINGS_RATED GROUP BY container_id ORDER BY excursion_share DESC;

-- 3. JOIN: shipment risk with origin and destination names.
SELECT r.risk_rank, r.shipment_id, o.name AS origin, d.name AS destination, r.risk_category, ROUND(r.slack_hours,1) AS slack_h
FROM MART_SHIPMENT_RISK r
JOIN STG_LOCATIONS o ON o.location_id = r.origin_id
JOIN STG_LOCATIONS d ON d.location_id = r.planned_destination_id
ORDER BY r.risk_rank;

-- 4. WINDOW FUNCTION: temperature change vs previous reading and 1-hour rolling average (container monitoring).
SELECT container_id, reading_ts, temperature_c,
       temperature_c - LAG(temperature_c) OVER (PARTITION BY container_id ORDER BY reading_ts) AS delta_prev,
       AVG(temperature_c) OVER (PARTITION BY container_id ORDER BY reading_ts ROWS BETWEEN 3 PRECEDING AND CURRENT ROW) AS rolling_1h_avg
FROM STG_SENSOR_EVENTS QUALIFY ROW_NUMBER() OVER (PARTITION BY container_id ORDER BY reading_ts DESC) <= 8;

-- 5. MARKET COMPARISON: latest price rank and premium over the cross-market average.
SELECT market_id, price_date, price_modal_usd_kg, ROUND(premium_vs_all_markets,2) AS premium, price_rank
FROM MART_MARKET_COMPARISON QUALIFY price_date = MAX(price_date) OVER () ORDER BY price_rank;

-- 6. ARBITRAGE: top reroute opportunities.
SELECT container_id, original_destination, best_alternative, ROUND(best_benefit_usd) AS benefit_usd, recommended_action
FROM MART_ARBITRAGE_RECOMMENDATIONS WHERE recommended_action = 'REROUTE' ORDER BY best_benefit_usd DESC;
