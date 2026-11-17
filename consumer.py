"""Kafka consumer -> sink. Requires confluent-kafka and a broker. UNTESTED against a live broker here.

  python -m streaming.consumer --sink duckdb        # local warehouse
  python -m streaming.consumer --sink jsonl
  python -m streaming.consumer --sink snowflake     # needs SNOWFLAKE_* env vars
"""
from __future__ import annotations
import argparse, base64, json
from datetime import datetime, timezone
from common.config import load_settings, abs_path, get_logger
from streaming.validation import validate_event
from streaming.sinks import JsonlSink, DuckDBSink, SnowflakeSink

log = get_logger(__name__)


def process_messages(messages: list[bytes], sink, dlq_handler=None) -> dict:
    """Pure function (unit-tested without Kafka): decode -> validate -> sink valid events."""
    good, bad = [], 0
    for raw in messages:
        try:
            ev = json.loads(raw)
        except (ValueError, TypeError):
            bad += 1; dlq_handler and dlq_handler(raw, ["bad_json"]); continue
        problems = validate_event(ev)
        if problems:
            bad += 1; dlq_handler and dlq_handler(raw, problems)
        else:
            good.append(ev)
    written = sink.write_batch(good) if good else 0
    return {"written": written, "rejected": bad}


def build_dlq_message(raw: bytes, problems: list[str], source_topic: str) -> bytes:
    """DLQ envelope: original payload preserved verbatim + rejection reasons + provenance.
    Non-UTF-8 payloads are kept losslessly as base64."""
    env = {"source_topic": source_topic, "problems": list(problems),
           "rejected_at": datetime.now(timezone.utc).isoformat()}
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    try:
        env["original_payload"] = raw.decode("utf-8")
    except UnicodeDecodeError:
        env["original_payload_b64"] = base64.b64encode(raw).decode("ascii")
    return json.dumps(env).encode("utf-8")


def make_dlq_handler(producer, dlq_topic: str, source_topic: str, errors: list | None = None):
    """Returns a handler(raw, problems) that forwards a rejected message to the DLQ topic."""
    errors = errors if errors is not None else []

    def on_delivery(err, _msg):
        if err is not None:
            errors.append(str(err))

    def handler(raw, problems):
        producer.produce(dlq_topic, value=build_dlq_message(raw, problems, source_topic), on_delivery=on_delivery)
        producer.poll(0)
    handler.errors = errors
    return handler


def flush_dlq(producer, handler, timeout: float = 30.0) -> None:
    """Block until DLQ messages are delivered; raise (=> offsets are NOT committed) otherwise."""
    remaining = producer.flush(timeout)
    if remaining or handler.errors:
        raise RuntimeError(f"DLQ delivery failed (undelivered={remaining}, errors={handler.errors[:3]})")


def run(sink_name: str = "duckdb", batch_size: int = 200, max_batches: int | None = None, cfg: dict | None = None, sink=None):
    from confluent_kafka import Consumer
    from streaming.producer import make_producer
    cfg = cfg or load_settings(); k = cfg["kafka"]
    if k["dlq_topic"] == k["topic"]:
        raise ValueError("kafka.dlq_topic must differ from kafka.topic (would create a reject loop)")
    sink = sink or {"duckdb": lambda: DuckDBSink(abs_path(cfg["paths"]["duckdb_file"])),
                    "jsonl": lambda: JsonlSink(abs_path(cfg["paths"]["processed_dir"]) / "kafka_events.jsonl"),
                    "snowflake": SnowflakeSink}[sink_name]()
    dlq_producer = make_producer(k["bootstrap_servers"])
    dlq = make_dlq_handler(dlq_producer, k["dlq_topic"], k["topic"])
    c = Consumer({"bootstrap.servers": k["bootstrap_servers"], "group.id": k["consumer_group"],
                  "auto.offset.reset": "earliest", "enable.auto.commit": False})
    c.subscribe([k["topic"]])            # ONLY the main topic: the DLQ is never consumed here => no reject loop
    batches = 0
    try:
        while max_batches is None or batches < max_batches:
            msgs = c.consume(num_messages=batch_size, timeout=2.0)
            payloads = [m.value() for m in msgs if m is not None and not m.error()]
            if not payloads:
                continue
            log.info("Batch: %s", process_messages(payloads, sink, dlq))
            flush_dlq(dlq_producer, dlq)       # DLQ delivered before offsets are committed
            c.commit(asynchronous=False)       # commit only after sink + DLQ succeeded (at-least-once)
            batches += 1
    finally:
        c.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--sink", choices=["duckdb", "jsonl", "snowflake"], default="duckdb")
    ap.add_argument("--max-batches", type=int, default=None)
    a = ap.parse_args(); run(a.sink, max_batches=a.max_batches)
