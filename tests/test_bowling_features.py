"""Unit tests for Phase 4.2 bowling features."""

import numpy as np
import pandas as pd
import pytest

from src.features.bowling import (
    QUALIFIED_OVERS_SEASON,
    compute_bowling_features,
    compute_spell_variance,
)


def _row(
    match="m1",
    innings=1,
    over_number=0,
    bowler="Bowler A",
    bowler_id="b1",
    total_runs=0,
    byes=0,
    legbyes=0,
    is_legal=True,
    four=0,
    six=0,
    dot=0,
    is_wicket=0,
    dismissal_type=pd.NA,
    start_year=2024,
):
    return {
        "match_id": match,
        "innings_number": innings,
        "over_number": over_number,
        "bowler": bowler,
        "bowler_canonical_id": bowler_id,
        "bowler_canonical_name": bowler,
        "total_runs": total_runs,
        "byes_runs": byes,
        "legbyes_runs": legbyes,
        "is_legal_ball": is_legal,
        "is_boundary_four": four,
        "is_boundary_six": six,
        "is_dot_ball": dot,
        "is_wicket": is_wicket,
        "dismissal_type": dismissal_type,
        "competition": "ipl",
        "start_year": start_year,
    }


def test_zero_wickets_strike_rate_is_nan():
    """0 wickets across the season -> bowling_strike_rate must be NaN, not 0.0 or inf."""
    rows = [_row(total_runs=1, is_legal=True) for _ in range(6)]
    fact = pd.DataFrame(rows)
    feats = compute_bowling_features(fact)
    row = feats.iloc[0]
    assert row["wickets"] == 0
    assert np.isnan(row["bowling_strike_rate"])
    assert row["economy_rate"] == 1.0 * 6  # 6 runs in 1 over = 6.0 econ


def test_zero_overs_bowled_no_crash_and_guarded_rates():
    """Bowler with 0 legal balls bowled (e.g. only illegal deliveries or empty record)
    should get 0.0 economy, 0.0 overs, and NaN strike rate without crashing."""
    rows = [_row(total_runs=1, is_legal=False)]
    fact = pd.DataFrame(rows)
    feats = compute_bowling_features(fact)
    row = feats.iloc[0]
    assert row["legal_balls"] == 0
    assert row["overs_bowled"] == 0.0
    assert row["economy_rate"] == 0.0
    assert row["dot_ball_pct"] == 0.0
    assert row["boundary_concession_pct"] == 0.0
    assert row["wicket_rate_per_over"] == 0.0
    assert np.isnan(row["bowling_strike_rate"])


def test_partial_over_arithmetic_and_economy():
    """Partial-over arithmetic: 4 legal balls = 4/6 = 0.666667 overs.
    If 6 runs conceded in 4 balls, economy = 6 / (4/6) = 9.0."""
    rows = [_row(total_runs=1, is_legal=True) for _ in range(2)] + [
        _row(total_runs=4, four=1, is_legal=True),
        _row(total_runs=0, dot=1, is_legal=True),
    ]
    fact = pd.DataFrame(rows)
    feats = compute_bowling_features(fact)
    row = feats.iloc[0]
    assert row["legal_balls"] == 4
    assert pytest.approx(row["overs_bowled"], rel=1e-5) == 4.0 / 6.0
    assert row["runs_conceded"] == 6
    assert pytest.approx(row["economy_rate"], rel=1e-5) == 9.0


def test_runs_conceded_excludes_byes_legbyes_includes_wides_noballs():
    """Runs conceded excludes byes and legbyes, but includes wides/noballs and off-the-bat runs.
    E.g. total 10 runs with 4 byes and 2 legbyes -> bowler conceded = 4 runs."""
    rows = [
        _row(total_runs=4, byes=4, is_legal=True),  # 0 bowler runs
        _row(total_runs=2, legbyes=2, is_legal=True),  # 0 bowler runs
        _row(total_runs=3, byes=0, legbyes=0, is_legal=True),  # 3 bowler runs
        _row(total_runs=1, byes=0, legbyes=0, is_legal=False),  # 1 wide/noball run (illegal)
    ]
    fact = pd.DataFrame(rows)
    feats = compute_bowling_features(fact)
    row = feats.iloc[0]
    assert row["runs_conceded"] == 4  # (4-4) + (2-2) + 3 + 1 = 4
    assert row["legal_balls"] == 3
    assert pytest.approx(row["economy_rate"], rel=1e-5) == 4.0 / (3.0 / 6.0)  # 8.0


