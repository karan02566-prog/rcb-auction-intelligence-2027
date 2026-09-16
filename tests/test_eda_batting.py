"""Unit tests for Phase 3.3 batting distributions and not-out handling."""

import numpy as np
import pandas as pd
import pytest

from src.analytics.eda_batting import (
    assert_right_skew,
    build_innings,
    complete_case_reach,
    conversion_rate,
    kaplan_meier_reach,
    player_distribution_table,
    summarize_score_vector,
)


def _fact_from_innings(innings_spec):
    rows = []
    for spec in innings_spec:
        for runs in spec["runs_seq"]:
            rows.append(
                {
                    "match_id": spec["match"],
                    "innings_number": spec["innings"],
                    "batter": spec["batter"],
                    "non_striker": spec.get("non_striker", "NS"),
                    "batter_canonical_id": spec["batter_id"],
                    "batter_canonical_name": spec["batter"],
                    "batter_runs": runs,
                    "is_legal_delivery": 1,
                    "is_boundary_four": int(runs == 4),
                    "is_boundary_six": int(runs == 6),
                    "dismissal_count": 0,
                    "dismissal_type": pd.NA,
                    "dismissal_player_out": pd.NA,
                    "competition": spec.get("competition", "ipl"),
                    "competition_canonical": spec.get("competition", "ipl"),
                    "competition_category": "IPL",
                    "start_year": 2024,
                }
            )
        if spec.get("out_kind"):
            rows[-1]["dismissal_count"] = 1
            rows[-1]["dismissal_type"] = spec["out_kind"]
            rows[-1]["dismissal_player_out"] = spec.get("player_out", spec["batter"])
    return pd.DataFrame(rows)


def test_not_out_zero_is_not_a_duck():
    fact = _fact_from_innings(
        [
            {"match": "m1", "innings": 1, "batter": "A", "batter_id": "a", "runs_seq": [0, 0]},
            {"match": "m2", "innings": 1, "batter": "A", "batter_id": "a", "runs_seq": [0], "out_kind": "bowled"},
        ]
    )
    innings = build_innings(fact, exact_lookup={}, norm_lookup={})
    not_out_zero = innings.loc[innings["match_id"].eq("m1")].iloc[0]
    duck = innings.loc[innings["match_id"].eq("m2")].iloc[0]
    assert bool(not_out_zero["is_not_out"])
    assert not bool(not_out_zero["is_duck"])
    assert bool(duck["is_duck"])


def test_retired_hurt_is_censored():
    fact = _fact_from_innings(
        [
            {
                "match": "m1",
                "innings": 1,
                "batter": "A",
                "batter_id": "a",
                "runs_seq": [1, 1, 1],
                "out_kind": "retired hurt",
            },
        ]
    )
    innings = build_innings(fact, exact_lookup={}, norm_lookup={})
    assert bool(innings.iloc[0]["is_not_out"])


def test_kaplan_meier_does_not_treat_not_out_below_threshold_as_failure():
    scores = np.array([15.0, 15.0, 25.0])
    is_out = np.array([True, False, True])
    naive = float((scores >= 20).mean())
    km = kaplan_meier_reach(scores, is_out, 20)
    cc = complete_case_reach(scores, is_out, 20)
    assert naive == pytest.approx(1 / 3)
    assert km == pytest.approx(2 / 3)
    assert cc == pytest.approx(0.5)
    assert km > naive


def test_conversion_excludes_stranded_not_outs():
    scores = np.array([22.0, 22.0, 35.0])
    is_out = np.array([True, False, True])
    assert conversion_rate(scores, is_out, 20, 30) == pytest.approx(0.5)


def test_summarize_right_skew_and_median_lt_mean():
    scores = np.array([0, 1, 2, 5, 8, 40, 80], dtype=float)
    is_out = np.array([True] * 7)
    summary = summarize_score_vector(scores, is_out)
    assert summary["median_score"] < summary["mean_score"]
    assert summary["median_lt_mean"]
    assert summary["rate_50_naive"] == pytest.approx(1 / 7)


def test_player_table_scope_and_qualified_flag():
    fact = _fact_from_innings(
        [
            {
                "match": f"m{i}",
                "innings": 1,
                "batter": "A",
                "batter_id": "a",
                "runs_seq": [1, 1],
                "out_kind": "caught",
            }
            for i in range(12)
        ]
    )
    innings = build_innings(fact, {}, {})
    tbl = player_distribution_table(innings, "ipl_2018_2026")
    assert bool(tbl.iloc[0]["qualified"])
    assert tbl.iloc[0]["innings"] == 12
    assert tbl.iloc[0]["scope"] == "ipl_2018_2026"


def test_assert_right_skew_passes_on_typical_scores():
    innings = pd.DataFrame({"runs": [0, 1, 4, 8, 12, 18, 45, 72]})
    result = assert_right_skew(innings)
    assert result["median_score"] < result["mean_score"]


def test_assert_right_skew_fails_when_left_skewed():
    innings = pd.DataFrame({"runs": [90, 91, 92, 93, 94, 10]})
    with pytest.raises(AssertionError, match="median < mean"):
        assert_right_skew(innings)
