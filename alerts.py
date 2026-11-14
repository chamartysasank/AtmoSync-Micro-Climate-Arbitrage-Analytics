"""Slack / e-mail alerts for REROUTE opportunities and CRITICAL containers.
dry_run (default) only logs. Real sending needs SLACK_WEBHOOK_URL and/or SMTP_* env vars. UNTESTED live."""
from __future__ import annotations
import os, smtplib
from email.message import EmailMessage
import pandas as pd
from common.config import get_logger

log = get_logger(__name__)


def build_alerts(recs: pd.DataFrame, status: pd.DataFrame, cfg: dict) -> list[str]:
    msgs = []
    s = status.set_index("container_id")
    for _, r in recs.iterrows():
        if r["recommended_action"] == "REROUTE" and r["best_benefit_usd"] >= cfg["alerts"]["min_benefit_usd"]:
            c = s.loc[r["container_id"]]
            msgs.append(f"[REROUTE] {r['container_id']} ({r['risk_category']}): {r['original_destination']} -> {r['best_alternative']}, "
                        f"est. net benefit ${r['best_benefit_usd']:,.0f}; quality window {c['quality_window_hours']:.0f} h vs "
                        f"{c['hours_to_destination']:.0f} h to destination.")
        elif r["risk_category"] == "CRITICAL":
            msgs.append(f"[CRITICAL] {r['container_id']}: slack {s.loc[r['container_id'], 'slack_hours']:.0f} h, no profitable reroute found.")
    return msgs


def send_alerts(messages: list[str], cfg: dict) -> dict:
    out = {"messages": len(messages), "sent": False, "dry_run": cfg["alerts"]["dry_run"]}
    if not cfg["alerts"]["enabled"] or not messages:
        return out
    text = "\n".join(messages)
    if cfg["alerts"]["dry_run"]:
        for m in messages:
            log.info("ALERT (dry run): %s", m)
        return out
    hook = os.getenv("SLACK_WEBHOOK_URL")
    if hook:
        import requests
        requests.post(hook, json={"text": "*AtmoSync alerts*\n" + text}, timeout=10).raise_for_status(); out["sent"] = True
    if os.getenv("SMTP_HOST") and os.getenv("ALERT_EMAIL_TO"):
        m = EmailMessage(); m["Subject"] = "AtmoSync alerts"; m["From"] = os.environ["SMTP_USER"]; m["To"] = os.environ["ALERT_EMAIL_TO"]
        m.set_content(text)
        with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587"))) as s:
            s.starttls(); s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"]); s.send_message(m); out["sent"] = True
    return out
