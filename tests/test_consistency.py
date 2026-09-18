"""Unit tests for Phase 4.3 consistency features."""

import numpy as np
import pandas as pd
import pytest

from src.features.consistency import (
    BOOM_MIN_HIGH_IMPACT_RATE,
    ELITE_MAX_FAILURE_RATE,
    ELITE_MIN_HIGH_IMPACT_RATE,
    HIGH_FLOOR_MAX_FAILURE_RATE,
    QUALIFIED_INNINGS_SEASON,
    assign_consistency_badge,
    compute_consistency_features,
)


def _delivery(
    match="m1",
    batter="Player A",
    batter_id="p1",
    bowler="Player B",
    bowler_id="p2",
    batter_runs=0,
    is_wicket=0,
    dismissal_type=pd.NA,
    is_legal=True,
    start_year=2024,
):
    return {
        "match_id": match,
        "batter": batter,
        "batter_canonical_id": batter_id,
        "batter_canonical_name": batter,
        "bowler": bowler,
        "bowler_canonical_id": bowler_id,
        "bowler_canonical_name": bowler,
        "batter_runs": batter_runs,
        "is_wicket": is_wicket,
        "dismissal_type": dismissal_type,
        "is_legal_delivery": 1 if is_legal else 0,
        "is_legal_ball": is_legal,
        "start_year": start_year,
    }


def test_p50_equals_computed_median_exactly():
    """Verify that P50 exactly matches computed median across an odd and even number of scores."""
    # 5 innings: scores 10, 20, 30, 40, 50 -> median = 30
    rows = []
    scores = [10, 20, 30, 40, 50]
    for i, s in enumerate(scores):
        rows.append(_delivery(match=f"m{i}", batter="Player A", batter_id="p1", batter_runs=s))

    fact = pd.DataFrame(rows)
    feats = compute_consistency_features(fact)
    row = feats.iloc[0]

    assert row["median_score"] == 30.0
    assert row["p50"] == 30.0
    assert row["p50"] == row["median_score"]

    # Even number of scores: 10, 20, 30, 40 -> median = 25.0
    rows_even = []
    for i, s in enumerate([10, 20, 30, 40]):
        rows_even.append(_delivery(match=f"m{i}", batter="Player B", batter_id="p2", batter_runs=s))
    fact_even = pd.DataFrame(rows_even)
    feats_even = compute_consistency_features(fact_even)
    row_even = feats_even.iloc[0]
    assert row_even["median_score"] == 25.0
    assert row_even["p50"] == 25.0
    assert row_even["p50"] == row_even["median_score"]


def test_failure_rate_and_high_impact_rate_correctness():
    """Synthetic test:
    Player bats in 10 matches:
      - 2 innings with scores < 10 (runs=0, runs=8) -> failure_rate = 2/10 = 0.20
      - 2 innings with scores > 45 (runs=52, runs=70)
      - 1 match with 3 wickets (score=15, wickets=3) -> high-impact match via bowling!
      - 5 normal innings (runs=25 each)
    Total high impact matches = 2 (batting > 45) + 1 (bowling 3 wickets) = 3 / 10 = 0.30."""
    rows = []
    # Match 0, 1: Low scores (< 10)
    rows.append(_delivery(match="m0", batter="AllRounder", batter_id="p1", batter_runs=0))
    rows.append(_delivery(match="m1", batter="AllRounder", batter_id="p1", batter_runs=8))
    # Match 2, 3: High scores (> 45)
    rows.append(_delivery(match="m2", batter="AllRounder", batter_id="p1", batter_runs=52))
    rows.append(_delivery(match="m3", batter="AllRounder", batter_id="p1", batter_runs=70))
    # Match 4: Score 15, but takes 3 wickets bowling
    rows.append(_delivery(match="m4", batter="AllRounder", batter_id="p1", batter_runs=15))
    for _ in range(3):
        rows.append(
            _delivery(
                match="m4",
                batter="Opponent",
                batter_id="opp",
                bowler="AllRounder",
                bowler_id="p1",
                is_wicket=1,
                dismissal_type="bowled",
            )
        )
    # Match 5-9: Moderate scores (25 runs each)
    for i in range(5, 10):
        rows.append(_delivery(match=f"m{i}", batter="AllRounder", batter_id="p1", batter_runs=25))

    fact = pd.DataFrame(rows)
    feats = compute_consistency_features(fact)
    row = feats.loc[feats["player_id"] == "p1"].iloc[0]

    assert row["innings_batted"] == 10
    assert row["matches_played"] == 10
    assert pytest.approx(row["failure_rate"], rel=1e-5) == 2.0 / 10.0  # 0.20
    assert pytest.approx(row["high_impact_rate"], rel=1e-5) == 3.0 / 10.0  # 0.30
    assert bool(row["qualified"]) is True
    # failure_rate (0.20) <= 0.35 AND high_impact_rate (0.30) >= 0.20 -> Elite
    assert row["consistency_badge"] == "Elite"


