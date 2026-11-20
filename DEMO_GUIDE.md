# Demonstration guide (≈10 minutes)

**Setup (once):** `pip install -r requirements.txt` → `python run_local.py --report` (≈30 s; runs the pipeline, dbt build on DuckDB, Tableau CSVs, Phase 2 persistence and the example report) → `streamlit run app/streamlit_app.py`.
> Say up front: *all data is simulated; scores and forecasts are heuristics, not validated predictions; Tableau is the primary dashboard (needs mentor approval vs Superset).*

| Step | Page | What to show | What you should see (sample data) |
|---|---|---|---|
| 1 | Overview | KPI tiles, risk table | 12 containers · 9 healthy · 3 at risk · 1 critical · 1 reroute ($56,685) |
| 2 | Shipment Monitoring | select CNT-009 and CNT-001 | CNT-009 temperature climbs far above the 5–13 °C band |
| 3 | Anomaly Detection | filter Severity = CRITICAL | 46 critical flags, CNT-009 worst; read one `reason` text |
| 4 | Shipment Health | table + trend | CNT-009 Critical (39, capped); explain the failure cap |
| 5 | Risk Forecasting | scenario `trend`, then `pessimistic` | CNT-009 CRITICAL from +6 h; CNT-007 HIGH → CRITICAL by +12 h; point at the **HEURISTIC** banner and assumptions table |
| 6 | Route Intelligence | CNT-009 detail | switch to DENVER via EXPRESS; "least-bad choice" explanation; healthy containers: keep route |
| 7 | Market Analytics | dataset banner, Arbitrage margins tab | `SIMULATED` banner; HOUSTON→NEW_YORK net ≈ $0.79/kg |
| 8 | Alert Centre | click *Run detection and sync alerts* → acknowledge → resolve an alert | 13 alerts; history shows CREATED → ACKNOWLEDGED → RESOLVED |
| 9 | Data Quality | scores and findings | overall ≈ 99; CNT-012 coverage 83 % (communication blackout) |
| 10 | Simulation Lab | `compressor_failure`, drag rate slider; Historical replay slider | normal LOW vs abnormal HIGH, health 100 → 39; replay shows risk growing over time |
| 11 | Reports | download PDF and CSV zip | labels on every page footer |
| 12 | System Monitoring | health tiles, last run steps | dbt_build SUCCESS; ingestion 819 → 804 |
**Tableau:** open `tableau/dashboard_guide.md` and the CSVs in `tableau/data_sources/` (workbook not included).
**Honest closing slide:** not tested against live Kafka/Snowflake/Tableau; real datasets not bundled; assumptions are in `docs/methodology/assumptions.md` and `docs/reference/configuration.md`.
