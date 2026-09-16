"""Unit tests for the Phase 2.3 dim_players materialization."""

import json

import pandas as pd

from src.cleaning.build_dim_players import appearance_stats, build_dim_players, collapse_mapping


def test_collapse_mapping_is_unique_per_canonical_id():
    mapped = pd.DataFrame(
        [
            {
                "source_name": "V Kohli",
                "canonical_id": "ba607b88",
                "canonical_name": "V Kohli",
                "method": "exact_match",
                "confidence": "exact",
            },
            {
                "source_name": "Virat Kohli",
                "canonical_id": "ba607b88",
                "canonical_name": "V Kohli",
                "method": "exact_match",
                "confidence": "exact",
            },
            {
                "source_name": "Other",
                "canonical_id": "aaaa",
                "canonical_name": "Other",
                "method": "fuzzy",
                "confidence": "medium",
            },
        ]
    )
    dim = collapse_mapping(mapped)
    assert dim["player_id"].is_unique
    kohli = dim.loc[dim["player_id"].eq("ba607b88")].iloc[0]
    assert kohli["n_source_names"] == 2
    assert "Virat Kohli" in kohli["source_names"]


def test_build_dim_players_joins_register_and_appearances(tmp_path):
    mapping = {
        "mapped": [
            {
                "source_name": "A",
                "canonical_id": "id1",
                "canonical_name": "Alpha",
                "method": "exact_match",
                "confidence": "exact",
            },
            {
                "source_name": "A1",
                "canonical_id": "id1",
                "canonical_name": "Alpha",
                "method": "normalized",
                "confidence": "medium",
            },
        ]
    }
    mapping_path = tmp_path / "player_mapping.json"
    mapping_path.write_text(json.dumps(mapping), encoding="utf-8")
    identity = pd.DataFrame(
        [{"identifier": "id1", "name": "Alpha", "unique_name": "Alpha", "key_cricinfo": "1"}]
    )
    identity_path = tmp_path / "identity.csv"
    identity.to_csv(identity_path, index=False)

    fact = pd.DataFrame(
        {
            "batter_canonical_id": ["id1", "id1", "UNRESOLVED"],
            "bowler_canonical_id": ["id1", "other", "id1"],
            "match_id": ["m1", "m2", "m3"],
        }
    )
    dim = build_dim_players(mapping_path, identity_path=identity_path, fact=fact)
    assert len(dim) == 1
    assert dim.iloc[0]["player_id"] == "id1"
    assert dim.iloc[0]["batter_matches"] == 2
    assert bool(dim.iloc[0]["in_cricsheet_register"])


def test_appearance_stats_ignore_unresolved():
    fact = pd.DataFrame(
        {
            "batter_canonical_id": ["UNRESOLVED", "p1"],
            "bowler_canonical_id": ["UNRESOLVED", "p1"],
            "match_id": ["m1", "m1"],
        }
    )
    stats = appearance_stats(fact)
    assert list(stats["player_id"]) == ["p1"]
