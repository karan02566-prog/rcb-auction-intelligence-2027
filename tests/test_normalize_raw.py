import json

import pandas as pd
import pytest

from src.cleaning.normalize_raw import (
    DELIVERY_COLUMNS,
    MATCH_COLUMNS,
    normalize_raw_data,
    parse_match,
    validate_normalized_tables,
)


def _write_match(tmp_path, payload, competition="test"):
    root = tmp_path / "raw" / competition
    root.mkdir(parents=True)
    path = root / "123.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return root, path


def _payload(deliveries, *, super_over=False):
    return {
        "meta": {"data_version": "1.2.0", "created": "2026-01-01", "revision": 1},
        "info": {
            "balls_per_over": 6,
            "dates": ["2026-01-01"],
            "gender": "male",
            "match_type": "T20",
            "overs": 1,
            "season": 2026,
            "team_type": "club",
            "teams": ["A", "B"],
            "venue": "Ground",
        },
        "innings": [{
            "team": "A",
            "super_over": super_over,
            "overs": [{"over": 0, "deliveries": deliveries}],
        }],
    }


def _delivery(actual, *, extras=None, wickets=None, runs=None):
    return {
        "actual_delivery": actual,
        "batter": "Batter",
        "bowler": "Bowler",
        "non_striker": "Runner",
        "runs": runs or {"batter": 1, "extras": 0, "total": 1},
        **({"extras": extras} if extras is not None else {}),
        **({"wickets": wickets} if wickets is not None else {}),
    }


def test_parse_legal_wide_noball_and_following_legal_ball(tmp_path):
    deliveries = [
        _delivery("0.1"),
        _delivery("0.2", extras={"wides": 1}, runs={"batter": 0, "extras": 1, "total": 1}),
        _delivery("0.2", extras={"noballs": 1}, runs={"batter": 0, "extras": 1, "total": 1}),
        _delivery(
            "0.2",
            extras={"byes": 1, "legbyes": 2, "penalty": 5},
            runs={"batter": 0, "extras": 8, "total": 8},
        ),
    ]
    _, path = _write_match(tmp_path, _payload(deliveries))

    _, rows = parse_match(path, "test")

    assert [row["is_legal_ball"] for row in rows] == [True, False, False, True]
    assert [row["legal_ball_number"] for row in rows] == [1, None, None, 2]
    assert rows[-1]["byes_runs"] == 1
    assert rows[-1]["legbyes_runs"] == 2
    assert rows[-1]["penalty_runs"] == 5
    assert rows[-1]["extras_json"] == '{"byes":1,"legbyes":2,"penalty":5}'


def test_dismissal_and_multiple_event_order_are_preserved(tmp_path):
    wickets = [
        {"kind": "run out", "player_out": "Runner", "fielders": [{"name": "Fielder"}]},
        {"kind": "retired hurt", "player_out": "Batter"},
    ]
    _, path = _write_match(tmp_path, _payload([_delivery("0.1", wickets=wickets)]))

    _, rows = parse_match(path, "test")

    assert rows[0]["dismissal_count"] == 2
    assert rows[0]["dismissal_type"] == "run out|retired hurt"
    assert json.loads(rows[0]["wickets_json"]) == wickets


def test_super_over_is_explicit_and_not_mixed_with_normal_innings(tmp_path):
    _, path = _write_match(tmp_path, _payload([_delivery("0.1")], super_over=True))

    match, rows = parse_match(path, "test")

    assert match["super_over_innings_count"] == 1
    assert rows[0]["is_super_over"] is True
    assert rows[0]["delivery_key"] == "test:123:1:0:1"


def test_validation_rejects_duplicate_delivery_keys(tmp_path):
    _, path = _write_match(tmp_path, _payload([_delivery("0.1"), _delivery("0.2")]))
    match, rows = parse_match(path, "test")
    matches = pd.DataFrame([match], columns=MATCH_COLUMNS)
    deliveries = pd.DataFrame(rows, columns=DELIVERY_COLUMNS)
    deliveries.loc[1, "delivery_key"] = deliveries.loc[0, "delivery_key"]

    with pytest.raises(ValueError, match="Duplicate delivery_key"):
        validate_normalized_tables(matches, deliveries)


def test_malformed_match_is_rejected(tmp_path):
    _, path = _write_match(tmp_path, {"meta": {}, "innings": []})

    with pytest.raises(ValueError, match="Unsupported Cricsheet match structure"):
        parse_match(path, "test")


def test_normalize_writes_deterministic_parquet_outputs(tmp_path):
    root = tmp_path / "raw" / "test"
    root.mkdir(parents=True)
    for match_id in ("002", "001"):
        (root / f"{match_id}.json").write_text(
            json.dumps(_payload([_delivery("0.1")])), encoding="utf-8"
        )

    first = normalize_raw_data(tmp_path / "raw", tmp_path / "first")
    second = normalize_raw_data(tmp_path / "raw", tmp_path / "second")
    pd.testing.assert_frame_equal(
        pd.read_parquet(first["matches_path"]),
        pd.read_parquet(second["matches_path"]),
    )
    pd.testing.assert_frame_equal(
        pd.read_parquet(first["deliveries_path"]),
        pd.read_parquet(second["deliveries_path"]),
    )
    assert first["validation"] == {
        "matches": 2,
        "deliveries": 2,
        "legal_deliveries": 2,
        "illegal_deliveries": 0,
        "dismissal_events": 0,
        "extra_events": 0,
    }