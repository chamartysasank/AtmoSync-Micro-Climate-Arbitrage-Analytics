# Feature 3 — Spoilage Risk Forecasting (Batch 03)
**Depends on:** Batch 01 (navigation + config merge). Reuses Phase 1 engine (`analytics/engine.py`).

> **HEURISTIC ESTIMATE.** The forecast extrapolates recent sensor trends through the project's shelf-life budget model. It is **not** a scientifically validated spoilage prediction and was not trained or validated on measured avocado spoilage data.

**What it does.** Forecasts the risk score and category of every container at **+6, +12, +24 and +48 h** under three what-if scenarios: `hold` (conditions stay as now), `trend` (recent trend continues, damped) and `pessimistic` (trend + one std-dev worse variability).

**How it works** (`analytics/forecast.py::forecast_risk`)
1. Current level = mean of the last 4 readings; slope = linear fit over the last 6 h (temperature and humidity).
2. Projected conditions per hour = level + damped slope × hours (±σ shift for `pessimistic`), clipped to configured bounds.
3. Projected conditions → burn rate with the **existing** Q10 formula (`engine.burn_rate_at`) → cumulative shelf-life consumption (trapezoid, 1 h steps).
4. At each horizon the **existing** risk score/category rules are re-applied (`engine.risk_score`, `engine.risk_category`) with remaining transit time reduced by the horizon.
5. Extra outputs: `below_quality_threshold`, `hours_until_threshold` (first hour remaining life ≤ required retail shelf life), `evidence_level`.

**Modified existing file:** `analytics/engine.py` — the scoring arithmetic inside `container_status` was extracted into `risk_score()`, `risk_category()` and `burn_rate_at()` (behaviour unchanged; Phase 1 tests and the dbt↔pandas parity tests still pass).
**Configure:** `config/features/forecast.yaml` (horizons, trend window, damping, scenarios, bounds) and the existing `quality_model` / `risk` blocks.
**Run:** `python -m analytics.forecast`; UI **Risk Forecasting** (scenario selector, category filter, charts, assumptions table, CSV).
**Example (shipped sample, `trend` scenario):** CNT-001…006,012 stay LOW at all horizons; CNT-009 is CRITICAL from +6 h; CNT-007 HIGH at +6 h → CRITICAL at +12 h; CNT-010 drifts LOW → HIGH by +48 h (humidity decline).
**Tests:** `tests/test_forecast.py` — analytic check (constant reference conditions consume exactly h/504 of life), scenario ordering, clipping, humidity trend, threshold crossing, fallbacks, helper equivalence.
**Limitations:** linear extrapolation cannot anticipate repairs, door openings or weather; scenarios are what-ifs, not probabilities; no uncertainty intervals are claimed; accuracy is unvalidated.
