"""Throughput probe for the mid-project review ("Kafka handles high-frequency streams without lag").

  python -m streaming.benchmark --events 100000            # needs a running broker
Offline part (no broker): measures how fast the simulator/validator can generate+validate events.
It does NOT prove broker throughput - run the broker part yourself and record the numbers.
"""
import argparse, time
from common.config import load_settings
from streaming.validation import validate_event


def offline_rate(n: int = 50000) -> float:
    ev = {"event_id": "x", "container_id": "C", "sensor_id": "S", "shipment_id": "SH", "reading_ts": "2026-01-01T00:00:00Z",
          "temperature_c": 7.0, "humidity_pct": 90.0, "vibration_g": 0.2}
    t = time.perf_counter()
    for i in range(n):
        validate_event({**ev, "event_id": str(i)})
    return n / (time.perf_counter() - t)


def broker_rate(n: int) -> dict:
    from streaming.producer import make_producer
    cfg = load_settings(); k = cfg["kafka"]; p = make_producer(k["bootstrap_servers"])
    t = time.perf_counter()
    for i in range(n):
        p.produce(k["topic"], key=b"bench", value=b'{"event_id":"%d","container_id":"B","sensor_id":"S","shipment_id":"X","reading_ts":"2026-01-01T00:00:00Z"}' % i)
        p.poll(0)
    p.flush(120)
    dt = time.perf_counter() - t
    return {"events": n, "seconds": round(dt, 2), "events_per_sec": round(n / dt)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--events", type=int, default=0); a = ap.parse_args()
    print(f"offline validation rate: {offline_rate():.0f} events/s")
    if a.events:
        print(broker_rate(a.events))
