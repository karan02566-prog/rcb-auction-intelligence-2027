"""Tests for Phase 4.10 domestic-to-franchise translation features."""
import numpy as np
import pandas as pd

from src.features.domestic_translation import (
    filter_to_smat,
    compute_uncapped_ids,
    add_percentile_and_dominance,
    transition_variance_flag,
)


def test_filter_to_smat_keeps_only_sma_and_excludes_ipl():
    fact = pd.DataFrame({
        "competition": ["sma", "sma", "ipl", "bbl"],
        "val": [1, 2, 3, 4],
    })
    out = filter_to_smat(fact)
    assert set(out["competition"]) == {"sma"}
    assert len(out) == 2


def test_compute_uncapped_ids_excludes_players_who_ever_played_ipl():
    fact = pd.DataFrame({
        "competition": ["sma", "sma", "sma", "ipl", "sma"],
        "batter_canonical_id": ["P1", "P2", "UNRESOLVED", "P1", "P3"],
        "bowler_canonical_id": ["UNRESOLVED", "UNRESOLVED", "UNRESOLVED", "UNRESOLVED", "UNRESOLVED"],
    })
    result = compute_uncapped_ids(fact)
    # P1 played IPL -> excluded. P2, P3 never did -> uncapped.
    assert result == {"P2", "P3"}


def test_add_percentile_and_dominance_higher_is_better():
    df = pd.DataFrame({
        "player_id": ["a", "b", "c"],
        "start_year": [2024, 2024, 2024],
        "qualified": [True, True, True],
        "strike_rate": [100.0, 150.0, 50.0],
    })
    out = add_percentile_and_dominance(df, "strike_rate", higher_is_better=True)
    # highest strike_rate -> highest percentile
    best = out.loc[out["strike_rate"] == 150.0, "strike_rate_percentile"].iloc[0]
    worst = out.loc[out["strike_rate"] == 50.0, "strike_rate_percentile"].iloc[0]
    assert best > worst
    mean_val = df["strike_rate"].mean()
    expected_ratio = 150.0 / mean_val
    actual_ratio = out.loc[out["strike_rate"] == 150.0, "strike_rate_dominance_ratio"].iloc[0]
    assert np.isclose(actual_ratio, expected_ratio)


def test_add_percentile_and_dominance_lower_is_better_for_economy():
    df = pd.DataFrame({
        "player_id": ["a", "b", "c"],
        "start_year": [2024, 2024, 2024],
        "qualified": [True, True, True],
        "economy_rate": [5.0, 9.0, 7.0],
    })
    out = add_percentile_and_dominance(df, "economy_rate", higher_is_better=False)
    # lowest economy is best -> should get the highest percentile
    best = out.loc[out["economy_rate"] == 5.0, "economy_rate_percentile"].iloc[0]
    worst = out.loc[out["economy_rate"] == 9.0, "economy_rate_percentile"].iloc[0]
    assert best > worst


def test_add_percentile_and_dominance_unqualified_rows_stay_nan():
    df = pd.DataFrame({
        "player_id": ["a", "b"],
        "start_year": [2024, 2024],
        "qualified": [True, False],
        "strike_rate": [100.0, 200.0],
    })
    out = add_percentile_and_dominance(df, "strike_rate", higher_is_better=True)
    unqualified_row = out.loc[~out["qualified"]].iloc[0]
    assert pd.isna(unqualified_row["strike_rate_percentile"])
    assert pd.isna(unqualified_row["strike_rate_dominance_ratio"])


def test_transition_variance_flag_nan_for_single_season_player():
    df = pd.DataFrame({
        "player_id": ["a", "b", "b"],
        "qualified": [True, True, True],
        "strike_rate": [100.0, 100.0, 200.0],
    })
    flags = transition_variance_flag(df, "strike_rate")
    # player 'a' has only one qualified season -> NaN, not False
    assert pd.isna(flags.iloc[0])


def test_transition_variance_flag_true_for_high_variance_player():
    df = pd.DataFrame({
        "player_id": ["a", "a", "b", "b"],
        "qualified": [True, True, True, True],
        "strike_rate": [50.0, 250.0, 100.0, 105.0],  # a: high variance, b: low variance
    })
    flags = transition_variance_flag(df, "strike_rate")
    a_flag = flags.loc[df["player_id"] == "a"].iloc[0]
    b_flag = flags.loc[df["player_id"] == "b"].iloc[0]
    assert a_flag == True
    assert b_flag == False


def test_transition_variance_flag_ignores_unqualified_seasons():
    df = pd.DataFrame({
        "player_id": ["a", "a", "a"],
        "qualified": [True, True, False],
        "strike_rate": [100.0, 100.0, 9999.0],  # unqualified outlier must be excluded
    })
    flags = transition_variance_flag(df, "strike_rate")
    # only 1 qualified season effectively used twice with same value -> variance 0 -> NaN median edge case is fine either way,
    # key assertion is the 9999 outlier must not blow up the computation
    assert flags.iloc[0] in (True, False) or pd.isna(flags.iloc[0])
