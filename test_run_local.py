import types
import pytest
import run_local


class _Done:
    def __init__(self, rc): self.returncode = rc


@pytest.fixture
def calls(monkeypatch):
    rec = {"export": 0, "alerts": 0, "warehouse": 0}
    monkeypatch.setattr(run_local, "load_local_warehouse", lambda cfg: rec.__setitem__("warehouse", rec["warehouse"] + 1))
    monkeypatch.setattr(run_local, "export", lambda cfg: rec.__setitem__("export", rec["export"] + 1))
    monkeypatch.setattr(run_local, "send_alerts", lambda msgs, cfg: rec.__setitem__("alerts", rec["alerts"] + 1))
    return rec


def test_failed_dbt_build_stops_pipeline(monkeypatch, calls, caplog):
    monkeypatch.setattr(run_local.subprocess, "run", lambda cmd, **kw: _Done(2))
    with caplog.at_level("ERROR"):
        assert run_local.main([]) == 1
    assert calls["export"] == 0 and calls["alerts"] == 0
    assert "dbt build" in caplog.text and "exit code 2" in caplog.text


def test_missing_dbt_executable_gives_clear_error(monkeypatch, calls, caplog):
    def boom(cmd, **kw): raise FileNotFoundError("dbt")
    monkeypatch.setattr(run_local.subprocess, "run", boom)
    with caplog.at_level("ERROR"):
        assert run_local.main([]) == 1
    assert calls["export"] == 0 and calls["alerts"] == 0 and "not found" in caplog.text


def test_successful_dbt_build_continues(monkeypatch, calls):
    monkeypatch.setattr(run_local.subprocess, "run", lambda cmd, **kw: _Done(0))
    assert run_local.main([]) == 0
    assert calls["export"] == 1 and calls["alerts"] == 1


def test_skip_dbt_does_not_call_dbt(monkeypatch, calls):
    def fail(cmd, **kw): raise AssertionError("dbt must not run")
    monkeypatch.setattr(run_local.subprocess, "run", fail)
    assert run_local.main(["--skip-dbt"]) == 0 and calls["export"] == 1


def test_run_dbt_build_raises(monkeypatch):
    monkeypatch.setattr(run_local.subprocess, "run", lambda cmd, **kw: _Done(1))
    with pytest.raises(run_local.DbtBuildError):
        run_local.run_dbt_build()
