import json
import warnings

import numpy as np
import pandas as pd

from src.models import train_price_model as t


def test_ridge_recovers_linear_relation():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, 2))
    y = 3 * X[:, 0] - 2 * X[:, 1] + 1
    m = t.fit_ridge(X, y, 1e-6)
    assert np.allclose(t.predict(m, X), y, atol=1e-3)


def test_all_nan_column_is_handled_without_warning():
    X = np.array([[1.0, np.nan], [2.0, np.nan], [3.0, np.nan], [4.0, np.nan]])
    y = np.array([1.0, 2.0, 3.0, 4.0])
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        m = t.fit_ridge(X, y, 0.1)
        p = t.predict(m, X)
    assert np.isfinite(p).all()


def test_to_inr_clips_negative_and_inverts_log1p():
    out = t.to_inr(np.array([-5.0, 0.0, np.log1p(100.0)]))
    assert np.allclose(out, [0.0, 0.0, 100.0])


def test_build_dataset_prior_price_is_strictly_earlier(monkeypatch, tmp_path):
    auction = pd.DataFrame(
        {
            "player_name": ["X", "X", "Y", "Z"],
            "year": [2015, 2017, 2016, 2017],
            "sold_price": [100.0, 400.0, 300.0, 50.0],
        }
    )
    mapping = {"mapped": [{"source_name": "X", "canonical_id": "idx"}, {"source_name": "Y", "canonical_id": "idy"}]}
    p = tmp_path / "m.json"
    p.write_text(json.dumps(mapping))
    monkeypatch.setattr(t, "load_auction", lambda: auction.copy())
    monkeypatch.setattr(t, "MAPPING", p)
    d = t.build_dataset()
    assert set(d.player_id) == {"idx", "idy"}
    x17 = d[(d.player_id == "idx") & (d.year == 2017)].iloc[0]
    assert np.isclose(x17.prev_log_price, np.log1p(100.0))
    assert x17.years_since_prev == 2 and x17.has_prev_price == 1.0
    assert np.isclose(x17.market_prev_median_log, np.log1p(300.0))
    x15 = d[(d.player_id == "idx") & (d.year == 2015)].iloc[0]
    assert x15.has_prev_price == 0.0


def test_perf_features_exclude_auction_year_and_respect_window(monkeypatch):
    bat = pd.DataFrame({"player_id": ["p", "p"], "start_year": [2020, 2021], "runs": [150, 1000], "balls_faced": [100, 1000]})
    bowl = pd.DataFrame(
        {"player_id": ["p", "p"], "start_year": [2020, 2021], "runs_conceded": [0, 0], "legal_balls": [0, 0], "wickets": [0, 0]}
    )

    def fake_tab(file, scope, cols):
        base = bat if file == "batting_features.parquet" else bowl
        return base[["player_id", "start_year"] + cols].copy()

    monkeypatch.setattr(t, "_tab", fake_tab)
    a = pd.DataFrame({"player_id": ["p", "p"], "year": [2021, 2022]})
    out = t.add_perf_features(a).set_index("year")
    assert np.isclose(out.loc[2021, "t20_bat_sr"], 150.0)  # 2021 season excluded for a 2021 auction
    assert np.isclose(out.loc[2022, "t20_bat_sr"], 100 * 1150 / 1100)
    assert out.loc[2021, "has_t20_prior"] == 1.0


def test_cv_alpha_returns_grid_value_with_finite_scores():
    rng = np.random.default_rng(1)
    df = pd.DataFrame({"year": np.repeat(np.arange(2015, 2024), 20), "x": rng.normal(size=180)})
    df["log_price"] = 2 * df.x + 0.1 * rng.normal(size=180)
    alpha, scores = t.cv_alpha(df, ["x"])
    assert alpha in t.ALPHAS
    assert all(np.isfinite(v) for v in scores.values())
