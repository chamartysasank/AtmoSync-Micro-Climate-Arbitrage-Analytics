# Feature 4 — Route Comparison Engine (Batch 04)
**Depends on:** Batch 01 (navigation, config merge). Uses Phase 1 `analytics/engine.py` (`latest_market_prices`), `analytics/geo.py`, cost assumptions in `settings.yaml → arbitrage`.

**What it does.** For every container it compares *destination market × route profile* options from the container's current position and recommends keeping or changing the route, with an explanation.

**Data.** `data/sample/route_profiles.csv` — four **SAMPLE / ILLUSTRATIVE** profiles (DIRECT, EXPRESS, SOUTHERN_ALT, NORTHERN_ALT) with distance multiplier, speed, cost multiplier, ambient-exposure index and vibration index. No real routing data was available; replace the CSV with real profiles when you have them.

**How it works** (`analytics/routes.py`)
- Distance = great-circle × road factor × profile multiplier; travel time = distance ÷ profile speed.
- **Environmental exposure:** effective burn rate = current burn rate × (1 + 0.30 × (exposure index − 0.5)) — an illustrative assumption (a warmer corridor ages the fruit faster).
- Remaining life at arrival → quality multiplier (same formula as Phase 1) minus a small vibration haircut above the baseline vibration index.
- Net value = price × kg × quality − transport (× profile cost multiplier) − handling − reroute fee (if the market differs from the original).
- **Rerouting cost** = fee + (transport − baseline transport). **Benefit** = net value − baseline net value, where baseline = original destination on DIRECT. DIRECT reproduces Phase 1 arbitrage numbers exactly (unit-tested).
- **Recommendation rule:** change only if the *current* route would arrive with less than the required shelf life **and** the best option beats the baseline by ≥ max($500, 3 %). Options that arrive "fresh enough" are preferred; if none does, the least-bad option is chosen and the explanation says so. A higher price alone never triggers a change.

**Configure:** `config/features/routes.yaml` (baseline profile, exposure sensitivity, vibration haircut). **Run:** `python -m analytics.routes`; UI **Route Intelligence** (profile filter, per-container explanation, ranked options, CSV).
**Example (sample):** CNT-009 → `Switch to DENVER via EXPRESS: arrives in 6.3 h with 55 h of shelf life (degraded) versus -48 h on the current route (spoiled) ... No option arrives fresh enough; this is the least-bad choice.` The other 11 containers: keep current route.
**Tests:** `tests/test_routes.py` (parity with Phase 1, burn-rate ordering, cost components, degradation rule, preference for fresh options).
**Limitations:** corridor exposure and vibration effects are illustrative assumptions; no live traffic, weather, tolls or driver-hours; straight-line distance × factor, not routed distance.
