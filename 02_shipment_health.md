# Feature 2 — Shipment Health Scoring (Batch 02)
**Depends on:** Batch 01 (navigation scaffold `app/views/`, `config/features/` merge in `common/config.py`).

**What it does.** Scores each shipment/container 0–100 for how well its *recent conditions* matched the target ranges and classifies it **Healthy ≥ 80 · Warning ≥ 60 · At Risk ≥ 40 · Critical < 40** (thresholds configurable). History is stored hourly in the local DuckDB database.

**How it works** (`analytics/health.py`)
1. Per reading, a penalty 0–1 for temperature (distance outside 5–13 °C ÷ 8 °C), humidity (distance outside 85–95 % ÷ 25 %) and vibration ((g − 0.6) ÷ 0.9).
2. Sub-score = 100 × (1 − mean penalty over the trailing 6 h). Health = weighted mean (temperature 0.5, humidity 0.3, vibration 0.2; missing variables are re-normalised).
3. **Failure cap:** if any sub-score ≤ 15 the total is capped at 39, so one failing variable cannot be averaged away.
4. Every row carries `main_driver` and a plain-English `explanation`.
Health is a *condition* score; the Phase 1 **risk** score looks forward (shelf life vs time to destination). The two can disagree (e.g. a slowly drifting container may still be "Healthy" while its risk is HIGH).

**Existing modules used:** `analytics/pipeline.py` readings (`add_reading_rates` output), `thresholds:` in `settings.yaml`.
**New shared module:** `common/store.py` — small DuckDB helper (schema `ops`, upsert/append/read, automatic column addition) reused by later batches (alerts, quality reports, pipeline logs).
**Configure:** `config/features/health.yaml`.
**Run:** `python -m analytics.health` (computes and persists `ops.health_history` in `data/processed/atmosync.duckdb`); UI: **Shipment Health** (category filter, date range, trend chart, save-snapshot button, CSV download).
**Example (shipped sample):** CNT-009 → `Health 39 (Critical) ... Main driver: temperature. Score capped at 39 because one variable is at or below 15/100.`; 11 other containers Healthy.
**Tests:** `tests/test_health_store.py` (scoring, caps, weights, boundaries, history idempotency, store behaviour).
**Limitations:** weights and penalty scales are assumptions; the score does not model chilling injury or ripening; vibration affects the score although no verified avocado dose-response was found — set its weight to 0 if your mentor prefers.
