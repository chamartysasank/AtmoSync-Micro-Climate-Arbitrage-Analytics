# Methodology — transparent heuristics (NOT a validated spoilage model)

There is no validated, public spoilage-prediction model for Hass avocados in transit that we could verify. AtmoSync therefore uses a **shelf-life budget** heuristic whose every parameter lives in `config/settings.yaml` and is tagged SOURCE or ASSUMPTION.

## 1. Burn rate per reading
```
T_eff = max(T, chill_floor)                      # cold below 5 °C earns no extra life (chilling injury risk instead)
rate  = q10 ^ ((T_eff − T_ref)/10) × (1 + k × max(0, RH_min − RH)/10)
```
* T_ref = 7 °C (WFLO), q10 = 2.5 (UC ANR says 2–3×/10 °C; midpoint), RH_min = 85 %, k = 0.25 (**assumption**).
* rate = 1 means "ageing at the reference speed".

## 2. Life consumed
`consumed = pre_loading_consumed + Σ(dt_hours × rate) / (base_shelf_life_days × 24)`, with dt capped at 1 h per reading gap (comms blackouts are not credited as safe or unsafe time). Base life = 21 days (midpoint of WFLO's 2–4 weeks).

## 3. Quality window and slack
```
remaining_life_h = base_life_h × (1 − consumed)
window_h         = max(remaining_life_h − required_retail_shelf_h, 0) / recent_rate      # recent = last 60 min
slack_h          = window_h − hours_to_destination          # hours_to_destination = road km / 70 km/h
```
`required_retail_shelf_h` = 72 h is an **assumption** (shelf life buyers expect on arrival).

## 4. Risk score (0–100, for ranking) and category (rule-based)
score = 100 × (0.25·burn + 0.50·margin + 0.15·excursion_share + 0.10·consumed), each component clipped to 0–1.
Category: **CRITICAL** slack ≤ 0 · **HIGH** slack < 24 h · **MEDIUM** score ≥ 30 · else **LOW**. Weights are assumptions. Vibration is recorded and shown but **not** used in the score (no verified avocado dose-response was found).

## 5. Spoilage arbitrage
For each container and each market with a price:
```
remaining_at_arrival = remaining_life_h − transit_h × recent_rate
quality_multiplier   = salvage + (1 − salvage) × clip(remaining_at_arrival / required_shelf_h, 0, 1)
net_value            = price × kg × quality_multiplier − transport − handling − reroute_fee(if not original)
benefit              = net_value(alt) − net_value(original)
```
**REROUTE only if** benefit ≥ max($500, 3 % of original net) **and** the original route's quality multiplier < 1.
A higher price alone never triggers a reroute (tested in `tests/test_engine.py`). Costs ($0.10/t-km, $0.03/kg, $250 fee) are assumptions.

## 6. Where the same logic lives
Python reference: `analytics/engine.py`. SQL: `dbt_project/models/intermediate/*`, `marts/*`. `tests/test_dbt_parity.py` asserts both give identical results; `tests/test_alerts_config.py` asserts dbt vars equal `settings.yaml`.
