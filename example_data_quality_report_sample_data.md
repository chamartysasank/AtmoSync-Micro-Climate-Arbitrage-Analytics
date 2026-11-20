# Data Quality Report

*Generated for data ending 2026-11-10 11:59:05 - rows analysed: 819*

**Overall score: 99.3/100 (GOOD)**

| Metric | Score |
|---|---|
| Completeness | 99.2 |
| Validity | 99.1 |
| Uniqueness | 99.0 |
| Timeliness | 100.0 |

## Issue counts

- Missing values: 4
- Invalid readings (sentinel / non-numeric / bad timestamp): 1
- Out-of-range values: 2
- Duplicate records: 8
- Rows rejected by cleaning: 7
- Missing expected readings (gaps): 12
- Stale containers: 0

## By field

| field         |   missing |   invalid |   out_of_range |   completeness_pct |   validity_pct |
|:--------------|----------:|----------:|---------------:|-------------------:|---------------:|
| event_id      |         0 |         0 |              0 |            100     |        100     |
| container_id  |         0 |         0 |              0 |            100     |        100     |
| sensor_id     |         0 |         0 |              0 |            100     |        100     |
| shipment_id   |         0 |         0 |              0 |            100     |        100     |
| reading_ts    |         0 |         0 |              0 |            100     |        100     |
| temperature_c |         4 |         1 |              0 |             99.512 |         99.878 |
| humidity_pct  |         0 |         0 |              2 |            100     |         99.756 |
| vibration_g   |         0 |         0 |              0 |            100     |        100     |

## By container

| container_id   |   rows |   expected_readings |   unique_readings |   coverage_pct |   rejected_rows |   duplicates |   completeness |   validity |   uniqueness | stale   | last_reading_ts     |   score |
|:---------------|-------:|--------------------:|------------------:|---------------:|----------------:|-------------:|---------------:|-----------:|-------------:|:--------|:--------------------|--------:|
| CNT-012        |     61 |                  72 |                60 |           83.3 |               4 |            1 |           91.3 |       93.4 |         98.4 | False   | 2026-11-10 11:57:03 |    93.7 |
| CNT-009        |     81 |                  80 |                80 |          100   |               3 |            1 |          100   |       96.3 |         98.8 | False   | 2026-11-10 11:51:17 |    98.4 |
| CNT-011        |     50 |                  48 |                48 |          100   |               0 |            2 |          100   |      100   |         96   | False   | 2026-11-10 11:45:46 |    99.6 |
| CNT-004        |     57 |                  56 |                56 |          100   |               0 |            1 |          100   |      100   |         98.2 | False   | 2026-11-10 11:49:21 |    99.8 |
| CNT-006        |     69 |                  68 |                68 |          100   |               0 |            1 |          100   |      100   |         98.6 | False   | 2026-11-10 11:51:58 |    99.9 |
| CNT-005        |     80 |                  79 |                79 |          100   |               0 |            1 |          100   |      100   |         98.8 | False   | 2026-11-10 11:52:24 |    99.9 |
| CNT-007        |    100 |                  99 |                99 |          100   |               0 |            1 |          100   |      100   |         99   | False   | 2026-11-10 11:58:01 |    99.9 |
| CNT-003        |     58 |                  58 |                58 |          100   |               0 |            0 |          100   |      100   |        100   | False   | 2026-11-10 11:51:55 |   100   |
| CNT-008        |     65 |                  65 |                65 |          100   |               0 |            0 |          100   |      100   |        100   | False   | 2026-11-10 11:58:51 |   100   |
| CNT-001        |     79 |                  79 |                79 |          100   |               0 |            0 |          100   |      100   |        100   | False   | 2026-11-10 11:55:16 |   100   |
| CNT-002        |     57 |                  57 |                57 |          100   |               0 |            0 |          100   |      100   |        100   | False   | 2026-11-10 11:59:05 |   100   |
| CNT-010        |     62 |                  62 |                62 |          100   |               0 |            0 |          100   |      100   |        100   | False   | 2026-11-10 11:50:00 |   100   |

## Findings

- **INFO** all: 8 duplicate records (1.0%) - removed by cleaning.
- **WARNING** all: 7 rows fail validation (0.9%).
- **WARNING** temperature_c: 4 missing values.
- **WARNING** temperature_c: 1 invalid readings (sentinel / non-numeric).
- **WARNING** humidity_pct: 2 values outside the plausible range [0, 100].
- **WARNING** CNT-012: reading coverage 83% (12 expected readings missing).
