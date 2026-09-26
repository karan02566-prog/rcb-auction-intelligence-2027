"""Tests for Phase 6.4 pitch adaptability filtering (Chinnaswamy-only scope)."""
import numpy as np
import pandas as pd

from src.analytics.funnel_adaptability import apply_stage4_filter, MIN_CHINNASWAMY_BALLS


def _stage3_row(player_id):
    return {"player_id": player_id, "passes_stage3": True}


def test_unsampled_candidate_passes_through_untested():
    stage3 = pd.DataFrame([_stage3_row("a")])
    chinna_bat = pd.DataFrame({"player_id": [], "balls_faced": [], "chinnaswamy_strike_rate": []})
    chinna_bowl = pd.DataFrame({"player_id": [], "legal_balls": [], "chinnaswamy_economy": []})
    result = apply_stage4_filter(stage3, chinna_bat, chinna_bowl)
    assert result.loc[result["player_id"] == "a", "passes_stage4"].iloc[0] == True


def test_sampled_batter_below_median_fails():
    stage3 = pd.DataFrame([_stage3_row("a"), _stage3_row("b")])
    chinna_bat = pd.DataFrame({
        "player_id": ["a", "b"],
        "balls_faced": [MIN_CHINNASWAMY_BALLS, MIN_CHINNASWAMY_BALLS],
        "chinnaswamy_strike_rate": [100.0, 200.0],
    })
    chinna_bowl = pd.DataFrame({"player_id": [], "legal_balls": [], "chinnaswamy_economy": []})
    result = apply_stage4_filter(stage3, chinna_bat, chinna_bowl)
    # median = 150; a (100) below -> fails, b (200) passes
    assert result.loc[result["player_id"] == "a", "passes_stage4"].iloc[0] == False
    assert result.loc[result["player_id"] == "b", "passes_stage4"].iloc[0] == True


def test_sampled_bowler_lower_economy_passes():
    stage3 = pd.DataFrame([_stage3_row("a"), _stage3_row("b")])
    chinna_bat = pd.DataFrame({"player_id": [], "balls_faced": [], "chinnaswamy_strike_rate": []})
    chinna_bowl = pd.DataFrame({
        "player_id": ["a", "b"],
        "legal_balls": [MIN_CHINNASWAMY_BALLS, MIN_CHINNASWAMY_BALLS],
        "chinnaswamy_economy": [6.0, 12.0],
    })
    result = apply_stage4_filter(stage3, chinna_bat, chinna_bowl)
    # median = 9.0; a (6.0, lower/better) passes, b (12.0) fails
    assert result.loc[result["player_id"] == "a", "passes_stage4"].iloc[0] == True
    assert result.loc[result["player_id"] == "b", "passes_stage4"].iloc[0] == False


def test_below_threshold_sample_treated_as_untested():
    stage3 = pd.DataFrame([_stage3_row("a")])
    chinna_bat = pd.DataFrame({
        "player_id": ["a"],
        "balls_faced": [MIN_CHINNASWAMY_BALLS - 1],  # just under threshold
        "chinnaswamy_strike_rate": [1.0],  # terrible SR, but shouldn't matter
    })
    chinna_bowl = pd.DataFrame({"player_id": [], "legal_balls": [], "chinnaswamy_economy": []})
    result = apply_stage4_filter(stage3, chinna_bat, chinna_bowl)
    assert result.loc[result["player_id"] == "a", "passes_stage4"].iloc[0] == True
