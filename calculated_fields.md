# Tableau calculated fields (paste into Analysis ▸ Create Calculated Field)
Field names in `[brackets]` are columns from the CSVs in `../data_sources/`.

**Risk Color Rank** (sort/colour helper)
```
CASE [risk_category] WHEN 'CRITICAL' THEN 4 WHEN 'HIGH' THEN 3 WHEN 'MEDIUM' THEN 2 ELSE 1 END
```
**Is At Risk**
```
[risk_category] != 'LOW'
```
**Excursion %**
```
SUM([excursion_readings]) / SUM([reading_count])
```
**Temp Out Of Range** (sensor_readings.csv)
```
IF [temperature_c] < 5 OR [temperature_c] > 13 THEN 'Out of range' ELSE 'In range' END
```
**Quality Window Status**
```
IF [slack_hours] <= 0 THEN 'Will miss quality window'
ELSEIF [slack_hours] < 24 THEN 'Tight (<24 h slack)'
ELSE 'Comfortable' END
```
**Net Benefit (USD)** (arbitrage_options.csv)
```
[net_value_usd] - [original_net_value_usd]
```
**Reroute Benefit (only REROUTE rows)** (arbitrage_recommendations.csv)
```
IF [recommended_action] = 'REROUTE' THEN [best_benefit_usd] END
```
**Value Lost To Quality (USD)**
```
[expected_gross_value_usd] - [expected_quality_adjusted_value_usd]
```
**Suggested Action Label**
```
IF [recommended_action] = 'REROUTE' THEN 'Reroute to ' + [best_alternative]
ELSEIF [recommended_action] = 'MONITOR' THEN 'Monitor closely'
ELSE 'No action' END
```
**Price vs 7-day avg**
```
[price_modal_usd_kg] - [modal_7d_avg]
```
Parameters: **Risk Filter** (string list: ALL, CRITICAL, HIGH, MEDIUM, LOW) and **Min Benefit (USD)** (integer, default 500, range 0–20000).