def test_badge_assignment_covers_all_categories_and_no_nulls():
    """Verify badge assignment function assigns every qualified scenario without nulls,
    covering Elite, High Floor, Boom-or-Bust, and Moderate."""
    # 1. Elite: low failure (0.20 <= 0.35) and high impact (0.30 >= 0.20)
    b_elite = assign_consistency_badge(failure_rate=0.20, high_impact_rate=0.30, qualified=True)
    assert b_elite == "Elite"

    # 2. High Floor: low failure (0.30 <= 0.40) and moderate impact (0.10 < 0.20)
    b_floor = assign_consistency_badge(failure_rate=0.30, high_impact_rate=0.10, qualified=True)
    assert b_floor == "High Floor"

    # 3. Boom-or-Bust: high failure (0.50 > 0.35) and high impact (0.30 >= 0.20)
    b_boom = assign_consistency_badge(failure_rate=0.50, high_impact_rate=0.30, qualified=True)
    assert b_boom == "Boom-or-Bust"

    # 4. Moderate: high failure (> 0.40) and low impact (< 0.20)
    b_mod = assign_consistency_badge(failure_rate=0.55, high_impact_rate=0.08, qualified=True)
    assert b_mod == "Moderate"

    # 5. Unqualified: below qualification innings
    b_unq = assign_consistency_badge(failure_rate=0.20, high_impact_rate=0.30, qualified=False)
    assert b_unq == "Unqualified"


def test_100_percent_qualified_players_have_valid_badges():
    """Assert that 100% of qualified players in any feature calculation have a non-null,
    valid badge belonging to the defined badge categories."""
    valid_badges = {"Elite", "High Floor", "Boom-or-Bust", "Moderate"}
    # Synthetic grid covering edge boundary rates
    rates = [
        (0.10, 0.40),  # Elite
        (0.35, 0.20),  # Elite boundary
        (0.38, 0.15),  # High Floor
        (0.40, 0.05),  # High Floor boundary
        (0.45, 0.25),  # Boom-or-Bust
        (0.60, 0.35),  # Boom-or-Bust
        (0.50, 0.10),  # Moderate
        (0.80, 0.00),  # Moderate
    ]
    for fail_r, impact_r in rates:
        badge = assign_consistency_badge(fail_r, impact_r, qualified=True)
        assert badge is not None
        assert badge != ""
        assert badge != "Unqualified"
        assert badge in valid_badges

def test_compute_consistency_features_zero_nulls_among_qualified():
    """End-to-end check on compute_consistency_features() itself (not just the helper):
    build several distinct players with >=10 innings each, spanning different
    failure/impact profiles, and assert zero null badges among qualified rows."""
    rows = []
    # Player 1: consistently high scores (Elite-ish)
    for i in range(12):
        rows.append(_delivery(match=f"m1_{i}", batter="P1", batter_id="p1", batter_runs=50))
    # Player 2: consistently low scores (High Floor / Moderate territory)
    for i in range(12):
        rows.append(_delivery(match=f"m2_{i}", batter="P2", batter_id="p2", batter_runs=15))
    # Player 3: boom-or-bust, alternating 0 and 60
    for i in range(12):
        score = 60 if i % 2 == 0 else 0
        rows.append(_delivery(match=f"m3_{i}", batter="P3", batter_id="p3", batter_runs=score))
    # Player 4: unqualified, only 3 innings
    for i in range(3):
        rows.append(_delivery(match=f"m4_{i}", batter="P4", batter_id="p4", batter_runs=20))

    fact = pd.DataFrame(rows)
    feats = compute_consistency_features(fact)

    qualified_rows = feats[feats["qualified"]]
    assert len(qualified_rows) > 0
    assert qualified_rows["consistency_badge"].isna().sum() == 0
    assert (qualified_rows["consistency_badge"] != "Unqualified").all()

    # P4 must be Unqualified
    p4_row = feats.loc[feats["player_id"] == "p4"].iloc[0]
    assert p4_row["qualified"] == False
    assert p4_row["consistency_badge"] == "Unqualified"
