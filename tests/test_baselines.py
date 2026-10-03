import numpy as np
import pandas as pd

from src.models import baselines as b


def test_normalize_role_variants_and_null():
    assert b.normalize_role("Batsman") == "Batter"
    assert b.normalize_role("Wicket Keeper") == "Wicket-Keeper"
    assert b.normalize_role("Wicket-Keeper") == "Wicket-Keeper"
    assert b.normalize_role(np.nan) == "Unknown"
    assert b.normalize_role("Coach") == "Unknown"


def test_metrics_values():
    m = b.metrics([10.0, 20.0], [10.0, 30.0])
    assert m["n"] == 2
    assert m["mae_inr"] == 5.0
    assert np.isclose(m["rmse_inr"], np.sqrt(50.0))
    assert m["mae_log1p"] > 0


def test_load_auction_drops_usd_and_normalizes(tmp_path):
    p = tmp_path / "a.csv"
    pd.DataFrame(
        {
            "year": [2013, 2014],
            "player_name": ["A", "B"],
            "role": ["Bowler", "Batsman"],
            "sold_price": [5.0, 7.0],
            "sold_price_currency": ["USD", "INR"],
        }
    ).to_csv(p, index=False)
    d = b.load_auction(p)
    assert list(d.player_name) == ["B"]
    assert d.role_norm.iloc[0] == "Batter"


def _synthetic_auction():
    rows = []
    for y in range(2014, 2027):
        for i, r in enumerate(["Batter", "Bowler", "Bowler"]):
            rows.append({"year": y, "role_norm": r, "sold_price": float((i + 1) * 1000 * (y - 2013))})
    return pd.DataFrame(rows)


def test_run_baselines_splits_and_holdout_never_scored():
    res = b.run_baselines(_synthetic_auction())
    s = res["split_sizes"]
    assert s["train"] == 30 and s["validation"] == 6 and s["holdout_2026_not_scored"] == 3
    assert set(res["baselines"]) == {"global_mean", "global_median", "role_median", "prev_year_median"}
    for v in res["baselines"].values():
        assert v["validation"]["n"] == 6


def test_unseen_role_falls_back_to_global_median():
    d = _synthetic_auction()
    d.loc[(d.year == 2024), "role_norm"] = "Unknown"
    res = b.run_baselines(d)
    assert res["baselines"]["role_median"]["validation"]["n"] == 6


def _fake_q(dom_val, dom_pct, ipl_val):
    dom = pd.DataFrame(
        {"player_id": list("abcd"), "start_year": 2020, "dom_val": dom_val, "dom_pct": dom_pct}
    )
    ipl = pd.DataFrame({"player_id": list("abcd"), "target_year": 2021, "ipl_val": ipl_val})
    return lambda sql: dom.copy() if "domestic_translation_features" in sql else ipl.copy()


def test_performance_identity_zero_error_and_constant_reference(monkeypatch):
    monkeypatch.setattr(b, "_q", _fake_q([1, 2, 3, 4], [0.25, 0.5, 0.75, 1.0], [1, 2, 3, 4]))
    m = b.performance_baseline()["metrics"]["strike_rate"]
    assert m["n"] == 4
    assert np.isclose(m["identity"]["mae"], 0.0)
    assert np.isclose(m["constant_0_5"]["mae"], 0.25)


def test_performance_detects_percent_scale_and_reversed_orientation(monkeypatch):
    monkeypatch.setattr(b, "_q", _fake_q([4, 3, 2, 1], [25, 50, 75, 100], [4, 3, 2, 1]))
    m = b.performance_baseline()["metrics"]["economy_rate"]
    assert m["domestic_pct_scale_divisor"] == 100.0
    assert m["pct_orientation_corr_with_raw"] < 0
    assert np.isclose(m["identity"]["mae"], 0.0)
