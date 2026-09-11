"""Normalize raw Cricsheet JSON into deterministic interim Parquet tables."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from src.utils.config import resolve_path


MATCH_COLUMNS = [
    "match_id", "source_match_id", "competition", "source_path",
    "meta_data_version", "meta_created", "meta_revision", "match_date",
    "dates_json", "season", "gender", "match_type", "team_type",
    "balls_per_over", "scheduled_overs", "city", "venue", "team_1",
    "team_2", "teams_json", "event_json", "officials_json",
    "outcome_winner", "outcome_type", "outcome_margin_value",
    "outcome_margin_unit", "outcome_json", "toss_winner", "toss_decision",
    "player_of_match_json", "players_json", "registry_people_json",
    "missing_json", "supersubs_json", "innings_count",
    "super_over_innings_count", "innings_metadata_json",
]

DELIVERY_COLUMNS = [
    "delivery_key", "match_id", "source_match_id", "competition", "source_path",
    "season", "innings_number", "innings_team", "is_super_over", "over_number",
    "delivery_in_over", "actual_delivery", "ball_in_over", "legal_ball_number",
    "is_legal_ball", "batter", "bowler", "non_striker", "batter_runs",
    "extra_runs", "total_runs", "byes_runs", "legbyes_runs", "noballs_runs",
    "penalty_runs", "wides_runs", "dismissal_count", "dismissal_type",
    "dismissal_player_out", "wickets_json", "extras_json", "review_json",
    "replacements_json",
]

_INT_COLUMNS = {
    "meta_revision", "balls_per_over", "scheduled_overs",
    "outcome_margin_value", "innings_count", "super_over_innings_count",
    "innings_number", "over_number", "delivery_in_over", "ball_in_over",
    "legal_ball_number", "batter_runs", "extra_runs", "total_runs", "byes_runs",
    "legbyes_runs", "noballs_runs", "penalty_runs", "wides_runs", "dismissal_count",
}
_BOOL_COLUMNS = {"is_super_over", "is_legal_ball"}


def _json_value(value: Any) -> str | None:
    """Serialize nested source values canonically, preserving source content."""
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _first_date(info: dict[str, Any]) -> str | None:
    dates = info.get("dates") or []
    return str(dates[0]) if dates else None


def _outcome_fields(outcome: dict[str, Any]) -> tuple[str | None, str | None, int | None, str | None]:
    margin = outcome.get("by") or {}
    if margin:
        unit, value = next(iter(margin.items()))
        return outcome.get("winner"), "by", int(value), str(unit)
    if "result" in outcome:
        return None, str(outcome["result"]), None, None
    if "bowl_out" in outcome:
        return None, "bowl_out", None, None
    return outcome.get("winner"), None, None, None


def _parse_ball_number(actual_delivery: Any) -> int | None:
    if actual_delivery is None or "." not in str(actual_delivery):
        return None
    try:
        return int(str(actual_delivery).split(".", 1)[1])
    except ValueError:
        return None


def _nullable_frame(rows: list[dict[str, Any]], columns: list[str]) -> pd.DataFrame:
    frame = pd.DataFrame.from_records(rows, columns=columns)
    for column in columns:
        if column in _BOOL_COLUMNS:
            frame[column] = frame[column].astype("boolean")
        elif column in _INT_COLUMNS:
            frame[column] = pd.array(frame[column], dtype="Int64")
        else:
            frame[column] = frame[column].astype("string")
    return frame


def _iter_match_files(raw_root: Path) -> Iterable[tuple[str, Path]]:
    for competition_dir in sorted(path for path in raw_root.iterdir() if path.is_dir()):
        for path in sorted(competition_dir.glob("*.json")):
            yield competition_dir.name, path


def _expected_over_balls(match: dict[str, Any], innings_number: int, over_number: int) -> int:
    metadata = json.loads(match["innings_metadata_json"])[innings_number - 1]
    scheduled_overs = int(match["scheduled_overs"])
    default_balls = int(match["balls_per_over"])
    if over_number < 0 or over_number >= scheduled_overs:
        raise ValueError("Over number falls outside the scheduled innings range")
    override = (metadata.get("miscounted_overs") or {}).get(str(over_number))
    if override is None:
        override = (metadata.get("miscounted_overs") or {}).get(over_number)
    if override is None:
        return default_balls
    try:
        return int(override["balls"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Malformed miscounted_overs metadata") from exc


def parse_match(path: Path, competition: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Parse one raw match file into one match row and delivery rows."""
    with path.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or not isinstance(payload.get("info"), dict):
        raise ValueError(f"Unsupported Cricsheet match structure: {path}")

    info = payload["info"]
    match_id = f"{competition}:{path.stem}"
    outcome = info.get("outcome") or {}
    outcome_winner, outcome_type, margin_value, margin_unit = _outcome_fields(outcome)
    teams = info.get("teams") or []
    innings = payload.get("innings") or []
    meta = payload.get("meta") or {}
    source_path = f"data/raw/cricsheet/{competition}/{path.name}"
    match_row = {
        "match_id": match_id, "source_match_id": path.stem, "competition": competition,
        "source_path": source_path, "meta_data_version": meta.get("data_version"),
        "meta_created": meta.get("created"), "meta_revision": meta.get("revision"),
        "match_date": _first_date(info), "dates_json": _json_value(info.get("dates")),
        "season": str(info["season"]) if info.get("season") is not None else None,
        "gender": info.get("gender"), "match_type": info.get("match_type"),
        "team_type": info.get("team_type"), "balls_per_over": info.get("balls_per_over"),
        "scheduled_overs": info.get("overs"), "city": info.get("city"),
        "venue": info.get("venue"), "team_1": teams[0] if len(teams) > 0 else None,
        "team_2": teams[1] if len(teams) > 1 else None, "teams_json": _json_value(teams),
        "event_json": _json_value(info.get("event")),
        "officials_json": _json_value(info.get("officials")),
        "outcome_winner": outcome_winner, "outcome_type": outcome_type,
        "outcome_margin_value": margin_value, "outcome_margin_unit": margin_unit,
        "outcome_json": _json_value(outcome), "toss_winner": (info.get("toss") or {}).get("winner"),
        "toss_decision": (info.get("toss") or {}).get("decision"),
        "player_of_match_json": _json_value(info.get("player_of_match")),
        "players_json": _json_value(info.get("players")),
        "registry_people_json": _json_value((info.get("registry") or {}).get("people")),
        "missing_json": _json_value(info.get("missing")),
        "supersubs_json": _json_value(info.get("supersubs")), "innings_count": len(innings),
        "super_over_innings_count": sum(bool(item.get("super_over")) for item in innings),
        "innings_metadata_json": _json_value(
            [{key: value for key, value in item.items() if key != "overs"} for item in innings]
        ),
    }

    delivery_rows: list[dict[str, Any]] = []
    for innings_number, innings_data in enumerate(innings, 1):
        legal_ball_number = 0
        for over_data in innings_data.get("overs", []):
            over_number = int(over_data["over"])
            for delivery_in_over, delivery in enumerate(over_data.get("deliveries", []), 1):
                extras = delivery.get("extras") or {}
                runs = delivery.get("runs") or {}
                is_legal = not bool(extras.get("wides", 0) or extras.get("noballs", 0))
                if is_legal:
                    legal_ball_number += 1
                wickets = delivery.get("wickets") or []
                dismissal_types = [str(item["kind"]) for item in wickets if item.get("kind") is not None]
                dismissal_players = [str(item["player_out"]) for item in wickets if item.get("player_out") is not None]
                actual_delivery = delivery.get("actual_delivery")
                delivery_rows.append({
                    "delivery_key": f"{match_id}:{innings_number}:{over_number}:{delivery_in_over}",
                    "match_id": match_id, "source_match_id": path.stem, "competition": competition,
                    "source_path": source_path,
                    "season": str(info["season"]) if info.get("season") is not None else None,
                    "innings_number": innings_number, "innings_team": innings_data.get("team"),
                    "is_super_over": bool(innings_data.get("super_over", False)),
                    "over_number": over_number, "delivery_in_over": delivery_in_over,
                    "actual_delivery": str(actual_delivery) if actual_delivery is not None else None,
                    "ball_in_over": _parse_ball_number(actual_delivery),
                    "legal_ball_number": legal_ball_number if is_legal else None,
                    "is_legal_ball": is_legal, "batter": delivery.get("batter"),
                    "bowler": delivery.get("bowler"), "non_striker": delivery.get("non_striker"),
                    "batter_runs": runs.get("batter", 0), "extra_runs": runs.get("extras", 0),
                    "total_runs": runs.get("total", 0), "byes_runs": extras.get("byes", 0),
                    "legbyes_runs": extras.get("legbyes", 0), "noballs_runs": extras.get("noballs", 0),
                    "penalty_runs": extras.get("penalty", 0), "wides_runs": extras.get("wides", 0),
                    "dismissal_count": len(wickets), "dismissal_type": "|".join(dismissal_types) or None,
                    "dismissal_player_out": "|".join(dismissal_players) or None,
                    "wickets_json": _json_value(wickets), "extras_json": _json_value(extras),
                    "review_json": _json_value(delivery.get("review")),
                    "replacements_json": _json_value(delivery.get("replacements")),
                })
    return match_row, delivery_rows


