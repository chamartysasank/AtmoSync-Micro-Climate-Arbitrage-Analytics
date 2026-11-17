-- Week-4 items. UNTESTED (no Snowflake account in the build environment). Materialized views need Enterprise edition+.
USE ROLE ATMOSYNC_ROLE; USE WAREHOUSE ATMOSYNC_WH;

-- 1. Clustering is already declared on RAW_SENSOR_EVENTS (02_raw_tables.sql) and via dbt `cluster_by` on staging/intermediate.
--    Inspect clustering quality with:
-- SELECT SYSTEM$CLUSTERING_INFORMATION('ATMOSYNC.RAW.RAW_SENSOR_EVENTS', '(TO_DATE(EVENT_TS), EVENT_ID)');

-- 2. Materialized view: hourly counts straight from the raw table (MVs allow one table + simple aggregates only,
--    so the heavy joins/window logic stays in dbt).
CREATE OR REPLACE MATERIALIZED VIEW ATMOSYNC.RAW.MV_EVENTS_PER_HOUR AS
SELECT DATE_TRUNC('hour', EVENT_TS) AS HOUR_TS, COUNT(*) AS EVENTS
FROM ATMOSYNC.RAW.RAW_SENSOR_EVENTS GROUP BY DATE_TRUNC('hour', EVENT_TS);

-- 3. Alert queue table + task (pure SQL). dbt Core itself is scheduled outside Snowflake (cron / Task Scheduler / GitHub-free runner).
CREATE TABLE IF NOT EXISTS ATMOSYNC.ANALYTICS.ALERT_QUEUE (created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    container_id VARCHAR, recommended_action VARCHAR, best_benefit_usd FLOAT, sent BOOLEAN DEFAULT FALSE);
CREATE OR REPLACE TASK ATMOSYNC.ANALYTICS.TASK_QUEUE_ALERTS WAREHOUSE = ATMOSYNC_WH SCHEDULE = '15 MINUTE' AS
INSERT INTO ATMOSYNC.ANALYTICS.ALERT_QUEUE (container_id, recommended_action, best_benefit_usd)
SELECT r.container_id, r.recommended_action, r.best_benefit_usd
FROM ATMOSYNC.ANALYTICS.MART_ARBITRAGE_RECOMMENDATIONS r
WHERE r.recommended_action = 'REROUTE'
  AND NOT EXISTS (SELECT 1 FROM ATMOSYNC.ANALYTICS.ALERT_QUEUE q WHERE q.container_id = r.container_id AND q.created_at > DATEADD('hour', -6, CURRENT_TIMESTAMP()));
-- ALTER TASK ATMOSYNC.ANALYTICS.TASK_QUEUE_ALERTS RESUME;   -- tasks are created suspended