def test_boundary_concession_pct_correctness():
    """4 dots + 2 fours + 1 six + 3 singles = 10 legal balls.
    Boundary concession % = (2+1)/10 * 100 = 30.0%."""
    rows = (
        [_row(total_runs=0, dot=1, is_legal=True) for _ in range(4)]
        + [_row(total_runs=4, four=1, is_legal=True) for _ in range(2)]
        + [_row(total_runs=6, six=1, is_legal=True)]
        + [_row(total_runs=1, is_legal=True) for _ in range(3)]
    )
    fact = pd.DataFrame(rows)
    feats = compute_bowling_features(fact)
    row = feats.iloc[0]
    assert row["legal_balls"] == 10
    assert row["dot_ball_pct"] == 40.0
    assert row["boundary_concession_pct"] == 30.0


def test_credited_vs_non_credited_wickets():
    """Bowler credited wickets: bowled, caught, lbw, stumped, hit wicket, caught and bowled.
    Run outs / retired out must NOT be credited to the bowler."""
    rows = [
        _row(is_wicket=1, dismissal_type="caught", is_legal=True),
        _row(is_wicket=1, dismissal_type="bowled", is_legal=True),
        _row(is_wicket=1, dismissal_type="run out", is_legal=True),  # Not credited
        _row(is_wicket=1, dismissal_type="retired hurt", is_legal=True),  # Not credited
        _row(is_legal=True),
        _row(is_legal=True),
    ]
    fact = pd.DataFrame(rows)
    feats = compute_bowling_features(fact)
    row = feats.iloc[0]
    assert row["wickets"] == 2
    assert row["legal_balls"] == 6
    assert row["bowling_strike_rate"] == 3.0  # 6 balls / 2 wickets


def test_synthetic_multi_spell_case_variance():
    """Bowler bowls 2 spells in the same match:
    - Spell 1: Over 0 (runs=6) & Over 1 (runs=6) -> 2 overs, 12 runs, economy = 6.0
    - Gap (Over 2 bowled by someone else)
    - Spell 2: Over 3 (runs=12) -> 1 over, 12 runs, economy = 12.0
    Mean economy = 9.0.
    Population variance (ddof=0) = ((6-9)^2 + (12-9)^2) / 2 = (9 + 9) / 2 = 9.0."""
    rows = [
        # Spell 1, Over 0 (6 runs, 6 balls)
        *[_row(match="m1", innings=1, over_number=0, total_runs=1, is_legal=True) for _ in range(6)],
        # Spell 1, Over 1 (6 runs, 6 balls)
        *[_row(match="m1", innings=1, over_number=1, total_runs=1, is_legal=True) for _ in range(6)],
        # Spell 2, Over 3 (12 runs, 6 balls)
        *[_row(match="m1", innings=1, over_number=3, total_runs=2, is_legal=True) for _ in range(6)],
    ]
    fact = pd.DataFrame(rows)
    var_df = compute_spell_variance(fact)
    assert len(var_df) == 1
    assert pytest.approx(var_df.iloc[0]["economy_variance_across_spells"], rel=1e-5) == 9.0

    feats = compute_bowling_features(fact)
    assert pytest.approx(feats.iloc[0]["economy_variance_across_spells"], rel=1e-5) == 9.0


def test_single_spell_variance_is_zero():
    """A single spell in a season should produce variance = 0.0."""
    rows = [_row(match="m1", innings=1, over_number=0, total_runs=1, is_legal=True) for _ in range(6)]
    fact = pd.DataFrame(rows)
    feats = compute_bowling_features(fact)
    assert feats.iloc[0]["economy_variance_across_spells"] == 0.0