def validate_normalized_tables(matches: pd.DataFrame, deliveries: pd.DataFrame) -> dict[str, int]:
    """Validate keys, ordering, ball semantics, and match bounds."""
    if matches["match_id"].duplicated().any():
        raise ValueError("Duplicate match_id values detected")
    if deliveries["delivery_key"].duplicated().any():
        raise ValueError("Duplicate delivery_key values detected")
    if not set(deliveries["match_id"]).issubset(set(matches["match_id"])):
        raise ValueError("Delivery rows reference unknown matches")

    illegal = (deliveries["wides_runs"].fillna(0) > 0) | (deliveries["noballs_runs"].fillna(0) > 0)
    if (deliveries["is_legal_ball"] != ~illegal).any():
        raise ValueError("Legal-ball flags are inconsistent with wides/no-balls")

    order_columns = ["match_id", "innings_number", "over_number", "delivery_in_over"]
    if not pd.MultiIndex.from_frame(deliveries[order_columns]).is_monotonic_increasing:
        raise ValueError("Delivery rows are not in deterministic cricket order")

    legal_rows = deliveries.loc[deliveries["is_legal_ball"], [
        "match_id", "innings_number", "legal_ball_number"
    ]]
    for _, legal_group in legal_rows.groupby(["match_id", "innings_number"], sort=False):
        legal = legal_group["legal_ball_number"].tolist()
        if legal != list(range(1, len(legal) + 1)):
            raise ValueError("Legal-ball sequence contains a gap or reset")

    match_lookup = matches.set_index("match_id").to_dict(orient="index")
    per_over = deliveries.groupby(
        ["match_id", "innings_number", "over_number"], sort=False, observed=True
    )["is_legal_ball"].sum()
    for (match_id, innings_number, over_number), observed in per_over.items():
        match = match_lookup[match_id]
        expected = _expected_over_balls(match, int(innings_number), int(over_number))
        if int(observed) > expected:
            raise ValueError("Legal-ball count exceeds the source-declared over capacity")

    return {
        "matches": len(matches), "deliveries": len(deliveries),
        "legal_deliveries": int(deliveries["is_legal_ball"].sum()),
        "illegal_deliveries": int((~deliveries["is_legal_ball"]).sum()),
        "dismissal_events": int(deliveries["dismissal_count"].sum()),
        "extra_events": int((deliveries["extra_runs"] > 0).sum()),
    }


