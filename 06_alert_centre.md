# Feature 6 — Alert Management Centre (Batch 06)
**Depends on:** Batches 01–03 (anomalies, health, forecast), Phase 1 risk/arbitrage results, `common/store.py` (Batch 02). Batch 07 can add data-quality alerts through the `extra=` hook.

**What it does.** Generates WARNING / CRITICAL alerts, stores them locally with timestamps and categories, tracks acknowledgement and resolution, keeps a full history, and lets you filter by shipment, container, date, severity, status and category.

**Generation rules** (`analytics/alert_center.py::collect_candidates`, all configurable in `config/features/alerts.yaml → alert_center`)
| Category | WARNING when | CRITICAL when |
|---|---|---|
| risk (Phase 1) | category HIGH | category CRITICAL |
| health (Feature 2) | score < 60 | score < 40 |
| anomaly (Feature 1) | ≥ 5 flagged readings in the last 12 h | ≥ 3 CRITICAL readings in the last 12 h |
| forecast (Feature 3, heuristic) | quality threshold expected within 48 h | within 12 h |
| arbitrage (Phase 1) | REROUTE recommended | — |

**Lifecycle.** One active alert per (container, category): re-detection updates it (`occurrences`++); a higher severity **escalates** and re-opens acknowledgement; re-detection after RESOLVED **re-opens**; a condition that disappears is marked `condition_active = false` (still needs a human resolution). OPEN → ACKNOWLEDGED → RESOLVED (resolve also allowed from OPEN). Every step is written to `ops.alert_events`.
**Persistence:** local DuckDB `data/processed/atmosync.duckdb`, schema `ops` (`alerts`, `alert_events`). `event_time` = data time of the detection; `created_at` = wall-clock record time.
**Run:** `python -m analytics.alert_center --sync` then `--list`; UI **Alert Centre** (sync button, KPIs, filters, acknowledge/resolve with actor + note, per-alert history, CSV). The Phase 1 Slack/e-mail module `analytics/alerts.py` is unchanged and independent.
**Example (shipped sample, first sync):** 13 alerts — e.g. `CNT-009 risk CRITICAL`, `CNT-009 health CRITICAL (39/100)`, `CNT-009 forecast CRITICAL: threshold in ~3 h (heuristic)`, `CNT-007 risk WARNING`; second sync: 0 created / 13 updated.
**Tests:** `tests/test_alert_center.py` (12 tests: lifecycle, escalation, reopen, cleared conditions, filters, configurability, sample generation).
**Limitations:** single-user local store (no authentication — `actor` is free text); DuckDB allows one writer at a time; notifications (Slack/e-mail) are not wired to the centre; forecast alerts inherit the forecast's lack of validation.
