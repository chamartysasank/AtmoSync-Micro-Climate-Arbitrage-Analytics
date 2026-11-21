import pandas as pd
import pytest
from analytics import engine as E
from analytics.routes import compare_routes, recommend_routes, load_profiles, _money
from common.config import abs_path


@pytest.fixture(scope="module")
def prices(cfg):
    return pd.read_csv(abs_path(cfg["paths"]["sample_dir"]) / "market_prices.csv")


@pytest.fixture(scope="module")
def opts(cfg, results, prices):
    return compare_routes(results["status"], results["locations"], load_profiles(cfg), prices, cfg)


def test_direct_profile_matches_phase1_arbitrage(cfg, results, opts, prices):
    p1 = E.arbitrage_options(results["status"], prices, results["locations"], cfg).set_index(["container_id", "market_id"])["net_value_usd"]
    d = opts[opts["profile_id"] == "DIRECT"].set_index(["container_id", "market_id"])["net_value_usd"]
    pd.testing.assert_series_equal(d.sort_index(), p1.sort_index(), check_names=False, rtol=1e-9)


def test_shape_and_baselines(opts, cfg):
    n_prof = len(pd.read_csv(abs_path(cfg["routes"]["profiles_file"])))
    assert len(opts) == 12 * 9 * n_prof
    assert opts.groupby("container_id")["is_baseline"].sum().eq(1).all()
    b = opts[opts["is_baseline"]]
    assert (b["benefit_vs_baseline_usd"].abs() < 1e-9).all() and (b["rerouting_cost_usd"].abs() < 1e-9).all()


def test_warmer_corridor_burns_faster(opts):
    o = opts[(opts.container_id == "CNT-009") & (opts.market_id == "DENVER")].set_index("profile_id")
    assert o.loc["SOUTHERN_ALT", "effective_burn_rate"] > o.loc["DIRECT", "effective_burn_rate"] > o.loc["NORTHERN_ALT", "effective_burn_rate"]


def test_reroute_cost_components(opts, cfg):
    o = opts[(opts.container_id == "CNT-009") & (opts.market_id == "DENVER") & (opts.profile_id == "DIRECT")].iloc[0]
    assert o["reroute_fee_usd"] == cfg["arbitrage"]["reroute_fixed_fee_usd"]
    assert o["rerouting_cost_usd"] == pytest.approx(o["reroute_fee_usd"] + o["transport_cost_usd"] - o["baseline_transport_usd"])


def test_recommendations_respect_degradation_rule(opts, cfg):
    rec = recommend_routes(opts, cfg).set_index("container_id")
    assert rec.loc["CNT-009", "recommendation"].startswith("REROUTE") and rec.loc["CNT-009", "recommended_market"] == "DENVER"
    keep = rec[rec["recommendation"] == "KEEP CURRENT ROUTE"]
    assert len(keep) == 11 and (keep["benefit_usd"] == 0).all()
    assert "higher price elsewhere alone" in rec.loc["CNT-001", "explanation"]       # healthy container: price alone is not enough
    assert rec.loc["CNT-009", "benefit_usd"] > cfg["arbitrage"]["min_benefit_usd"]
    assert "least-bad" in rec.loc["CNT-009", "explanation"]


def test_prefers_option_with_enough_shelf_life(opts, cfg):
    x = opts.copy()
    cid = "CNT-009"
    mask = (x.container_id == cid) & (x.market_id == "PHOENIX") & (x.profile_id == "NORTHERN_ALT")
    x.loc[mask, ["remaining_life_at_arrival_h", "net_value_usd"]] = [100.0, 1.0]        # fresh but low value
    x.loc[mask, "benefit_vs_baseline_usd"] = 1e6                                         # make it clear the threshold is met
    rec = recommend_routes(x, cfg).set_index("container_id")
    assert (rec.loc[cid, "recommended_market"], rec.loc[cid, "recommended_profile"]) == ("PHOENIX", "NORTHERN_ALT")


def test_money_format():
    assert _money(1234.4) == "$1,234" and _money(-2872.2) == "-$2,872"


def test_sample_profiles_are_labelled(cfg):
    assert load_profiles(cfg)["data_origin"].str.contains("SAMPLE").all()
