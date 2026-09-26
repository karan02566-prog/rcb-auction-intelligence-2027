"""Tests for Phase 6.2 performance threshold and role alignment filtering."""
import numpy as np
import pandas as pd

from src.analytics.funnel_performance import apply_stage2_filter


def _stage1_row(player_id, meets_bat=False, meets_bowl=False):
    return {
        "player_id": player_id,
        "passes_stage1": True,
        "meets_batting_threshold": meets_bat,
        "meets_bowling_threshold": meets_bowl,
    }


def test_batter_below_median_fails_stage2():
    stage1 = pd.DataFrame([_stage1_row("a", meets_bat=True), _stage1_row("b", meets_bat=True)])
    adj_bat = pd.DataFrame({"player_id": ["a", "b"], "adjusted_batting_avg": [20.0, 40.0]})
    adj_bowl = pd.DataFrame({"player_id": [], "adjusted_economy": []})
    result = apply_stage2_filter(stage1, adj_bat, adj_bowl)
    # median of [20, 40] = 30; a (20) is below median -> fails, b (40) passes
    assert result.loc[result["player_id"] == "a", "passes_stage2"].iloc[0] == False
    assert result.loc[result["player_id"] == "b", "passes_stage2"].iloc[0] == True


def test_bowler_lower_economy_is_better():
    stage1 = pd.DataFrame([_stage1_row("a", meets_bowl=True), _stage1_row("b", meets_bowl=True)])
    adj_bat = pd.DataFrame({"player_id": [], "adjusted_batting_avg": []})
    adj_bowl = pd.DataFrame({"player_id": ["a", "b"], "adjusted_economy": [6.0, 10.0]})
    result = apply_stage2_filter(stage1, adj_bat, adj_bowl)
    # median = 8.0; a (6.0, lower/better) passes, b (10.0, higher/worse) fails
    assert result.loc[result["player_id"] == "a", "passes_stage2"].iloc[0] == True
    assert result.loc[result["player_id"] == "b", "passes_stage2"].iloc[0] == False


def test_never_dismissed_batter_passes_automatically():
    stage1 = pd.DataFrame([_stage1_row("a", meets_bat=True), _stage1_row("b", meets_bat=True)])
    adj_bat = pd.DataFrame({"player_id": ["a", "b"], "adjusted_batting_avg": [np.nan, 40.0]})
    adj_bowl = pd.DataFrame({"player_id": [], "adjusted_economy": []})
    result = apply_stage2_filter(stage1, adj_bat, adj_bowl)
    # a has NaN avg (never dismissed) -- must pass, not fail a NaN comparison
    assert result.loc[result["player_id"] == "a", "passes_stage2"].iloc[0] == True


def test_allrounder_passes_on_either_discipline():
    stage1 = pd.DataFrame([_stage1_row("a", meets_bat=True, meets_bowl=True)])
    adj_bat = pd.DataFrame({"player_id": ["a"], "adjusted_batting_avg": [5.0]})   # weak batting
    adj_bowl = pd.DataFrame({"player_id": ["a"], "adjusted_economy": [6.0]})       # strong bowling
    result = apply_stage2_filter(stage1, adj_bat, adj_bowl)
    # only one player exists so they ARE the median in both disciplines -- passes on both trivially,
    # key point is the function doesn't crash combining both eligible disciplines for one player
    assert result.loc[result["player_id"] == "a", "passes_stage2"].iloc[0] == True


def test_player_ineligible_in_both_disciplines_fails():
    stage1 = pd.DataFrame([_stage1_row("a", meets_bat=False, meets_bowl=False)])
    adj_bat = pd.DataFrame({"player_id": [], "adjusted_batting_avg": []})
    adj_bowl = pd.DataFrame({"player_id": [], "adjusted_economy": []})
    result = apply_stage2_filter(stage1, adj_bat, adj_bowl)
    assert result.loc[result["player_id"] == "a", "passes_stage2"].iloc[0] == False