def normalize_raw_data(raw_root: str | Path | None = None, output_dir: str | Path | None = None) -> dict[str, Any]:
    """Normalize all raw Cricsheet matches and write interim Parquet outputs."""
    root = resolve_path(raw_root or "data/raw/cricsheet")
    destination = resolve_path(output_dir or "data/interim")
    if not root.is_dir():
        raise FileNotFoundError(f"Cricsheet raw directory not found: {root}")

    match_rows: list[dict[str, Any]] = []
    delivery_rows: list[dict[str, Any]] = []
    for competition, path in _iter_match_files(root):
        match_row, parsed_deliveries = parse_match(path, competition)
        match_rows.append(match_row)
        delivery_rows.extend(parsed_deliveries)

    matches = _nullable_frame(match_rows, MATCH_COLUMNS)
    deliveries = _nullable_frame(delivery_rows, DELIVERY_COLUMNS)
    validation = validate_normalized_tables(matches, deliveries)
    destination.mkdir(parents=True, exist_ok=True)
    matches_path = destination / "matches.parquet"
    deliveries_path = destination / "deliveries.parquet"
    matches.to_parquet(matches_path, index=False, engine="pyarrow")
    deliveries.to_parquet(deliveries_path, index=False, engine="pyarrow")
    return {
        "matches_path": matches_path, "deliveries_path": deliveries_path,
        "validation": validation, "match_columns": MATCH_COLUMNS,
        "delivery_columns": DELIVERY_COLUMNS,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", default="data/raw/cricsheet")
    parser.add_argument("--output-dir", default="data/interim")
    args = parser.parse_args()
    result = normalize_raw_data(args.raw_root, args.output_dir)
    print(json.dumps({key: str(value) for key, value in result.items()}, default=str))


if __name__ == "__main__":
    main()