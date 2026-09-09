from pathlib import Path

import pandas as pd

from src.ingestion.metadata import (
    build_player_competition_summary,
    build_player_identity_table,
    load_people_register,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_people_register_loads():
    path = PROJECT_ROOT / "data" / "raw" / "people.csv"

    df = load_people_register(path)

    assert len(df) == 18_507
    assert {"identifier", "name", "unique_name"}.issubset(df.columns)


def test_people_register_identifiers_are_unique():
    path = PROJECT_ROOT / "data" / "raw" / "people.csv"

    df = load_people_register(path)

    assert df["identifier"].is_unique


def test_identity_table_does_not_create_biographical_fields():
    path = PROJECT_ROOT / "data" / "raw" / "people.csv"

    people = load_people_register(path)
    identity = build_player_identity_table(people)

    forbidden_fabricated_fields = {
        "age",
        "nationality",
        "role",
        "batting_position",
        "bowling_style",
    }

    assert forbidden_fabricated_fields.isdisjoint(identity.columns)


def test_competition_summary_aggregates_matches():
    participation = pd.DataFrame(
        [
            {
                "competition": "Test Competition",
                "season": "2025",
                "match_id": "1",
                "player_name": "Player A",
                "team": "Team A",
                "match_date": "2025-01-01",
            },
            {
                "competition": "Test Competition",
                "season": "2025",
                "match_id": "2",
                "player_name": "Player A",
                "team": "Team A",
                "match_date": "2025-01-05",
            },
        ]
    )

    result = build_player_competition_summary(participation)

    assert len(result) == 1
    assert result.iloc[0]["matches"] == 2
    assert result.iloc[0]["teams"] == 1
