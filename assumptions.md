# Facts vs assumptions

| Item | Value | Status |
|---|---|---|
| Mature-green Hass optimum 5–13 °C | thresholds.temp_* | **Cited fact** (UC Davis) |
| Hass best near 7.2 °C, 2–4 weeks in air | reference_temp_c, base life | **Cited fact** (WFLO) |
| RH 85–95 % | thresholds.rh_* | Cited range union (WFLO 85–90, Blue Book 90–95); upper bound 95 is an assumption |
| Deterioration 2–3× per +10 °C | q10 = 2.5 | Cited range (general produce); point value = assumption |
| Humidity penalty k | 0.25 | **Assumption** (qualitative support only: water loss rises as RH falls) |
| Required retail shelf life | 72 h | **Assumption** |
| Pre-loading life consumed (sim.) | 3–76 % by scenario | **Assumption**; chosen so the demo contains at-risk shipments |
| Fault patterns (drift, compressor failure, door-open) | simulator | **Illustrative** |
| Truck speed / road factor | 70 km/h / 1.25 | **Assumption** |
| Transport, handling, reroute fee, salvage 10 % | arbitrage.* | **Assumption** |
| Coordinates | locations.csv | Approximate |
| Simulated prices | market_prices.csv | **Simulated**, not market data |

**Needs mentor approval:** (1) Tableau instead of Apache Superset, (2) the heuristic model/weights, (3) the cost assumptions, (4) use of simulated prices if real wholesale data is required.
