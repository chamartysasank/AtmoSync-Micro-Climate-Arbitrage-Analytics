"""One-command LOCAL pipeline:  python run_local.py [--skip-dbt] [--regenerate]
generate sample -> clean -> analytics -> load DuckDB -> (dbt build) -> Tableau CSVs -> alerts (dry-run).
If `dbt build` fails the pipeline stops with a non-zero exit code BEFORE exporting Tableau data or sending alerts."""
import argparse, subprocess, sys
from common.config import load_settings, abs_path, get_logger
from analytics.pipeline import run_pipeline
from analytics.alerts import build_alerts, send_alerts
from analytics.export_tableau import export
from ingestion.local_warehouse import load_local_warehouse

log = get_logger("run_local")


class DbtBuildError(RuntimeError):
    """Raised when `dbt build` cannot run or exits with a non-zero code."""


def run_dbt_build(project_dir: str = "dbt_project", target: str = "duckdb") -> None:
    cmd = ["dbt", "build", "--profiles-dir", ".", "--target", target]
    try:
        rc = subprocess.run(cmd, cwd=project_dir).returncode
    except FileNotFoundError as e:
        raise DbtBuildError("`dbt` was not found on PATH. Install it (pip install -r requirements.txt) "
                            "or run with --skip-dbt.") from e
    if rc != 0:
        raise DbtBuildError(f"`dbt build` failed with exit code {rc}. Fix the dbt errors above (or run with "
                            "--skip-dbt). Tableau export and alerts were NOT run.")
    log.info("dbt build succeeded")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--skip-dbt", action="store_true"); ap.add_argument("--regenerate", action="store_true")
    a = ap.parse_args(argv); cfg = load_settings()
    if a.regenerate or not abs_path(cfg["paths"]["sample_dir"] + "/raw_sensor_events.csv").exists():
        subprocess.run([sys.executable, "scripts/generate_sample_data.py"], check=True)
    r = run_pipeline(cfg)
    log.info("Cleaning stats: %s", r["cleaning_stats"].iloc[0].to_dict())
    log.info("KPIs: %s", r["kpis"].iloc[0].to_dict())
    load_local_warehouse(cfg)
    if not a.skip_dbt:
        try:
            run_dbt_build()
        except DbtBuildError as e:
            log.error("%s", e)
            return 1
    export(cfg)
    send_alerts(build_alerts(r["recs"], r["status"], cfg), cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
