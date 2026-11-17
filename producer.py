"""Kafka producer. Requires: pip install confluent-kafka  and a running broker (see docker-compose.yml).

NOT executed against a live broker in the delivery environment - see docs/limitations.
Usage:
  python -m streaming.producer --source data/sample/raw_sensor_events.csv --speedup 600
  python -m streaming.producer --simulate            # live simulator instead of replay
"""
from __future__ import annotations
import argparse, json
from common.config import load_settings, get_logger
from ingestion.replay import replay_events
from streaming.validation import validate_event

log = get_logger(__name__)


def make_producer(bootstrap: str):
    from confluent_kafka import Producer  # lazy import: local mode works without Kafka libs
    return Producer({"bootstrap.servers": bootstrap, "linger.ms": 20, "compression.type": "lz4",
                     "enable.idempotence": True, "acks": "all"})


def publish(events, cfg: dict, producer=None) -> dict:
    k = cfg["kafka"]
    producer = producer or make_producer(k["bootstrap_servers"])
    stats = {"sent": 0, "dlq": 0, "delivery_errors": 0}

    def on_delivery(err, msg):
        if err is not None:
            stats["delivery_errors"] += 1
            log.error("Delivery failed: %s", err)

    for ev in events:
        problems = validate_event(ev)
        topic = k["topic"] if not problems else k["dlq_topic"]
        body = ev if not problems else {"event": ev, "problems": problems}
        producer.produce(topic, key=str(ev.get("container_id", "")).encode(), value=json.dumps(body).encode(),
                         on_delivery=on_delivery)       # key = container_id keeps per-container ordering
        stats["dlq" if problems else "sent"] += 1
        producer.poll(0)
    producer.flush(30)
    log.info("Producer finished: %s", stats)
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="data/sample/raw_sensor_events.csv")
    ap.add_argument("--speedup", type=float, default=0.0)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    cfg = load_settings()
    publish(replay_events(a.source, a.speedup, a.limit), cfg)


if __name__ == "__main__":
    main()
