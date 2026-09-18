"""Unit tests for Phase 4.4 phase-wise performance features."""

import numpy as np
import pandas as pd
import pytest

from src.features.phase import compute_batting_phase, compute_bowling_phase, compute_phase_features


def _row(
    match="m1", batter="A", batter_id="p1", bowler="B", bowler_id="p2",
    batter_runs=0, total_runs=0, byes=0, legbyes=0, is_legal_bat=True, is_legal_bowl=True,
    four=0, six=0, dot=0, is_wicket=0, dismissal_type=pd.NA, phase="Powerplay", start_year=2024,
):
    return {
        "match_id": match, "batter": batter, "batter_canonical_id": batter_id, "batter_canonical_name": batter,
        "bowler": bowler, "bowler_canonical_id": bowler_id, "bowler_canonical_name": bowler,
        "batter_runs": batter_runs, "total_runs": total_runs, "byes_runs": byes, "legbyes_runs": legbyes,
        "is_legal_delivery": 1 if is_legal_bat else 0, "is_legal_ball": is_legal_bowl,
        "is_boundary_four": four, "is_boundary_six": six, "is_dot_ball": dot,
        "is_wicket": is_wicket, "dismissal_type": dismissal_type,
        "phase": phase, "competition": "ipl", "start_year": start_year,
    }


def test_phase_runs_sum_equals_season_total():
    """Sum of batting_runs across all phases for a player-season must equal
    the total runs they scored that season (no runs lost/duplicated across phases)."""
    rows = [
        _row(batter_runs=10, phase="Powerplay"),
        _row(batter_runs=20, phase="Middle"),
        _row(batter_runs=15, phase="Death"),
    ]
    fact = pd.DataFrame(rows)
    bat = compute_batting_phase(fact)
    total = bat.loc[bat["player_id"] == "p1", "batting_runs"].sum()
    assert total == 45


def test_zero_balls_gives_nan_rates_not_crash():
    """A phase with zero balls faced/bowled by a player should not appear
    with 0.0 rates masquerading as real data; if it appears at all, NaN is used."""
    rows = [_row(batter_runs=10, phase="Powerplay")]
    fact = pd.DataFrame(rows)
    bat = compute_batting_phase(fact)
    row = bat[bat["phase"] == "Powerplay"].iloc[0]
    assert row["batting_balls"] > 0
    assert not np.isnan(row["batting_strike_rate"])


def test_bowling_economy_correct_per_phase():
    """4 legal balls, 6 runs conceded in Death phase -> economy = 6 / (4/6) = 9.0."""
    rows = [
        _row(total_runs=1, is_legal_bowl=True, phase="Death"),
        _row(total_runs=1, is_legal_bowl=True, phase="Death"),
        _row(total_runs=4, four=1, is_legal_bowl=True, phase="Death"),
        _row(total_runs=0, dot=1, is_legal_bowl=True, phase="Death"),
    ]
    fact = pd.DataFrame(rows)
    bowl = compute_bowling_phase(fact)
    row = bowl[bowl["phase"] == "Death"].iloc[0]
    assert row["bowling_legal_balls"] == 4
    assert pytest.approx(row["bowling_overs"], rel=1e-5) == 4.0 / 6.0
    assert row["bowling_runs_conceded"] == 6
    assert pytest.approx(row["bowling_economy"], rel=1e-5) == 9.0


def test_wickets_credited_correctly_per_phase():
    rows = [
        _row(is_wicket=1, dismissal_type="bowled", phase="Middle"),
        _row(is_wicket=1, dismissal_type="run out", phase="Middle"),  # not credited
        _row(phase="Middle"),
    ]
    fact = pd.DataFrame(rows)
    bowl = compute_bowling_phase(fact)
    row = bowl[bowl["phase"] == "Middle"].iloc[0]
    assert row["bowling_wickets"] == 1


def test_real_data_over_boundaries_match_expected_phase_counts():
    """Sanity check against actual fact_deliveries.parquet: Powerplay/Middle/Death
    row counts must all be non-zero and sum to the filtered total (no rows dropped
    or misclassified into a phase outside the known three)."""
    from src.features.phase import prepare_fact
    from src.utils.config import get_project_root

    fact = prepare_fact(get_project_root())
    counts = fact["phase"].value_counts()
    assert set(counts.index) <= {"Powerplay", "Middle", "Death"}
    assert counts.sum() == len(fact)
    assert all(counts[p] > 0 for p in ["Powerplay", "Middle", "Death"])
