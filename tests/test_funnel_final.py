import pandas as pd
from src.analytics.funnel_final import apply_translation_filter, role_representation

FL = ["sr_transition_variance_flag", "avg_transition_variance_flag",
      "economy_transition_variance_flag", "wicket_rate_transition_variance_flag"]


def _trans(rows):
    df = pd.DataFrame(rows)
    for c in FL:
        if c not in df:
            df[c] = None
        df[c] = df[c].astype(object)
    return df


def _setup():
    passers = pd.DataFrame({"player_id": ["p1", "p2", "p3", "p4"],
                            "player_name": ["A", "B", "C", "D"]})
    trans = _trans([
        dict(player_id="p1", player_type="batter", qualified=True, is_uncapped=False, sr_transition_variance_flag=True),
        dict(player_id="p2", player_type="batter", qualified=True, is_uncapped=False),
        dict(player_id="p3", player_type="bowler", qualified=True, is_uncapped=True,
             economy_transition_variance_flag=False, wicket_rate_transition_variance_flag=False),
        dict(player_id="p4", player_type="batter", qualified=False, is_uncapped=False),
        dict(player_id="p9", player_type="batter", qualified=True, is_uncapped=False),
    ])
    return passers, trans


def test_counts_and_membership():
    keep, c = apply_translation_filter(*_setup())
    assert c == {"stage4_passers": 4, "dropped_no_qualified_translation_row": 1,
                 "dropped_unstable_transition_flag": 1, "final_shortlist": 2}
    assert set(keep.player_id) == {"p2", "p3"}


def test_untested_tag_and_uncapped():
    keep, _ = apply_translation_filter(*_setup())
    k = keep.set_index("player_id")
    assert bool(k.loc["p2", "variance_untested"]) and not bool(k.loc["p3", "variance_untested"])
    assert bool(k.loc["p3", "is_uncapped"]) and not bool(k.loc["p2", "is_uncapped"])


def test_flag_role_specificity():
    passers = pd.DataFrame({"player_id": ["p1"], "player_name": ["A"]})
    trans = _trans([dict(player_id="p1", player_type="bowler", qualified=True, is_uncapped=False,
                         sr_transition_variance_flag=True)])  # batting flag must not hit a bowler row
    keep, _ = apply_translation_filter(passers, trans)
    assert list(keep.player_id) == ["p1"]


def test_role_representation_reports_empty_cells():
    short = pd.DataFrame({"roles": ["batter,bowler", "batter"], "is_uncapped": [False, False]})
    r = role_representation(short)
    assert r["counts"] == {"batter|uncapped=False": 2, "bowler|uncapped=False": 1}
    assert set(r["empty_cells"]) == {"batter|uncapped=True", "bowler|uncapped=True"}
