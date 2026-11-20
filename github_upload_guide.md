# Manual GitHub upload (information only — no git operations were performed)

## Upload these (repository root = the `AtmoSync/` folder contents)
```
README.md  requirements.txt  .env.example  .gitignore  run_local.py
config/  common/  simulator/  ingestion/  streaming/  analytics/  app/  scripts/  tests/
snowflake/sql/        dbt_project/ (without target/ logs/ dbt_packages/)
tableau/ (data_sources CSVs, calculated_fields, dashboard_guide.md, dashboard_assets/)
data/sample/  data/DATA_SOURCES.md  data/raw/.gitkeep  data/processed/.gitkeep
docs/  reports/  presentation/
```
## Do NOT upload
`.env` (secrets), `.venv/`, `__pycache__/`, `.pytest_cache/`, `*.duckdb` (regenerated), `dbt_project/target|logs|dbt_packages`, anything in `data/raw/` (real datasets stay external), `data/processed/*`.
## Keep external
Real datasets (Kaggle/Mendeley/AGMARKNET) — fetch with `python scripts/download_datasets.py`; check each licence before redistributing. Tableau `.twbx` files containing real data extracts may be large — use Git LFS or share separately.

## Simple manual upload
1. Unzip `AtmoSync_Complete_Project.zip`. 2. Open your repo on github.com ▸ **Add file ▸ Upload files**. 3. Drag the *contents* of the `AtmoSync` folder (GitHub's web uploader keeps folders when you drag folders). Web upload limits: ~100 files per drag-and-drop batch → upload in 3–4 batches (`config/common/simulator/ingestion/streaming/analytics/app/scripts/tests`, then `dbt_project/snowflake`, then `tableau/data docs reports presentation`, then root files). 4. Commit message e.g. "Add AtmoSync application". 5. Confirm `.env` is not present. 
## Suggested repository README (short)
Use the root `README.md` as-is; add a badge-free one-paragraph summary at top: "AtmoSync — streaming IoT cold-chain analytics with spoilage-arbitrage recommendations (Python · Kafka · Snowflake · dbt · Tableau)."

---
**Phase 2:** the ten feature batches have their own step-by-step guide with per-batch file lists (`BATCH_UPLOAD_GUIDE.md` in the project root and ready-to-copy folders under `batch_upload/`). Upload the Phase 1 files first (this guide), then batches 01–10 in order.
