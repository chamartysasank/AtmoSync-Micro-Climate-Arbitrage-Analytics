import json
from streaming.consumer import process_messages
from streaming.validation import validate_event
from streaming.sinks import JsonlSink, DuckDBSink

GOOD = {"event_id": "a", "container_id": "C", "sensor_id": "S", "shipment_id": "SH", "reading_ts": "2026-01-01T00:00:00Z",
        "temperature_c": 7.0, "humidity_pct": 90.0, "vibration_g": 0.2, "latitude": 1.0, "longitude": 2.0}


class ListSink:
    def __init__(self): self.rows = []
    def write_batch(self, e): self.rows += e; return len(e)


def test_validation():
    assert validate_event(GOOD) == []
    assert "missing:container_id" in validate_event({**GOOD, "container_id": None})
    assert "type:temperature_c" in validate_event({**GOOD, "temperature_c": "hot"})


def test_process_messages_routes_bad_to_dlq():
    sink, dlq = ListSink(), []
    out = process_messages([json.dumps(GOOD).encode(), b"{not json", json.dumps({**GOOD, "sensor_id": ""}).encode()], sink,
                           lambda raw, why: dlq.append(why))
    assert out == {"written": 1, "rejected": 2} and len(dlq) == 2


def test_jsonl_and_duckdb_sinks(tmp_path):
    assert JsonlSink(tmp_path / "x.jsonl").write_batch([GOOD]) == 1
    s = DuckDBSink(tmp_path / "t.duckdb")
    assert s.write_batch([GOOD]) == 1
    assert s.con.execute("select count(*) from raw.raw_sensor_events").fetchone()[0] == 1


# ---------------- consumer-side dead-letter handling ----------------
import base64, sys, types
import pytest
from streaming import consumer as C


class FakeProducer:
    def __init__(self, log=None, fail_flush=False): self.sent, self.log, self.fail_flush = [], log if log is not None else [], fail_flush
    def produce(self, topic, value=None, key=None, on_delivery=None): self.sent.append((topic, value)); self.log.append("produce")
    def poll(self, t): pass
    def flush(self, t=None): self.log.append("flush"); return 1 if self.fail_flush else 0


def test_build_dlq_message_preserves_payload_and_reasons():
    raw = b'{"event_id": "x", "container_id": null}'
    env = json.loads(C.build_dlq_message(raw, ["missing:container_id"], "atmosync.sensor.events"))
    assert env["original_payload"] == raw.decode() and env["problems"] == ["missing:container_id"]
    assert env["source_topic"] == "atmosync.sensor.events" and "rejected_at" in env


def test_build_dlq_message_binary_payload_is_lossless():
    raw = b"\xff\xfe\x00bad"
    env = json.loads(C.build_dlq_message(raw, ["bad_json"], "t"))
    assert "original_payload" not in env and base64.b64decode(env["original_payload_b64"]) == raw


def test_process_messages_forwards_rejects_to_dlq_topic():
    prod, sink = FakeProducer(), ListSink()
    h = C.make_dlq_handler(prod, "dlq.topic", "main.topic")
    bad_json, bad_event = b"{not json", json.dumps({**GOOD, "sensor_id": ""}).encode()
    out = C.process_messages([json.dumps(GOOD).encode(), bad_json, bad_event], sink, h)
    assert out == {"written": 1, "rejected": 2}
    assert [t for t, _ in prod.sent] == ["dlq.topic", "dlq.topic"]
    bodies = [json.loads(v) for _, v in prod.sent]
    assert bodies[0]["original_payload"] == bad_json.decode() and bodies[0]["problems"] == ["bad_json"]
    assert json.loads(bodies[1]["original_payload"])["event_id"] == "a" and "missing:sensor_id" in bodies[1]["problems"]


def test_flush_dlq_raises_when_undelivered():
    p = FakeProducer(fail_flush=True); h = C.make_dlq_handler(p, "d", "m")
    with pytest.raises(RuntimeError):
        C.flush_dlq(p, h)


def _fake_kafka(monkeypatch, msgs, log):
    state = {"subscribed": None, "consumed": False}

    class Msg:
        def __init__(self, v): self.v = v
        def value(self): return self.v
        def error(self): return None

    class Consumer:
        def __init__(self, conf): state["conf"] = conf
        def subscribe(self, topics): state["subscribed"] = list(topics)
        def consume(self, num_messages, timeout):
            if state["consumed"]: return []
            state["consumed"] = True; return [Msg(m) for m in msgs]
        def commit(self, asynchronous=False): log.append("commit")
        def close(self): log.append("close")

    prod = FakeProducer(log)
    mod = types.SimpleNamespace(Consumer=Consumer, Producer=lambda conf: prod)
    monkeypatch.setitem(sys.modules, "confluent_kafka", mod)
    return state, prod


def test_run_never_subscribes_to_dlq_and_flushes_before_commit(monkeypatch, cfg):
    log, sink = [], ListSink()
    state, prod = _fake_kafka(monkeypatch, [json.dumps(GOOD).encode(), b"garbage"], log)
    C.run(max_batches=1, cfg=cfg, sink=sink)
    k = cfg["kafka"]
    assert state["subscribed"] == [k["topic"]] and k["dlq_topic"] not in state["subscribed"]
    assert len(sink.rows) == 1 and [t for t, _ in prod.sent] == [k["dlq_topic"]]
    assert log.index("flush") < log.index("commit")           # DLQ delivered before offsets committed
    assert state["conf"]["enable.auto.commit"] is False


def test_run_rejects_dlq_equal_to_main_topic(monkeypatch, cfg):
    _fake_kafka(monkeypatch, [], [])
    bad = {**cfg, "kafka": {**cfg["kafka"], "dlq_topic": cfg["kafka"]["topic"]}}
    with pytest.raises(ValueError):
        C.run(max_batches=1, cfg=bad, sink=ListSink())


def test_run_does_not_commit_when_dlq_flush_fails(monkeypatch, cfg):
    log = []
    state, prod = _fake_kafka(monkeypatch, [b"garbage"], log); prod.fail_flush = True
    with pytest.raises(RuntimeError):
        C.run(max_batches=1, cfg=cfg, sink=ListSink())
    assert "commit" not in log and "close" in log
