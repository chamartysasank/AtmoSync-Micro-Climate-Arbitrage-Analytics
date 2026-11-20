# Feature 5 — Agricultural Market Price Intelligence (Batch 05)
**Depends on:** Batch 01 (navigation, config merge). Uses Phase 1 `market_prices.csv`, `locations.csv`, `analytics/geo.py`, cost assumptions (`settings.yaml → arbitrage`) and the optional `ingestion/hab_prices.py` adapter.

**What it does.** Loads one or more price datasets **with an explicit type label** (SIMULATED, HISTORICAL_DERIVED …), compares markets, analyses trends (7/30-day change, 7-day average, volatility, slope, Rising/Falling/Stable) and estimates **gross and net market-to-market margins** after transport and handling.

**Datasets** (`config/features/market.yaml → datasets`)
| id | type | status |
|---|---|---|
| `sample_simulated` | SIMULATED | shipped (`data/sample/market_prices.csv`, 810 rows, 9 markets, 90 days) |
| `hab_derived` | HISTORICAL_DERIVED | **optional, not shipped** — create with `load_hab_avocado("data/raw/avocado.csv").to_csv("data/processed/market_prices_hab.csv", index=False)` after downloading the Hass Avocado Board data (retail price per fruit converted to wholesale USD/kg with *assumed* factors) |
`simulate_price_series()` generates reproducible what-if series (always labelled `SIMULATED (scenario)`). Add more datasets by appending entries to the YAML.

**How margins work** (`analytics/market.py::arbitrage_margins`): buy market A, sell market B on the same date: gross = pB − pA; net = gross − distance(A→B)/1000 × $/t-km − handling; totals = per-kg × quantity. This is a *price-difference* view; spoilage-driven rerouting remains in the Phase 1 engine and Batch 04.
**Run:** `python -m analytics.market`; UI **Market Analytics** (dataset selector with type banner, market + date filters, trend table, comparison, margin table with quantity input, margin history chart, dataset catalog).
**Example (simulated sample, 2026-11-10):** top margin HOUSTON → NEW_YORK: gross $1.11/kg, net $0.79/kg (24 %), $15,898 for 20 t — *simulated numbers*.
**Tests:** `tests/test_market.py` (loading/labels/optional datasets, validation, trend labels, margin arithmetic, cost-defeats-small-gap, history, simulation reproducibility).
**Limitations:** no real wholesale series is bundled; HAB retail→wholesale conversion is an assumption; margins ignore spoilage, FX, tariffs, price impact of volume and market access.
