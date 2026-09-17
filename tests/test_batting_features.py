"""Unit tests for Phase 4.1 batting features."""

import numpy as np
import pandas as pd

from src.features.batting import compute_batting_features, validate_boundary_dependency


def _row(match, innings, batter, batter_id, runs, is_legal=1, four=0, six=0, dot=0,
         phase="Middle", dismissal_count=0, dismissal_type=pd.NA, dismissal_player_out=None,
         start_year=2024):
    if dismissal_count and dismissal_player_out is None:
        dismissal_player_out = batter
    if dismissal_player_out is None:
        dismissal_player_out = pd.NA
    return {
        "match_id": match,
        "innings_number": innings,
        "batter": batter,
        "non_striker": "NS",
        "batter_canonical_id": batter_id,
        "batter_canonical_name": batter,
        "batter_runs": runs,
        "is_legal_delivery": is_legal,
        "is_boundary_four": four,
        "is_boundary_six": six,
        "is_dot_ball": dot,
        "phase": phase,
        "dismissal_count": dismissal_count,
        "dismissal_type": dismissal_type,
        "dismissal_player_out": dismissal_player_out,
        "competition": "ipl",
        "competition_canonical": "ipl",
        "competition_category": "IPL",
        "start_year": start_year,
    }


def test_zero_balls_faced_no_crash_and_zero_rates():
    """Player with a row but 0 legal balls faced (e.g. run-out non-striker,
    never faced) should get 0.0 rates, not a crash or inf/NaN."""
    rows = [_row("m1", 1, "A", "a", runs=0, is_legal=0, dot=0)]
    fact = pd.DataFrame(rows)
    feats = compute_batting_features(fact, exact_lookup={}, norm_lookup={})
    row = feats.iloc[0]
    assert row["balls_faced"] == 0
    assert row["strike_rate"] == 0.0
    assert row["dot_pct"] == 0.0
    assert row["boundary_pct"] == 0.0
    assert row["rotation_rate"] == 0.0
    assert row["boundary_dependency"] == 0.0


def test_zero_runs_boundary_dependency_is_zero():
    """Batter faces balls, scores 0 runs (out for a duck): dep must be 0.0,
    not NaN/inf, and must satisfy the [0,1] bound."""
    rows = [
        _row("m1", 1, "A", "a", runs=0, dot=1),
        _row("m1", 1, "A", "a", runs=0, dot=1, dismissal_count=1, dismissal_type="bowled"),
    ]
    fact = pd.DataFrame(rows)
    feats = compute_batting_features(fact, exact_lookup={}, norm_lookup={})
    row = feats.iloc[0]
    assert row["runs"] == 0
    assert row["boundary_dependency"] == 0.0
    validate_boundary_dependency(feats)  # should not raise


def test_boundary_dependency_bounds_with_mixed_scoring():
    """4 dots + 2 fours + 1 six = 14 runs off 7 balls; boundary runs = 8+6=14
    -> dependency should be exactly 1.0 (every run came from a boundary)."""
    rows = (
        [_row("m1", 1, "A", "a", runs=0, dot=1) for _ in range(4)]
        + [_row("m1", 1, "A", "a", runs=4, four=1) for _ in range(2)]
        + [_row("m1", 1, "A", "a", runs=6, six=1)]
    )
    fact = pd.DataFrame(rows)
    feats = compute_batting_features(fact, exact_lookup={}, norm_lookup={})
    row = feats.iloc[0]
    assert row["runs"] == 14
    assert row["boundary_dependency"] == 1.0
    validate_boundary_dependency(feats)


def test_rotation_rate_correctness():
    """2 singles + 1 double + 1 dot + 1 four = 5 balls, 1 boundary ball
    -> non_boundary_balls = 4, rotation = (2+1)/4 = 0.75."""
    rows = (
        [_row("m1", 1, "A", "a", runs=1) for _ in range(2)]
        + [_row("m1", 1, "A", "a", runs=2)]
        + [_row("m1", 1, "A", "a", runs=0, dot=1)]
        + [_row("m1", 1, "A", "a", runs=4, four=1)]
    )
    fact = pd.DataFrame(rows)
    feats = compute_batting_features(fact, exact_lookup={}, norm_lookup={})
    row = feats.iloc[0]
    assert row["rotation_rate"] == 0.75


def test_batting_average_nan_when_never_out():
    """0 dismissals across the season -> average must be NaN, not 0 or inf."""
    rows = [_row("m1", 1, "A", "a", runs=10)]
    fact = pd.DataFrame(rows)
    feats = compute_batting_features(fact, exact_lookup={}, norm_lookup={})
    assert np.isnan(feats.iloc[0]["batting_average"])


def test_batting_average_correct_when_dismissed():
    rows = [
        _row("m1", 1, "A", "a", runs=20, dismissal_count=1, dismissal_type="bowled"),
        _row("m2", 1, "A", "a", runs=10),  # not out
    ]
    fact = pd.DataFrame(rows)
    feats = compute_batting_features(fact, exact_lookup={}, norm_lookup={})
    row = feats.iloc[0]
    assert row["dismissals"] == 1
    assert row["runs"] == 30
    assert row["batting_average"] == 30.0


def test_acceleration_rate_death_minus_powerplay():
    rows = (
        [_row("m1", 1, "A", "a", runs=1, phase="Powerplay") for _ in range(10)]
        + [_row("m1", 1, "A", "a", runs=2, phase="Death") for _ in range(10)]
    )
    fact = pd.DataFrame(rows)
    feats = compute_batting_features(fact, exact_lookup={}, norm_lookup={})
    row = feats.iloc[0]
    # Powerplay SR = 100.0, Death SR = 200.0 -> acceleration = 100.0
    assert row["acceleration_rate"] == 100.0


def test_acceleration_rate_nan_when_phase_missing():
    rows = [_row("m1", 1, "A", "a", runs=1, phase="Powerplay") for _ in range(5)]
    fact = pd.DataFrame(rows)
    feats = compute_batting_features(fact, exact_lookup={}, norm_lookup={})
    assert np.isnan(feats.iloc[0]["acceleration_rate"])
