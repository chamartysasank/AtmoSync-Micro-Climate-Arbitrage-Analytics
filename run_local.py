"""One-command LOCAL pipeline:  python run_local.py [--skip-dbt] [--regenerate] [--skip-phase2] [--report] [--no-monitor]
generate sample -> clean + analytics -> load DuckDB -> (dbt build) -> Tableau CSVs -> Slack/e-mail alerts (dry-run)
-> Phase 2: health history, data-quality summary, alert-centre sync, (optional) executive report.
If `dbt build` fails the pipeline stops with a non-zero exit code BEFORE exporting Tableau data or sending alerts.
Every run is recorded (runs, steps, logs, ingestion statistics) in the local database for the System Monitoring page."""
import argparse, subprocess, sys
from common.config import load_settings, abs_path, get_logger
from common.monitoring import PipelineMonitor
from common.store import Store
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


def run_phase2(r: dict, cfg: dict, run, store: Store, report: bool = False) -> None:
    """Persist Phase 2 outputs (history, quality, alerts) - each as a monitored step."""
    from analytics.health import health_timeline, save_health_history
    from analytics.alert_center import collect_candidates, sync_alerts
    from ingestion.quality import quality_alert_candidates, save_quality_summary
    with run.step("health_history") as s:
        s.metrics(rows_out=save_health_history(health_timeline(r["readings"], cfg), store))
    with run.step("quality_summary") as s:
        s.metrics(rows_out=save_quality_summary(r["quality"], store))
    with run.step("alert_sync") as s:
        stats = sync_alerts(collect_candidates(r, cfg, extra=quality_alert_candidates(r["quality"], cfg)), store)
        s.metrics(rows_out=stats["created"] + stats["updated"], message=str(stats)); log.info("alert sync: %s", stats)
    if report:
        from analytics.reporting import build_report, export_csv_bundle, export_pdf
        with run.step("executive_report") as s:
            rep = build_report(r, cfg); out = abs_path(cfg["reporting"]["export_dir"])
            export_csv_bundle(rep, out); export_pdf(rep, cfg, out / "executive_report.pdf"); s.metrics(message=str(out))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-dbt", action="store_true"); ap.add_argument("--regenerate", action="store_true")
    ap.add_argument("--skip-phase2", action="store_true"); ap.add_argument("--report", action="store_true"); ap.add_argument("--no-monitor", action="store_true")
    a = ap.parse_args(argv); cfg = load_settings(); store = Store()
    with PipelineMonitor("run_local", store, trigger="cli", cfg=cfg, enabled=not a.no_monitor) as run:
        if a.regenerate or not abs_path(cfg["paths"]["sample_dir"] + "/raw_sensor_events.csv").exists():
            with run.step("generate_sample_data"):
                subprocess.run([sys.executable, "scripts/generate_sample_data.py"], check=True)
        with run.step("analytics_pipeline") as s:
            r = run_pipeline(cfg)
            s.metrics(rows_in=len(r["raw"]), rows_out=len(r["clean"]))
            run.record_ingestion(r["cleaning_stats"].iloc[0].to_dict(), r["quality"].summary)
        log.info("Cleaning stats: %s", r["cleaning_stats"].iloc[0].to_dict())
        log.info("KPIs: %s", r["kpis"].iloc[0].to_dict())
        log.info("Data quality: %.1f/100 (%s)", r["quality"].summary["overall_score"], r["quality"].summary["status"])
        with run.step("load_local_warehouse"):
            load_local_warehouse(cfg)
        if not a.skip_dbt:
            try:
                with run.step("dbt_build"):
                    run_dbt_build()
            except DbtBuildError as e:
                log.error("%s", e)
                return 1
        with run.step("tableau_export"):
            export(cfg)
        with run.step("slack_email_alerts"):
            send_alerts(build_alerts(r["recs"], r["status"], cfg), cfg)
        if not a.skip_phase2:
            run_phase2(r, cfg, run, store, report=a.report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
