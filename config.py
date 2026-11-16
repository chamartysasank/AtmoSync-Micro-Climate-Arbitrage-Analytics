"""Configuration loader: YAML settings + environment variables (.env supported)."""
from __future__ import annotations
import logging, os
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]

try:  # optional dependency
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:  # pragma: no cover
    pass


def load_settings(path: str | Path | None = None) -> dict:
    p = Path(path) if path else ROOT / "config" / "settings.yaml"
    with open(p, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if os.getenv("KAFKA_BOOTSTRAP_SERVERS"):
        cfg["kafka"]["bootstrap_servers"] = os.environ["KAFKA_BOOTSTRAP_SERVERS"]
    return cfg


def load_commodities() -> dict:
    with open(ROOT / "config" / "commodities.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def abs_path(rel: str) -> Path:
    return ROOT / rel


def get_logger(name: str) -> logging.Logger:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                            format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    return logging.getLogger(name)
