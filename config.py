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
    # Phase 2: optional per-feature files config/features/*.yaml are merged under their own top-level keys.
    feat_dir = p.parent / "features"
    if feat_dir.is_dir():
        for f in sorted(feat_dir.glob("*.yaml")):
            with open(f, "r", encoding="utf-8") as fh:
                for key, val in (yaml.safe_load(fh) or {}).items():
                    cfg[key] = {**cfg.get(key, {}), **val} if isinstance(val, dict) and isinstance(cfg.get(key), dict) else val
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
