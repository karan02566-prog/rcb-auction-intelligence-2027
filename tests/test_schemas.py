import pandas as pd
import pytest
from pandera.errors import SchemaError, SchemaErrors
from src.utils.config import get_project_root

from src.cleaning.normalize_raw import DELIVERY_COLUMNS, MATCH_COLUMNS
from src.validation.schemas import (
    DELIVERY_SCHEMA,
    MATCH_SCHEMA,
    validate_deliveries,
    validate_interim_parquet,
    validate_interim_tables,
    validate_matches,
)


@pytest.fixture(scope="module")
def real_tables():
    project_root = get_project_root()
    matches = pd.read_parquet(project_root / "data/interim/matches.parquet")
    deliveries = pd.read_parquet(project_root / "data/interim/deliveries.parquet")
    return matches, deliveries


def _copy_tables(real_tables):
    matches, deliveries = real_tables
    return matches.iloc[:2].copy(), deliveries.iloc[:2].copy()


def test_real_parquet_files_pass_schema_and_cross_table_validation(real_tables, project_root):
    matches, deliveries = real_tables
    result = validate_interim_parquet(
        project_root / "data/interim/matches.parquet",
        project_root / "data/interim/deliveries.parquet",
    )
    assert len(result["matches"]) == len(matches) == 3798
    assert len(result["deliveries"]) == len(deliveries) == 871141


def test_actual_columns_and_dtypes_are_explicit(real_tables):
    matches, deliveries = real_tables
    assert list(matches.columns) == MATCH_COLUMNS
    assert list(deliveries.columns) == DELIVERY_COLUMNS
    assert str(matches["season"].dtype) == "string"
    assert str(matches["match_date"].dtype) == "string"
    assert str(deliveries["is_legal_ball"].dtype) == "boolean"
    assert str(deliveries["batter_runs"].dtype) == "Int64"


@pytest.mark.parametrize("table, validator, column", [
    ("matches", validate_matches, "match_id"),
    ("deliveries", validate_deliveries, "delivery_key"),
])
def test_missing_required_columns_fail(real_tables, table, validator, column):
    frame = real_tables[0 if table == "matches" else 1].drop(columns=[column])
    with pytest.raises(ValueError, match="missing columns"):
        validator(frame)


def test_unexpected_columns_fail_in_strict_mode(real_tables):
    frame = real_tables[0].assign(unexpected_column=1)
    with pytest.raises(ValueError, match="unexpected columns"):
        validate_matches(frame)


def test_invalid_integer_value_fails(real_tables):
    frame = real_tables[1].iloc[[0]].copy()
    frame["over_number"] = frame["over_number"].astype(object)
    frame.loc[0, "over_number"] = "not an integer"
    with pytest.raises((SchemaError, SchemaErrors)):
        validate_deliveries(frame)


def test_negative_runs_fail(real_tables):
    frame = real_tables[1].iloc[[0]].copy()
    frame.loc[0, "total_runs"] = -1
    with pytest.raises(ValueError, match="total_runs"):
        validate_deliveries(frame)


@pytest.mark.parametrize("column, value, message", [
    ("innings_number", 0, "innings_number"),
    ("over_number", -1, "over_number"),
])
def test_invalid_innings_or_over_numbers_fail(real_tables, column, value, message):
    frame = real_tables[1].iloc[[0]].copy()
    frame.loc[0, column] = value
    with pytest.raises(ValueError, match=message):
        validate_deliveries(frame)


def test_duplicate_match_ids_fail(real_tables):
    matches, deliveries = _copy_tables(real_tables)
    matches.loc[1, "match_id"] = matches.loc[0, "match_id"]
    with pytest.raises(ValueError, match="Duplicate match_id"):
        validate_matches(matches)


def test_duplicate_delivery_keys_fail(real_tables):
    frame = real_tables[1].iloc[:2].copy()
    frame.loc[1, "delivery_key"] = frame.loc[0, "delivery_key"]
    with pytest.raises(ValueError, match="Duplicate delivery_key"):
        validate_deliveries(frame)


