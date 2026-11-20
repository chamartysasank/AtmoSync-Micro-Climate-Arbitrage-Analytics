# Feature 1 — Sensor Anomaly Detection (Batch 01)

**What it does.** Flags abnormal, missing and invalid sensor readings, classifies each as WARNING or CRITICAL and explains why in plain text.

**How it works** (`analytics/anomaly.py`, function `detect_anomalies(raw, cfg)`): it runs on the RAW events (before cleaning) so invalid data is still visible.
| Check | Type label | Logic |
|---|---|---|
| Missing / invalid | `missing_value`, `invalid_reading` | null, non-numeric, sentinel (-999/-9999), outside plausible range, bad timestamp → severity from `invalid_severity` |
| Threshold | `threshold` | outside warn limits → WARNING; beyond limit + critical margin → CRITICAL (vibration: warn/critical g) |
| Statistical | `statistical` | z-score vs previous 12 readings of the same container (std floored by `min_std`) |
| Rate of change | `rate_of_change` | °C/h and %RH/h between consecutive readings |
| Gap | `gap` | minutes between consecutive readings |
| Stuck sensor | `stuck_sensor` | 8 identical consecutive values (reported once per run) |

**Existing modules used:** `common/config.py` (extended to merge `config/features/*.yaml`), `analytics/pipeline.py` (now also returns `raw`), the `thresholds:` block of `config/settings.yaml`, `app/` (navigation scaffold added in this batch).

**Configure:** `config/features/anomaly.yaml` (`null` limits inherit from `settings.yaml → thresholds`). Values are project defaults [ASSUMPTION], not validated limits.

**Run:**
```python
import pandas as pd; from common.config import load_settings; from analytics.anomaly import detect_anomalies, summarize_anomalies
a = detect_anomalies(pd.read_csv("data/sample/raw_sensor_events.csv"), load_settings())
```
UI: `streamlit run app/streamlit_app.py` → **Anomaly Detection** (filters: severity, container, type; CSV download).

**Example output (shipped sample, 819 raw events):** 138 flags — 46 CRITICAL / 92 WARNING across 9 containers; worst container CNT-009 (compressor failure: 33 CRITICAL). Example row: `Vibration 0.69 g exceeds the warning limit of 0.60 g.`

**Also in this batch:** Streamlit navigation scaffold (`app/context.py`, `app/views/`): the Phase 1 tabs are preserved as **Overview** and **Shipment Monitoring**; later batches add pages by adding one file to `app/views/`.

**Tests:** `tests/test_anomaly.py` (14), `tests/test_app_navigation.py` (renders every registered page).
**Limitations:** thresholds are heuristics; z-scores assume a locally stable baseline and can miss slow drifts (the threshold check catches those); the sample data is simulated, so flag counts are demonstrations, not findings.
