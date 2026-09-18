"""Unit tests for Phase 4.9 league-strength adjustment features."""

import numpy as np
import pandas as pd
import pytest

from src.analytics.league_adjustment import (
    MIN_DISMISSALS_BATTING,
    MIN_OVERS_BOWLING,
    compute_batting_strength_factors,
    compute_bowling_strength_factors,
)


def test_ipl_baseline_factor_is_one():
    """IPL must always have M_batting == 1.0 and M_bowling == 1.0 by definition."""
    bat_df = pd.DataFrame({
        "player_id": ["p1"] * 6,
        "competition": ["ipl"] * 6,
        "batting_avg": [30.0] * 6,
        "dismissals": [MIN_DISMISSALS_BATTING] * 6,
    })
    factors = compute_batting_strength_factors(bat_df)
    assert factors["ipl"]["M_batting"] == 1.0

    bowl_df = pd.DataFrame({
        "player_id": ["p1"],
        "competition": ["ipl"],
        "economy": [8.0],
        "overs": [MIN_OVERS_BOWLING],
    })
    bowl_factors = compute_bowling_strength_factors(bowl_df)
    assert bowl_factors["ipl"]["M_bowling"] == 1.0


def test_lower_tier_league_gets_correct_direction_factor():
    """Synthetic case: crossover players score exactly 2x as much in league X as
    in IPL -> raw_ratio = 2.0 -> M_batting should be 1/2.0 = 0.5 (scales down
    the inflated stat to an IPL-equivalent)."""
    bat_df = pd.DataFrame({
        "player_id": ["p1", "p1", "p2", "p2"],
        "competition": ["ipl", "leagueX", "ipl", "leagueX"],
        "batting_avg": [20.0, 40.0, 30.0, 60.0],
        "dismissals": [MIN_DISMISSALS_BATTING] * 4,
    })
    factors = compute_batting_strength_factors(bat_df)
    assert pytest.approx(factors["leagueX"]["M_batting"], rel=1e-5) == 0.5
    assert factors["leagueX"]["n_crossover_players_batting"] == 2


def test_min_sample_threshold_excludes_low_sample_players():
    """A player with fewer dismissals than MIN_DISMISSALS_BATTING must not count
    as a crossover player for the ratio calculation."""
    bat_df = pd.DataFrame({
        "player_id": ["p1", "p1"],
        "competition": ["ipl", "leagueX"],
        "batting_avg": [20.0, 40.0],
        "dismissals": [1, 1],  # below MIN_DISMISSALS_BATTING
    })
    factors = compute_batting_strength_factors(bat_df)
    assert factors["leagueX"]["n_crossover_players_batting"] == 0
    assert factors["leagueX"]["M_batting"] is None
    assert factors["leagueX"]["note_batting"] is not None


def test_no_crossover_players_gives_null_not_default_one():
    """A league with zero qualifying crossover players must get an explicit
    null factor and a note, never silently default to 1.0."""
    bat_df = pd.DataFrame({
        "player_id": ["p1"],
        "competition": ["leagueX"],
        "batting_avg": [40.0],
        "dismissals": [MIN_DISMISSALS_BATTING],
    })
    factors = compute_batting_strength_factors(bat_df)
    assert factors["leagueX"]["M_batting"] is None
    assert factors["leagueX"]["note_batting"] == "no qualified crossover players; factor unadjustable"


def test_bowling_factor_direction_is_correct():
    """Synthetic case: crossover bowlers concede exactly half the runs-per-over
    in league X vs IPL -> raw_ratio = 0.5 -> M_bowling should be 1/0.5 = 2.0
    (scales the deflated economy UP to an IPL-equivalent, harsher value)."""
    bowl_df = pd.DataFrame({
        "player_id": ["p1", "p1"],
        "competition": ["ipl", "leagueX"],
        "economy": [8.0, 4.0],
        "overs": [MIN_OVERS_BOWLING] * 2,
    })
    factors = compute_bowling_strength_factors(bowl_df)
    assert pytest.approx(factors["leagueX"]["M_bowling"], rel=1e-5) == 2.0
