import pandas as pd
import pytest
from analytics import market as M
from common.config import abs_path


@pytest.fixture(scope="module")
def ds(cfg):
    return M.load_price_datasets(cfg)


@pytest.fixture(scope="module")
def loc(cfg):
    return pd.read_csv(abs_path(cfg["paths"]["sample_dir"]) / "locations.csv")


def _prices(rows):
    return pd.DataFrame(rows, columns=["price_date", "market_id", "price_modal_usd_kg"]).assign(
        commodity_id="avocado_hass", price_date=lambda d: pd.to_datetime(d["price_date"]), dataset_type="SIMULATED")


def test_loading_labels_and_optional_dataset(ds, cfg):
    assert set(ds) == {"sample_simulated"}                       # hab_derived is optional and absent
    assert ds["sample_simulated"]["dataset_type"].eq("SIMULATED").all()
    cat = M.dataset_catalog(ds).iloc[0]
    assert cat["rows"] == 810 and cat["markets"] == 9 and cat["dataset_type"] == "SIMULATED"


def test_historical_derived_dataset_loads_via_config(tmp_path, cfg):
    from ingestion.hab_prices import load_hab_avocado
    raw = tmp_path / "avocado.csv"
    raw.write_text("Date,AveragePrice,type,region\n2018-01-07,1.00,conventional,Chicago\n2018-01-14,1.10,conventional,Chicago\n")
    out = tmp_path / "hab.csv"; load_hab_avocado(str(raw)).to_csv(out, index=False)
    c2 = {**cfg, "market": {**cfg["market"], "datasets": cfg["market"]["datasets"] + [dict(id="hab_test", path=str(out), type="HISTORICAL_DERIVED", optional=False, description="test")]}}
    d = M.load_price_datasets(c2)["hab_test"]
    assert d["dataset_type"].iloc[0] == "HISTORICAL_DERIVED" and d["data_origin"].str.contains("DERIVED").all()


def test_validation_errors():
    with pytest.raises(ValueError): M.validate_price_dataset(pd.DataFrame({"market_id": ["A"]}))
    with pytest.raises(ValueError): M.validate_price_dataset(pd.DataFrame(dict(price_date=["2026-01-01"], market_id=["A"], commodity_id=["x"], price_modal_usd_kg=[-1.0])))


def test_missing_required_dataset_raises(cfg):
    c2 = {**cfg, "market": {**cfg["market"], "datasets": [dict(id="x", path="data/sample/nope.csv", type="SIMULATED", optional=False, description="")]}}
    with pytest.raises(FileNotFoundError): M.load_price_datasets(c2)


def test_trends_rising_falling_stable(cfg):
    days = pd.date_range("2026-01-01", periods=40)
    rows = [(d, "UP", 3 + 0.05 * i) for i, d in enumerate(days)] + [(d, "DOWN", 5 - 0.05 * i) for i, d in enumerate(days)] + [(d, "FLAT", 4.0) for d in days]
    t = M.price_trends(_prices(rows), cfg).set_index("market_id")
    assert (t.loc["UP", "trend"], t.loc["DOWN", "trend"], t.loc["FLAT", "trend"]) == ("Rising", "Falling", "Stable")
    assert t.loc["UP", "slope_usd_per_day"] == pytest.approx(0.05, abs=1e-6) and t.loc["FLAT", "volatility_pct"] == 0
    assert t.loc["UP", "change_7d_pct"] == pytest.approx(100 * (4.95 / 4.60 - 1), abs=0.01)


def test_margin_arithmetic(cfg, loc):
    p = _prices([("2026-01-01", "CHICAGO", 3.0), ("2026-01-01", "NEW_YORK", 4.0)])
    m = M.arbitrage_margins(p, loc, cfg, quantity_kg=1000).set_index(["buy_market", "sell_market"])
    r = m.loc[("CHICAGO", "NEW_YORK")]
    transport = r["distance_km"] / 1000 * cfg["arbitrage"]["transport_usd_per_tonne_km"]
    assert r["gross_margin_usd_kg"] == pytest.approx(1.0) and r["net_margin_usd_kg"] == pytest.approx(1.0 - transport - cfg["arbitrage"]["handling_usd_per_kg"])
    assert r["net_margin_usd"] == pytest.approx(r["net_margin_usd_kg"] * 1000) and r["profitable"]
    assert not m.loc[("NEW_YORK", "CHICAGO"), "profitable"] and m.loc[("NEW_YORK", "CHICAGO"), "gross_margin_usd_kg"] == pytest.approx(-1.0)


def test_small_price_gap_is_not_profitable_after_costs(cfg, loc):
    p = _prices([("2026-01-01", "LOS_ANGELES", 3.00), ("2026-01-01", "NEW_YORK", 3.20)])         # 0.20 gross, ~0.4 transport
    r = M.arbitrage_margins(p, loc, cfg).set_index(["buy_market", "sell_market"]).loc[("LOS_ANGELES", "NEW_YORK")]
    assert r["gross_margin_usd_kg"] > 0 and not r["profitable"]


def test_latest_comparison_and_history(ds, cfg, loc):
    p = ds["sample_simulated"]
    lc = M.latest_comparison(p)
    assert lc["rank"].min() == 1 and lc["premium_vs_avg_usd_kg"].sum() == pytest.approx(0, abs=1e-9) and lc.iloc[0]["market_id"] == "NEW_YORK"
    h = M.margin_history(p, loc, cfg, "HOUSTON", "NEW_YORK")
    last = M.arbitrage_margins(p, loc, cfg).set_index(["buy_market", "sell_market"]).loc[("HOUSTON", "NEW_YORK")]
    assert h.iloc[-1]["net_margin_usd_kg"] == pytest.approx(last["net_margin_usd_kg"]) and len(h) == 90


def test_simulated_series_reproducible_and_labelled(cfg):
    a = M.simulate_price_series({"A": 0.2, "B": -0.1}, cfg); b = M.simulate_price_series({"A": 0.2, "B": -0.1}, cfg)
    assert a.equals(b) and a["data_origin"].str.startswith("SIMULATED").all() and len(a) == 180
    assert not a.equals(M.simulate_price_series({"A": 0.2, "B": -0.1}, cfg, seed=99))
