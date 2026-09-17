"""
Phase 4.1: Batting Features.

Inputs: data/processed/fact_deliveries.parquet
Output: data/features/batting_features.parquet (grain: player x season)

Reuses `build_innings` from src.analytics.eda_batting for dismissal counts
(batting average needs outs-per-season; that pipe-separated-dismissal
parsing logic already exists and is tested there -- no reason to
re-derive it here).

Metric definitions (spec leaves some formulas implicit; stated explicitly
here per project convention):
  - batting_average = season runs / season dismissals. Undefined (NaN,
    matching real cricket convention) when dismissals == 0 -- a player
    never out has no average, not a 0 or inf.
  - strike_rate = runs / balls_faced * 100
  - dot_pct = dot balls / balls_faced * 100
  - boundary_pct = (fours + sixes) / balls_faced * 100
  - boundary_dependency = (4*fours + 6*sixes) / runs -- boundary runs are
    always a subset of total runs, so this is mathematically bounded to
    [0, 1] whenever runs > 0.
  - rotation_rate = (singles + doubles) / non_boundary_balls, where
    non_boundary_balls = balls_faced - fours - sixes (dots + 1s + 2s + 3s).
  - acceleration_rate = death-overs strike rate - powerplay strike rate,
    per player-season (phase column from build_delivery_features.py:
    Powerplay/Middle/Death). NaN (not 0.0) when a player faced zero balls
    in either phase that season -- there is no acceleration to report,
    that's a missing-data case, not a "no change" case.

Common failure modes guarded (per phase.md):
  - Division by zero on 0 balls faced: every rate defaults to 0.0, not NaN
    or a crash -- except batting_average (0 dismissals -> NaN by cricket
    convention, see above) and acceleration_rate (missing phase -> NaN).
  - boundary_dependency's numerator/denominator are both guarded
    separately from the shared balls_faced==0 case, since it's runs==0
    that zeroes it, not balls_faced==0.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.analytics.eda_batting import build_innings
from src.cleaning.apply_player_mapping import get_mapping_lookups
from src.utils.config import get_project_root

SEASON_MIN = 2018
SEASON_MAX = 2026


def prepare_fact(root: Path) -> pd.DataFrame:
    processed = root / "data" / "processed"
    fact = pd.read_parquet(processed / "fact_deliveries.parquet")
    if "start_year" not in fact.columns:
        dim_comp = pd.read_parquet(processed / "dim_competitions.parquet")
        fact = fact.merge(dim_comp[["competition_id", "start_year"]], on="competition_id", how="left")
    matches_gender = pd.read_parquet(root / "data" / "interim" / "matches.parquet")[["match_id", "gender"]]
    fact = fact.merge(matches_gender, on="match_id", how="left")
    n_before = len(fact)
    fact = fact[fact["gender"] == "male"]
    fact = fact[fact["start_year"].between(SEASON_MIN, SEASON_MAX)]
    fact = fact[~fact["is_super_over"].fillna(False)]
    fact = fact[fact["batter_canonical_id"].ne("UNRESOLVED")]
    print(f"Filtered to {SEASON_MIN}-{SEASON_MAX}, men's, non-super-over, resolved batters: "
          f"{len(fact):,} / {n_before:,} rows")
    return fact


def season_ball_stats(fact: pd.DataFrame) -> pd.DataFrame:
    """Ball-level aggregation, grain = (player, season)."""
    d = fact.copy()
    d["balls_faced"] = d["is_legal_delivery"].fillna(0).astype("int64")
    d["runs"] = d["batter_runs"].fillna(0).astype("int64")
    d["singles"] = ((d["batter_runs"] == 1) & (d["is_legal_delivery"] == 1)).astype("int64")
    d["doubles"] = ((d["batter_runs"] == 2) & (d["is_legal_delivery"] == 1)).astype("int64")

    grouped = d.groupby(
        ["batter_canonical_id", "batter_canonical_name", "start_year"], dropna=False
    ).agg(
        runs=("runs", "sum"),
        balls_faced=("balls_faced", "sum"),
        dots=("is_dot_ball", "sum"),
        fours=("is_boundary_four", "sum"),
        sixes=("is_boundary_six", "sum"),
        singles=("singles", "sum"),
        doubles=("doubles", "sum"),
    ).reset_index().rename(
        columns={"batter_canonical_id": "player_id", "batter_canonical_name": "player_name"}
    )
    return grouped


def season_phase_acceleration(fact: pd.DataFrame) -> pd.DataFrame:
    """Death-overs SR minus Powerplay SR, per (player, season). NaN if a
    player faced 0 balls in either phase that season."""
    d = fact.copy()
    d["balls_faced"] = d["is_legal_delivery"].fillna(0).astype("int64")
    d["runs"] = d["batter_runs"].fillna(0).astype("int64")
    phase_grp = d.groupby(
        ["batter_canonical_id", "start_year", "phase"], dropna=False
    ).agg(runs=("runs", "sum"), balls_faced=("balls_faced", "sum")).reset_index()
    phase_grp["sr"] = np.where(
        phase_grp["balls_faced"] > 0, phase_grp["runs"] / phase_grp["balls_faced"] * 100, np.nan
    )
    pivot = phase_grp.pivot_table(
        index=["batter_canonical_id", "start_year"], columns="phase", values="sr"
    ).reset_index().rename(columns={"batter_canonical_id": "player_id"})
    for col in ("Powerplay", "Death"):
        if col not in pivot.columns:
            pivot[col] = np.nan
    pivot["acceleration_rate"] = pivot["Death"] - pivot["Powerplay"]
    return pivot[["player_id", "start_year", "acceleration_rate"]]


def season_dismissals(fact: pd.DataFrame, exact_lookup: dict, norm_lookup: dict) -> pd.DataFrame:
    innings = build_innings(fact, exact_lookup, norm_lookup)
    return (
        innings.groupby(["player_id", "start_year"], dropna=False)["is_out"]
        .sum()
        .reset_index()
        .rename(columns={"is_out": "dismissals"})
    )


def compute_batting_features(fact: pd.DataFrame, exact_lookup: dict, norm_lookup: dict) -> pd.DataFrame:
    stats = season_ball_stats(fact)
    dismissals = season_dismissals(fact, exact_lookup, norm_lookup)
    accel = season_phase_acceleration(fact)

    df = stats.merge(dismissals, on=["player_id", "start_year"], how="left")
    df = df.merge(accel, on=["player_id", "start_year"], how="left")
    df["dismissals"] = df["dismissals"].fillna(0).astype("int64")

    has_balls = df["balls_faced"] > 0
    has_dismissals = df["dismissals"] > 0
    has_runs = df["runs"] > 0
    non_boundary_balls = df["balls_faced"] - df["fours"] - df["sixes"]
    has_non_boundary = non_boundary_balls > 0

    df["batting_average"] = np.where(has_dismissals, df["runs"] / df["dismissals"].replace(0, np.nan), np.nan)
    df["strike_rate"] = np.where(has_balls, df["runs"] / df["balls_faced"].replace(0, 1) * 100, 0.0)
    df["dot_pct"] = np.where(has_balls, df["dots"] / df["balls_faced"].replace(0, 1) * 100, 0.0)
    df["boundary_pct"] = np.where(
        has_balls, (df["fours"] + df["sixes"]) / df["balls_faced"].replace(0, 1) * 100, 0.0
    )
    df["boundary_dependency"] = np.where(
        has_runs, (4 * df["fours"] + 6 * df["sixes"]) / df["runs"].replace(0, 1), 0.0
    )
    df["rotation_rate"] = np.where(
        has_non_boundary, (df["singles"] + df["doubles"]) / non_boundary_balls.replace(0, 1), 0.0
    )

    return df


def validate_boundary_dependency(df: pd.DataFrame) -> None:
    bad = df.loc[~df["boundary_dependency"].between(0.0, 1.0)]
    if len(bad):
        raise AssertionError(f"boundary_dependency out of [0,1] bounds for {len(bad)} rows")


def main() -> Path:
    root = get_project_root()
    out_dir = root / "data" / "features"
    out_dir.mkdir(parents=True, exist_ok=True)

    fact = prepare_fact(root)
    exact_lookup, norm_lookup = get_mapping_lookups()
    if not exact_lookup:
        raise RuntimeError("player_mapping.json lookups are empty; run from the repo root")

    features = compute_batting_features(fact, exact_lookup, norm_lookup)
    validate_boundary_dependency(features)
    print(f"boundary_dependency bounds check passed: {len(features):,} player-seasons, all in [0,1]")

    cols = [
        "player_id", "player_name", "start_year", "runs", "balls_faced", "dismissals",
        "batting_average", "strike_rate", "dot_pct", "boundary_pct",
        "boundary_dependency", "rotation_rate", "acceleration_rate",
    ]
    features = features[cols].sort_values(["player_name", "start_year"]).reset_index(drop=True)

    out_path = out_dir / "batting_features.parquet"
    features.to_parquet(out_path, index=False)
    print(f"Saved: {out_path} ({len(features):,} player-season rows)")
    return out_path


if __name__ == "__main__":
    main()