def test_illegal_delivery_without_legal_number_passes(real_tables):
    frame = real_tables[1]
    illegal = frame.loc[~frame["is_legal_ball"]].iloc[[0]].copy()
    assert pd.isna(validate_deliveries(illegal).iloc[0]["legal_ball_number"])


def test_legal_delivery_without_legal_number_fails(real_tables):
    frame = real_tables[1].iloc[[0]].copy()
    frame.loc[:, "legal_ball_number"] = pd.NA
    with pytest.raises(ValueError, match="legal deliveries"):
        validate_deliveries(frame)


def test_illegal_delivery_with_legal_number_fails(real_tables):
    frame = real_tables[1].loc[~real_tables[1]["is_legal_ball"]].iloc[[0]].copy()
    frame.loc[:, "legal_ball_number"] = 1
    with pytest.raises(ValueError, match="illegal deliveries"):
        validate_deliveries(frame)


@pytest.mark.parametrize("column", ["wides_runs", "noballs_runs"])
def test_wides_and_no_balls_must_be_illegal(real_tables, column):
    frame = real_tables[1].iloc[[0]].copy()
    frame.loc[:, column] = 1
    with pytest.raises(ValueError, match="inconsistent"):
        validate_deliveries(frame)


def test_dismissal_count_must_match_wickets_json(real_tables):
    frame = real_tables[1].iloc[[0]].copy()
    frame.loc[:, "dismissal_count"] = 1
    with pytest.raises(ValueError, match="dismissal_count"):
        validate_deliveries(frame)


def test_invalid_json_event_fields_fail(real_tables):
    frame = real_tables[1].iloc[[0]].copy()
    frame.loc[:, "extras_json"] = "not json"
    with pytest.raises(ValueError, match="extras_json"):
        validate_deliveries(frame)


def test_orphan_delivery_match_ids_fail(real_tables):
    matches = real_tables[0].iloc[:1].copy()
    deliveries = real_tables[1].iloc[[0]].copy()
    deliveries.loc[0, "match_id"] = "ipl:orphan"
    with pytest.raises(ValueError, match="unknown matches"):
        validate_interim_tables(matches, deliveries)


def test_invalid_innings_reference_fails(real_tables):
    matches = real_tables[0].iloc[:1].copy()
    deliveries = real_tables[1].iloc[[0]].copy()
    deliveries.loc[0, "innings_number"] = int(matches.loc[0, "innings_count"]) + 1
    deliveries.loc[0, "match_id"] = matches.loc[0, "match_id"]
    with pytest.raises(ValueError, match="innings_count"):
        validate_interim_tables(matches, deliveries)


def test_super_over_marker_must_match_metadata(real_tables):
    matches, deliveries = _copy_tables(real_tables)
    row = deliveries.iloc[0]
    deliveries.loc[0, "is_super_over"] = True
    deliveries.loc[0, "match_id"] = row["match_id"]
    with pytest.raises(ValueError, match="is_super_over"):
        validate_interim_tables(matches, deliveries)


def test_ordering_violations_fail(real_tables):
    matches, deliveries = _copy_tables(real_tables)
    matches.iloc[:] = matches.sort_values("match_id", ascending=False).to_numpy()
    with pytest.raises(ValueError, match="ordered"):
        validate_matches(matches)

    deliveries.iloc[[0, 1]] = deliveries.iloc[[1, 0]].to_numpy()
    with pytest.raises(ValueError, match="ordered"):
        validate_deliveries(deliveries)


def test_real_edge_cases_and_miscounted_overs_pass(real_tables):
    matches, deliveries = real_tables
    assert (matches["innings_count"] > 2).any()
    assert (matches["super_over_innings_count"] > 0).any()
    assert (deliveries["byes_runs"] > 0).any()
    assert (deliveries["legbyes_runs"] > 0).any()
    assert (deliveries["penalty_runs"] > 0).any()
    assert (deliveries["wides_runs"] > 0).any()
    assert (deliveries["noballs_runs"] > 0).any()
    validate_interim_tables(matches, deliveries)