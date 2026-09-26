"""Tests for Phase 6.1 universe definition and Stage 1 sample filtering."""
import pandas as pd

from src.analytics.funnel_sample import (
    build_universe,
    apply_stage1_filter,
    MIN_BATTING_BALLS,
    MIN_BOWLING_BALLS,
)


def test_build_universe_outer_joins_batters_and_bowlers():
    bat = pd.DataFrame({"player_id": ["a", "b"], "player_name": ["A", "B"], "balls_faced": [200, 50]})
    bowl = pd.DataFrame({"player_id": ["b", "c"], "player_name": ["B", "C"], "legal_balls": [90, 120]})
    universe = build_universe(bat, bowl)

    assert set(universe["player_id"]) == {"a", "b", "c"}
    # pure batter 'a' has zero bowling balls, not NaN/missing
    a_row = universe.loc[universe["player_id"] == "a"].iloc[0]
    assert a_row["bowling_legal_balls_recent"] == 0
    # pure bowler 'c' has zero batting balls
    c_row = universe.loc[universe["player_id"] == "c"].iloc[0]
    assert c_row["batting_balls_faced_recent"] == 0


def test_stage1_filter_passes_on_either_threshold_not_both():
    df = pd.DataFrame({
        "player_id": ["specialist_bat", "specialist_bowl", "neither", "both"],
        "batting_balls_faced_recent": [MIN_BATTING_BALLS, 0, 10, MIN_BATTING_BALLS],
        "bowling_legal_balls_recent": [0, MIN_BOWLING_BALLS, 5, MIN_BOWLING_BALLS],
    })
    result = apply_stage1_filter(df)

    assert result.loc[result["player_id"] == "specialist_bat", "passes_stage1"].iloc[0] == True
    assert result.loc[result["player_id"] == "specialist_bowl", "passes_stage1"].iloc[0] == True
    assert result.loc[result["player_id"] == "neither", "passes_stage1"].iloc[0] == False
    assert result.loc[result["player_id"] == "both", "passes_stage1"].iloc[0] == True


def test_stage1_filter_boundary_is_inclusive():
    df = pd.DataFrame({
        "player_id": ["exact_bat", "one_under_bat"],
        "batting_balls_faced_recent": [MIN_BATTING_BALLS, MIN_BATTING_BALLS - 1],
        "bowling_legal_balls_recent": [0, 0],
    })
    result = apply_stage1_filter(df)
    assert result.loc[result["player_id"] == "exact_bat", "passes_stage1"].iloc[0] == True
    assert result.loc[result["player_id"] == "one_under_bat", "passes_stage1"].iloc[0] == False
