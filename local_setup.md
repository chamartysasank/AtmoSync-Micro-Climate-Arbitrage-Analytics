# Local setup (Mode A) — Windows / macOS / Linux, Python 3.10+

```powershell
cd AtmoSync
python -m venv .venv ; .\.venv\Scripts\Activate.ps1        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

python scripts/generate_sample_data.py     # (re)creates data/sample/*.csv  (SIMULATED)
python run_local.py                        # clean -> analytics -> DuckDB -> dbt build -> Tableau CSVs -> dry-run alerts
python -m pytest -q                        # 39 tests
streamlit run app/streamlit_app.py         # optional preview UI
```
Run pieces separately:
```powershell
python -m ingestion.local_warehouse                         # load raw tables into data/processed/atmosync.duckdb
cd dbt_project ; dbt build --profiles-dir . --target duckdb ; dbt docs generate --profiles-dir . ; dbt docs serve --profiles-dir .
cd .. ; python -m analytics.export_tableau                  # refresh tableau/data_sources/*.csv
```
Using real avocado prices: download via `python scripts/download_datasets.py`, then
`from ingestion.hab_prices import load_hab_avocado; load_hab_avocado("data/raw/avocado.csv").to_csv("data/sample/market_prices.csv", index=False)`.
(Check the CSV's real column/region names first.)
