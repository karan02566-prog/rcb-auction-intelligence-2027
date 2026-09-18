"""
Phase 4.4: Phase-wise performance features (Powerplay/Middle/Death).

Inputs: data/processed/fact_deliveries.parquet
Output: data/features/phase_features.parquet (grain: player x season x phase)

Reuses the existing `phase` column (built in build_delivery_features.py) rather
than re-deriving PP/Middle/Death from over_number, avoiding the off-by-one
failure mode named in the spec.

NaN policy: rates (strike_rate, economy, dot_pct, boundary_pct) are NaN when
the relevant ball count is 0 for that player-season-phase (undefined, not 0.0).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.analytics.eda_bowling import is_bowler_credited
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
    print(f"Filtered to {SEASON_MIN}-{SEASON_MAX}, men's, non-super-over: {len(fact):,} / {n_before:,} rows")
    return fact


def compute_batting_phase(fact: pd.DataFrame) -> pd.DataFrame:
    d = fact[fact["batter_canonical_id"].ne("UNRESOLVED")].copy()
    d["dot"] = d["is_dot_ball"].fillna(0).astype(int)
    d["boundary"] = ((d["is_boundary_four"].fillna(0) > 0) | (d["is_boundary_six"].fillna(0) > 0)).astype(int)
    d["legal_bat"] = d["is_legal_delivery"].fillna(0).astype(int)

    g = (
        d.groupby(["batter_canonical_id", "batter_canonical_name", "start_year", "phase"], dropna=False)
        .agg(
            batting_runs=("batter_runs", "sum"),
            batting_balls=("legal_bat", "sum"),
            batting_dots=("dot", "sum"),
            batting_boundaries=("boundary", "sum"),
        )
        .reset_index()
        .rename(columns={"batter_canonical_id": "player_id", "batter_canonical_name": "player_name"})
    )

    has_balls = g["batting_balls"] > 0
    g["batting_strike_rate"] = np.where(has_balls, g["batting_runs"] / g["batting_balls"] * 100.0, np.nan)
    g["batting_dot_pct"] = np.where(has_balls, g["batting_dots"] / g["batting_balls"] * 100.0, np.nan)
    g["batting_boundary_pct"] = np.where(has_balls, g["batting_boundaries"] / g["batting_balls"] * 100.0, np.nan)
    return g


def compute_bowling_phase(fact: pd.DataFrame) -> pd.DataFrame:
    d = fact[fact["bowler_canonical_id"].ne("UNRESOLVED")].copy()
    d["bowler_runs"] = d["total_runs"].fillna(0) - d["byes_runs"].fillna(0) - d["legbyes_runs"].fillna(0)
    d["legal_bowl"] = d["is_legal_ball"].fillna(False).astype(int)
    wicket_flag = d["is_wicket"].astype(bool)
    credited = d["dismissal_type"].apply(is_bowler_credited)
    d["bowler_wicket"] = (wicket_flag & credited).astype(int)
    d["dot"] = d["is_dot_ball"].fillna(0).astype(int)
    d["boundary"] = ((d["is_boundary_four"].fillna(0) > 0) | (d["is_boundary_six"].fillna(0) > 0)).astype(int)

    g = (
        d.groupby(["bowler_canonical_id", "bowler_canonical_name", "start_year", "phase"], dropna=False)
        .agg(
            bowling_legal_balls=("legal_bowl", "sum"),
            bowling_runs_conceded=("bowler_runs", "sum"),
            bowling_wickets=("bowler_wicket", "sum"),
            bowling_dots=("dot", "sum"),
            bowling_boundaries=("boundary", "sum"),
        )
        .reset_index()
        .rename(columns={"bowler_canonical_id": "player_id", "bowler_canonical_name": "player_name"})
    )

    g["bowling_overs"] = g["bowling_legal_balls"] / 6.0
    has_balls = g["bowling_legal_balls"] > 0
    g["bowling_economy"] = np.where(has_balls, g["bowling_runs_conceded"] / g["bowling_overs"], np.nan)
    g["bowling_dot_pct"] = np.where(has_balls, g["bowling_dots"] / g["bowling_legal_balls"] * 100.0, np.nan)
    g["bowling_boundary_pct"] = np.where(has_balls, g["bowling_boundaries"] / g["bowling_legal_balls"] * 100.0, np.nan)
    return g


def compute_phase_features(fact: pd.DataFrame) -> pd.DataFrame:
    bat = compute_batting_phase(fact)
    bowl = compute_bowling_phase(fact)
    return pd.merge(bat, bowl, on=["player_id", "player_name", "start_year", "phase"], how="outer")


def main() -> Path:
    root = get_project_root()
    out_dir = root / "data" / "features"
    out_dir.mkdir(parents=True, exist_ok=True)

    fact = prepare_fact(root)

    all_feats = compute_phase_features(fact)
    all_feats["scope"] = "all_t20_2018_2026"

    ipl_fact = fact.loc[fact["competition"].eq("ipl")]
    ipl_feats = compute_phase_features(ipl_fact)
    ipl_feats["scope"] = "ipl_2018_2026"

    features = pd.concat([all_feats, ipl_feats], ignore_index=True)
    cols = [
        "scope", "player_id", "player_name", "start_year", "phase",
        "batting_runs", "batting_balls", "batting_strike_rate", "batting_dot_pct", "batting_boundary_pct",
        "bowling_legal_balls", "bowling_overs", "bowling_runs_conceded", "bowling_wickets",
        "bowling_economy", "bowling_dot_pct", "bowling_boundary_pct",
    ]
    features = features[cols].sort_values(["scope", "player_name", "start_year", "phase"]).reset_index(drop=True)

    out_path = out_dir / "phase_features.parquet"
    features.to_parquet(out_path, index=False)
    print(f"Saved: {out_path} ({len(features):,} rows)")
    return out_path


if __name__ == "__main__":
    main()
