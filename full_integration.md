# Full integration (Mode B): Python → Kafka → Snowflake → dbt → Tableau
> Everything here is **written but UNTESTED** against live services (no Kafka broker, Snowflake account or Tableau in the build environment).

## 1. Kafka (Docker Desktop required)
```powershell
pip install confluent-kafka
docker compose -f streaming/docker-compose.yml up -d
docker exec atmosync-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --topic atmosync.sensor.events --partitions 3 --replication-factor 1
docker exec atmosync-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --topic atmosync.sensor.events.dlq --partitions 1 --replication-factor 1
python -m streaming.consumer --sink duckdb       # terminal 1  (use --sink snowflake later)
python -m streaming.producer --speedup 600       # terminal 2  (replays the sample at 600x)
python -m streaming.benchmark --events 100000    # records events/s for the mid-project review
```
If Docker is unavailable: skip Kafka, use `ingestion/replay.py` straight into `streaming/sinks.py` (documented fallback; it demonstrates the pipeline but **not** Kafka throughput).

**Dead-letter handling:** the consumer subscribes ONLY to `atmosync.sensor.events`. Rejected messages (bad JSON or failed validation) are forwarded to `atmosync.sensor.events.dlq` as `{source_topic, problems, rejected_at, original_payload | original_payload_b64}`; the DLQ is flushed before offsets are committed (at-least-once), and a DLQ delivery failure aborts the batch without committing. Inspect with `kafka-console-consumer.sh --topic atmosync.sensor.events.dlq --from-beginning`. Never point the main consumer at the DLQ (config check raises if both topics are equal). Live-broker behaviour remains untested.

## 2. Snowflake (free trial works)
1. Run `snowflake/sql/01_setup.sql`, `02_raw_tables.sql` in a worksheet (grant roles to your user).
2. Copy `.env.example` → `.env`, fill `SNOWFLAKE_*` (never commit it). `pip install snowflake-connector-python dbt-snowflake`.
3. `python scripts/load_snowflake.py` (dimension tables + sample events) **or** `python -m streaming.consumer --sink snowflake`.

## 3. dbt on Snowflake
```powershell
cd dbt_project
dbt debug --profiles-dir . --target snowflake
dbt build --profiles-dir . --target snowflake
```
Schedule: Windows Task Scheduler / cron running `dbt build --target snowflake` every 15 min (dbt Core has no built-in scheduler). Week-4 clustering/MV/task examples: `snowflake/sql/04_performance_and_automation.sql`.
Possible Snowflake-only issues to check on first run: `to_timestamp_ntz` parsing in `macros/helpers.sql`, clustering config, `date_trunc` types.

## 4. Alerts
`alerts.dry_run: true` in `config/settings.yaml` only logs. Set false and export `SLACK_WEBHOOK_URL` (+ `pip install requests`) and/or `SMTP_*`.

## 5. Tableau → see `tableau/dashboard_guide.md` (Snowflake connector or the CSVs).
