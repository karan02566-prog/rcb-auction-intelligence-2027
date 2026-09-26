"""Tests for Phase 6.3 consistency and floor/ceiling filtering."""
import pandas as pd

from src.analytics.funnel_consistency import get_recent_badge, apply_stage3_filter, SCOPE


def test_get_recent_badge_prefers_2026_over_2025():
    consistency = pd.DataFrame({
        "scope": [SCOPE, SCOPE],
        "player_id": ["a", "a"],
        "start_year": [2025, 2026],
        "qualified": [True, True],
        "consistency_badge": ["Moderate", "Elite"],
    })
    result = get_recent_badge(consistency)
    assert result.loc[result["player_id"] == "a", "recent_consistency_badge"].iloc[0] == "Elite"


def test_get_recent_badge_falls_back_to_2025_if_2026_unqualified():
    consistency = pd.DataFrame({
        "scope": [SCOPE, SCOPE],
        "player_id": ["a", "a"],
        "start_year": [2025, 2026],
        "qualified": [True, False],
        "consistency_badge": ["High Floor", "Unqualified"],
    })
    result = get_recent_badge(consistency)
    assert result.loc[result["player_id"] == "a", "recent_consistency_badge"].iloc[0] == "High Floor"


def test_boom_or_bust_is_not_penalized():
    stage2 = pd.DataFrame({
        "player_id": ["a"],
        "passes_stage2": [True],
        "meets_batting_threshold": [True],
        "meets_bowling_threshold": [False],
    })
    recent_badge = pd.DataFrame({"player_id": ["a"], "recent_consistency_badge": ["Boom-or-Bust"]})
    result = apply_stage3_filter(stage2, recent_badge)
    assert result.loc[result["player_id"] == "a", "passes_stage3"].iloc[0] == True


def test_moderate_badge_fails():
    stage2 = pd.DataFrame({
        "player_id": ["a"],
        "passes_stage2": [True],
        "meets_batting_threshold": [True],
        "meets_bowling_threshold": [False],
    })
    recent_badge = pd.DataFrame({"player_id": ["a"], "recent_consistency_badge": ["Moderate"]})
    result = apply_stage3_filter(stage2, recent_badge)
    assert result.loc[result["player_id"] == "a", "passes_stage3"].iloc[0] == False


def test_bowling_only_candidate_unaffected_by_badge():
    stage2 = pd.DataFrame({
        "player_id": ["a"],
        "passes_stage2": [True],
        "meets_batting_threshold": [False],
        "meets_bowling_threshold": [True],
    })
    # no badge at all (pure bowler never batted) -- must still pass
    recent_badge = pd.DataFrame({"player_id": [], "recent_consistency_badge": []})
    result = apply_stage3_filter(stage2, recent_badge)
    assert result.loc[result["player_id"] == "a", "passes_stage3"].iloc[0] == True


def test_unqualified_batter_passes_through():
    stage2 = pd.DataFrame({
        "player_id": ["a"],
        "passes_stage2": [True],
        "meets_batting_threshold": [True],
        "meets_bowling_threshold": [False],
    })
    recent_badge = pd.DataFrame({"player_id": ["a"], "recent_consistency_badge": ["Unqualified"]})
    result = apply_stage3_filter(stage2, recent_badge)
    assert result.loc[result["player_id"] == "a", "passes_stage3"].iloc[0] == True
