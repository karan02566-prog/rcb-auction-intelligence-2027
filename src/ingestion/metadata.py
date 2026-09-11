from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
METADATA_DIR = RAW_DIR / "metadata"
CRICSHEET_DIR = RAW_DIR / "cricsheet"


def load_people_register(path: Path | None = None) -> pd.DataFrame:
    """Load the immutable Cricsheet People Register."""
    path = path or RAW_DIR / "people.csv"

    if not path.exists():
        raise FileNotFoundError(f"People register not found: {path}")

    df = pd.read_csv(path, dtype=str, keep_default_na=False)

    required = {"identifier", "name", "unique_name"}

    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"People register is missing required columns: {sorted(missing)}"
        )

    return df


def build_player_identity_table(
    people_df: pd.DataFrame,
) -> pd.DataFrame:
    """Create the canonical player identity table.

    Only fields actually supplied by the Cricsheet People Register
    are retained. Missing biographical information is not fabricated.
    """
    columns = [
        "identifier",
        "name",
        "unique_name",
        "key_bcci",
        "key_bcci_2",
        "key_bigbash",
        "key_cricbuzz",
        "key_cricheroes",
        "key_crichq",
        "key_cricinfo",
        "key_cricinfo_2",
        "key_cricinfo_3",
        "key_cricingif",
        "key_cricketarchive",
        "key_cricketarchive_2",
        "key_cricketworld",
        "key_nvplay",
        "key_nvplay_2",
        "key_opta",
        "key_opta_2",
        "key_pulse",
        "key_pulse_2",
    ]

    available = [column for column in columns if column in people_df.columns]

    result = people_df[available].copy()
    result = result.drop_duplicates(subset=["identifier"])

    return result


def _iter_match_files(root: Path):
    """Yield Cricsheet JSON match files from a competition directory."""
    if not root.exists():
        return

    yield from sorted(root.glob("*.json"))


def extract_match_participation(
    competition_root: Path,
    competition_name: str,
) -> pd.DataFrame:
    """Extract player/team/season participation from Cricsheet JSON."""
    records: list[dict[str, Any]] = []

    for path in _iter_match_files(competition_root):
        with path.open("r", encoding="utf-8") as handle:
            match = json.load(handle)

        info = match.get("info", {})

        season = info.get("season")
        dates = info.get("dates", [])
        venue = info.get("venue")
        city = info.get("city")
        teams = info.get("teams", [])
        players = info.get("players", {})

        for team, team_players in players.items():
            for player_name in team_players:
                records.append(
                    {
                        "competition": competition_name,
                        "season": str(season) if season is not None else None,
                        "match_id": path.stem,
                        "player_name": player_name,
                        "team": team,
                        "match_date": dates[0] if dates else None,
                        "venue": venue,
                        "city": city,
                    }
                )

        if not players:
            for team in teams:
                records.append(
                    {
                        "competition": competition_name,
                        "season": str(season) if season is not None else None,
                        "match_id": path.stem,
                        "player_name": None,
                        "team": team,
                        "match_date": dates[0] if dates else None,
                        "venue": venue,
                        "city": city,
                    }
                )

    return pd.DataFrame(records)


def build_competition_participation() -> pd.DataFrame:
    """Build participation metadata for all acquired Cricsheet competitions."""
    competition_map = {
        "ipl": "Indian Premier League",
        "sma": "Syed Mushtaq Ali Trophy",
        "bbl": "Big Bash League",
        "cpl": "Caribbean Premier League",
        "sat": "SA20",
        "ilt": "International League T20",
        "mlc": "Major League Cricket",
        "hnd": "The Hundred",
    }

    frames: list[pd.DataFrame] = []

    for code, competition in competition_map.items():
        root = CRICSHEET_DIR / code
        frame = extract_match_participation(root, competition)

        if not frame.empty:
            frames.append(frame)

    if not frames:
        return pd.DataFrame(
            columns=[
                "competition",
                "season",
                "match_id",
                "player_name",
                "team",
                "match_date",
                "venue",
                "city",
            ]
        )

    return pd.concat(frames, ignore_index=True)


def build_player_competition_summary(
    participation_df: pd.DataFrame,
) -> pd.DataFrame:
    """Aggregate participation into player/competition/season metadata."""
    df = participation_df.dropna(subset=["player_name"]).copy()

    if df.empty:
        return pd.DataFrame()

    summary = (
        df.groupby(
            ["competition", "season", "player_name"],
            dropna=False,
        )
        .agg(
            matches=("match_id", "nunique"),
            teams=("team", "nunique"),
            first_match_date=("match_date", "min"),
            last_match_date=("match_date", "max"),
        )
        .reset_index()
    )

    return summary.sort_values(
        ["competition", "season", "player_name"]
    ).reset_index(drop=True)


def write_metadata_outputs() -> dict[str, Path]:
    """Build and write Phase 1.3 metadata outputs."""
    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    people = load_people_register()

    identity = build_player_identity_table(people)
    participation = build_competition_participation()
    summary = build_player_competition_summary(participation)

    identity_path = METADATA_DIR / "player_identity.csv"
    participation_path = METADATA_DIR / "player_participation.csv"
    summary_path = METADATA_DIR / "player_competition_summary.csv"

    identity.to_csv(identity_path, index=False)
    participation.to_csv(participation_path, index=False)
    summary.to_csv(summary_path, index=False)

    return {
        "player_identity": identity_path,
        "player_participation": participation_path,
        "player_competition_summary": summary_path,
    }


if __name__ == "__main__":
    outputs = write_metadata_outputs()

    for name, path in outputs.items():
        print(f"{name}: {path}")