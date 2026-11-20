# Feature 8 — Shipment Replay and Simulation Controls (Batch 08)
**Depends on:** Batch 01 (navigation/config). Uses Batch 01–03 modules (anomalies, health, forecast) for the comparison metrics and the Phase 1 simulator conventions, `ingestion/cleaning.py`, `analytics/engine.py`, `ingestion/replay.py` (streaming replay, unchanged).
**All data produced here is SIMULATED; fault shapes are illustrative, not measured failure profiles.**

**What it does**
1. **Configurable scenarios** (`config/features/simulation.yaml`): `normal`, `temperature_spike`, `cooling_drift`, `compressor_failure`, `humidity_fluctuation`, `low_humidity`, `vibration_anomaly`, `combined_failure`. Edit or add presets in YAML; override any parameter in code or in the UI (route, progress, shelf life already used, spike size/duration, drift rate, humidity swing/loss, vibration multiplier, seed).
2. **Normal vs abnormal comparison** (`simulator/lab.py::compare_scenarios`): both runs use the same seed, so the random noise is identical and every difference comes from the injected fault. Output: risk category/score, health score, anomaly counts, burn rate, quality window, +24 h forecast category, max temperature, etc.
3. **Historical replay** (`replay_status_at`, `replay_timeline`): re-computes container status using only readings up to a chosen time ("what did the system know then?"); the final frame equals the normal Phase 1 result (tested). The existing streaming replay (`ingestion/replay.py` with a speed-up factor, `streaming/producer.py`) is unchanged.
4. **Container comparison** (`compare_containers`) for any two containers of an existing dataset.

**How a scenario is built:** setpoint + 6-hour sinusoid + seeded noise; spikes are Gaussian pulses (FWHM = duration); drift is a clipped ramp; humidity = sinusoidal swing and/or linear loss; vibration bursts multiply lognormal noise inside a window; GPS interpolates along the route.
**Run:** `python -m simulator.lab` (prints a normal-vs-abnormal line for every preset); UI **Simulation Lab** (scenario builder with sliders, replay slider with risk timeline, container comparison).
**Example output (defaults: PHARR_TX→CHICAGO, 50 % route, 60 % shelf life used):**
`compressor_failure risk LOW->HIGH health 100->39 anomalies 0->45` · `cooling_drift LOW->MEDIUM, 100->95, 0->17` · `temperature_spike risk unchanged, 18 anomalies` (a short spike outside the current health window is still caught by the anomaly detector — that is the point of keeping history).
**Tests:** `tests/test_simulation_lab.py` (10 tests: presets, reproducibility, schema compatibility, effect sizes, normal-vs-abnormal, replay causality and consistency).
**Limitations:** single-container scenarios; no stochastic sensor failures (those exist in the Phase 1 fleet generator); fault parameters are not calibrated; outcomes depend on the shelf-life assumption (set high so that abnormal cases show risk differences).
