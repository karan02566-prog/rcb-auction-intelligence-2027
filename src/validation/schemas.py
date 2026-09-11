"""Pandera contracts and data-quality checks for the Phase 2 interim tables."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pandera.pandas as pa

from src.cleaning.normalize_raw import DELIVERY_COLUMNS, MATCH_COLUMNS


SUPPORTED_COMPETITIONS = frozenset({"bbl", "cpl", "hnd", "ilt", "ipl", "mlc", "sat", "sma"})
CRICSHEET_SOURCE_PREFIX = "data/raw/cricsheet/"
JSON_MATCH_COLUMNS = {
    "dates_json", "teams_json", "event_json", "officials_json", "outcome_json",
    "player_of_match_json", "players_json", "registry_people_json", "missing_json",
    "supersubs_json", "innings_metadata_json",
}
JSON_DELIVERY_COLUMNS = {"wickets_json", "extras_json", "review_json", "replacements_json"}
RUN_COLUMNS = {
    "batter_runs", "extra_runs", "total_runs", "byes_runs", "legbyes_runs",
    "noballs_runs", "penalty_runs", "wides_runs",
}


def _string_columns(columns: list[str], *, nullable: bool = True) -> dict[str, pa.Column]:
    return {column: pa.Column(pa.String, nullable=nullable) for column in columns}


def _integer_columns(columns: list[str], *, nullable: bool = True) -> dict[str, pa.Column]:
    return {
        column: pa.Column(pa.Int64, nullable=nullable, coerce=False)
        for column in columns
    }


MATCH_SCHEMA = pa.DataFrameSchema(
    {
        **_string_columns([
            "match_id", "source_match_id", "competition", "source_path",
            "meta_data_version", "meta_created", "match_date", "dates_json", "season",
            "gender", "match_type", "team_type", "city", "venue", "team_1", "team_2",
            "teams_json", "event_json", "officials_json", "outcome_winner", "outcome_type",
            "outcome_margin_unit", "outcome_json", "toss_winner", "toss_decision",
            "player_of_match_json", "players_json", "registry_people_json", "missing_json",
            "supersubs_json", "innings_metadata_json",
        ]),
        **_integer_columns([
            "meta_revision", "balls_per_over", "scheduled_overs", "outcome_margin_value",
            "innings_count", "super_over_innings_count",
        ]),
    },
    strict=True,
    coerce=False,
    name="matches",
)

DELIVERY_SCHEMA = pa.DataFrameSchema(
    {
        **_string_columns([
            "delivery_key", "match_id", "source_match_id", "competition", "source_path",
            "season", "innings_team", "actual_delivery", "batter", "bowler", "non_striker",
            "dismissal_type", "dismissal_player_out", "wickets_json", "extras_json",
            "review_json", "replacements_json",
        ]),
        "is_super_over": pa.Column(pd.BooleanDtype(), nullable=False, coerce=False),
        "is_legal_ball": pa.Column(pd.BooleanDtype(), nullable=False, coerce=False),
        **_integer_columns([
            "innings_number", "over_number", "delivery_in_over", "ball_in_over",
            "legal_ball_number", "batter_runs", "extra_runs", "total_runs", "byes_runs",
            "legbyes_runs", "noballs_runs", "penalty_runs", "wides_runs", "dismissal_count",
        ]),
    },
    strict=True,
    coerce=False,
    name="deliveries",
)

for _required_delivery_column in (
    "delivery_key", "match_id", "source_match_id", "competition", "source_path",
    "batter", "bowler", "non_striker",
):
    DELIVERY_SCHEMA.columns[_required_delivery_column].nullable = False


def _json_value(value: Any, column: str, expected_type: type | tuple[type, ...] | None = None) -> Any:
    if pd.isna(value):
        return None
    try:
        decoded = json.loads(str(value))
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{column} contains invalid JSON") from exc
    if expected_type is not None and not isinstance(decoded, expected_type):
        name = ", ".join(item.__name__ for item in expected_type) if isinstance(expected_type, tuple) else expected_type.__name__
        raise ValueError(f"{column} must decode to {name}")
    return decoded


def _require_columns(frame: pd.DataFrame, expected: list[str], name: str) -> None:
    missing = sorted(set(expected) - set(frame.columns))
    unexpected = sorted(set(frame.columns) - set(expected))
    if missing or unexpected:
        details = []
        if missing:
            details.append(f"missing columns: {missing}")
        if unexpected:
            details.append(f"unexpected columns: {unexpected}")
        raise ValueError(f"{name} schema columns invalid ({'; '.join(details)})")


def _validate_json_columns(frame: pd.DataFrame, columns: set[str]) -> None:
    for column in columns:
        for value in frame[column].dropna().unique():
            _json_value(value, column)


def validate_matches(matches: pd.DataFrame, *, lazy: bool = True) -> pd.DataFrame:
    """Validate match columns and match-level value/JSON contracts."""
    _require_columns(matches, MATCH_COLUMNS, "matches")
    validated = MATCH_SCHEMA.validate(matches, lazy=lazy)
    if validated["match_id"].duplicated().any():
        raise ValueError("Duplicate match_id values detected")
    for column in ("match_id", "source_match_id", "competition", "source_path"):
        if validated[column].isna().any():
            raise ValueError(f"{column} must be non-null")
    if not validated["competition"].isin(SUPPORTED_COMPETITIONS).all():
        raise ValueError("competition contains an unsupported Cricsheet directory")
    source_paths = validated["source_path"].astype("string")
    if not source_paths.str.startswith(CRICSHEET_SOURCE_PREFIX).all():
        raise ValueError("source_path must point to data/raw/cricsheet")
    if (validated["balls_per_over"] <= 0).any():
        raise ValueError("balls_per_over must be positive")
    if (validated["scheduled_overs"].dropna() <= 0).any():
        raise ValueError("scheduled_overs must be positive when present")
    if (validated["innings_count"] <= 0).any():
        raise ValueError("innings_count must be positive")
    if (validated["super_over_innings_count"] < 0).any() or (
        validated["super_over_innings_count"] > validated["innings_count"]
    ).any():
        raise ValueError("super_over_innings_count must be between zero and innings_count")
    if (validated["outcome_margin_value"].dropna() < 0).any():
        raise ValueError("outcome_margin_value must be non-negative when present")
    _validate_json_columns(validated, JSON_MATCH_COLUMNS)
    if not validated["match_id"].tolist() == sorted(validated["match_id"].tolist()):
        raise ValueError("matches must be deterministically ordered by match_id")
    return validated


def _validate_run_columns(deliveries: pd.DataFrame) -> None:
    for column in RUN_COLUMNS:
        if (deliveries[column].dropna() < 0).any():
            raise ValueError(f"{column} must be non-negative")


def validate_deliveries(deliveries: pd.DataFrame, *, lazy: bool = True) -> pd.DataFrame:
    """Validate delivery columns and row-level ball/event contracts."""
    _require_columns(deliveries, DELIVERY_COLUMNS, "deliveries")
    validated = DELIVERY_SCHEMA.validate(deliveries, lazy=lazy)
    for column in ("delivery_key", "match_id", "competition", "source_path", "batter", "bowler", "non_striker"):
        if validated[column].isna().any():
            raise ValueError(f"{column} must be non-null")
    if validated["delivery_key"].duplicated().any():
        raise ValueError("Duplicate delivery_key values detected")
    if not validated["competition"].isin(SUPPORTED_COMPETITIONS).all():
        raise ValueError("competition contains an unsupported Cricsheet directory")
    if not validated["source_path"].astype("string").str.startswith(CRICSHEET_SOURCE_PREFIX).all():
        raise ValueError("source_path must point to data/raw/cricsheet")
    if (validated["innings_number"] < 1).any():
        raise ValueError("innings_number must be greater than or equal to 1")
    if (validated["over_number"] < 0).any():
        raise ValueError("over_number must be greater than or equal to 0")
    if (validated["delivery_in_over"] < 1).any():
        raise ValueError("delivery_in_over must be greater than or equal to 1")
    if (validated["ball_in_over"].dropna() <= 0).any():
        raise ValueError("ball_in_over must be positive when present")
    _validate_run_columns(validated)
    if (validated["dismissal_count"] < 0).any():
        raise ValueError("dismissal_count must be non-negative")

    illegal = (validated["wides_runs"] > 0) | (validated["noballs_runs"] > 0)
    if (validated["is_legal_ball"] == illegal).any():
        raise ValueError("is_legal_ball is inconsistent with wides/no-balls")
    if validated.loc[validated["is_legal_ball"], "legal_ball_number"].isna().any():
        raise ValueError("legal deliveries must have legal_ball_number")
    if validated.loc[~validated["is_legal_ball"], "legal_ball_number"].notna().any():
        raise ValueError("illegal deliveries must not have legal_ball_number")
    if (validated.loc[validated["is_legal_ball"], "legal_ball_number"] <= 0).any():
        raise ValueError("legal_ball_number must be positive for legal deliveries")

    wickets_cache = {
        str(value): _json_value(value, "wickets_json", list)
        for value in validated["wickets_json"].dropna().unique()
    }
    extras_cache = {
        str(value): _json_value(value, "extras_json", dict)
        for value in validated["extras_json"].dropna().unique()
    }
    wicket_lengths = validated["wickets_json"].map(
        {key: len(value) for key, value in wickets_cache.items()}
    )
    mismatch = wicket_lengths != validated["dismissal_count"]
    if mismatch.any():
        raise ValueError(f"dismissal_count disagrees with wickets_json at row {mismatch.idxmax()}")
    for key, column in (("byes", "byes_runs"), ("legbyes", "legbyes_runs"), ("noballs", "noballs_runs"), ("penalty", "penalty_runs"), ("wides", "wides_runs")):
        expected = validated["extras_json"].map(
            {json_value: values.get(key, 0) for json_value, values in extras_cache.items()}
        )
        mismatch = expected != validated[column]
        if mismatch.any():
            raise ValueError(f"{column} does not preserve extras_json[{key!r}] at row {mismatch.idxmax()}")
    order_columns = ["match_id", "innings_number", "over_number", "delivery_in_over"]
    if not validated[order_columns].sort_values(order_columns, kind="stable").index.equals(validated.index):
        raise ValueError("deliveries must be ordered by match_id, innings_number, over_number, delivery_in_over")
    return validated


def validate_interim_tables(matches: pd.DataFrame, deliveries: pd.DataFrame, *, lazy: bool = True) -> dict[str, pd.DataFrame]:
    """Validate both tables, including cross-table references and metadata agreement."""
    validated_matches = validate_matches(matches, lazy=lazy)
    validated_deliveries = validate_deliveries(deliveries, lazy=lazy)
    match_ids = set(validated_matches["match_id"])
    if not set(validated_deliveries["match_id"]).issubset(match_ids):
        raise ValueError("Delivery rows reference unknown matches")
    match_lookup = validated_matches.set_index("match_id")
    semantic_columns = ["match_id", "innings_number", "is_super_over", "is_legal_ball", "legal_ball_number"]
    for match_id, group in validated_deliveries[semantic_columns].groupby("match_id", sort=False):
        match = match_lookup.loc[match_id]
        if (group["innings_number"] > int(match["innings_count"])).any():
            raise ValueError("Delivery innings_number exceeds the declared innings_count")
        metadata = _json_value(match["innings_metadata_json"], "innings_metadata_json", list)
        for innings_number, innings_group in group.groupby("innings_number", sort=False)[["is_super_over", "is_legal_ball", "legal_ball_number"]]:
            metadata_item = metadata[int(innings_number) - 1]
            expected_super_over = bool(metadata_item.get("super_over", False))
            if (innings_group["is_super_over"] != expected_super_over).any():
                raise ValueError("is_super_over disagrees with innings metadata")
            legal_numbers = innings_group.loc[innings_group["is_legal_ball"], "legal_ball_number"].tolist()
            if legal_numbers != list(range(1, len(legal_numbers) + 1)):
                raise ValueError("legal_ball_number must increase only on legal deliveries")
    return {"matches": validated_matches, "deliveries": validated_deliveries}


def validate_interim_parquet(matches_path: str | Path, deliveries_path: str | Path) -> dict[str, pd.DataFrame]:
    """Read and validate the Phase 2 interim Parquet files."""
    return validate_interim_tables(pd.read_parquet(matches_path), pd.read_parquet(deliveries_path))