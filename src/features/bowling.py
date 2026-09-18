"""
Phase 4.2: Bowling Features.

Inputs: data/processed/fact_deliveries.parquet
Output: data/features/bowling_features.parquet (grain: player x season)

Reuses `is_bowler_credited` and `BOWLER_CREDITED_KINDS` from src.analytics.eda_bowling
to ensure consistent wicket crediting across the engine.
Reuses spell-gap identification from src.analytics.eda_bowling.

Metric definitions:
  - overs_bowled = legal_balls / 6 (fractional, unrounded float; uses is_legal_ball,
    NEVER is_legal_delivery).
  - runs_conceded = total_runs - byes_runs - legbyes_runs (excludes byes/leg-byes,
    includes wides and no-balls).
  - economy_rate = runs_conceded / overs_bowled (0.0 when overs_bowled == 0).
  - bowling_strike_rate = legal_balls / wickets. Guarded to NaN (not 0.0 or inf)
    when wickets == 0, matching cricket convention where un-dismissed rates are undefined.
  - dot_ball_pct = dot_balls / legal_balls * 100 (0.0 when legal_balls == 0).
  - boundary_concession_pct = (fours + sixes) / legal_balls * 100 (0.0 when legal_balls == 0).
  - wicket_rate_per_over = wickets / overs_bowled (0.0 when overs_bowled == 0).
  - economy_variance_across_spells = population variance (ddof=0) of per-spell
    economies within that player-season (0.0 when <= 1 spell).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.analytics.eda_bowling import BOWLER_CREDITED_KINDS, is_bowler_credited
from src.utils.config import get_project_root

SEASON_MIN = 2018
SEASON_MAX = 2026
QUALIFIED_OVERS_SEASON = 20.0  # 120 legal balls (~5 matches worth of 4-over quotas)


def prepare_fact(root: Path) -> pd.DataFrame:
    """Load and filter fact_deliveries to men's non-super-over resolved bowler records."""
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
    fact = fact[fact["bowler_canonical_id"].ne("UNRESOLVED")]
    print(
        f"Filtered to {SEASON_MIN}-{SEASON_MAX}, men's, non-super-over, resolved bowlers: "
        f"{len(fact):,} / {n_before:,} rows"
    )
    return fact


def compute_spell_variance(fact: pd.DataFrame) -> pd.DataFrame:
    """Calculate per-spell economy and compute variance across spells per (player, season)."""
    if len(fact) == 0:
        return pd.DataFrame(columns=["player_id", "start_year", "economy_variance_across_spells"])

    d = fact.copy()
    d["bowler_runs"] = d["total_runs"].fillna(0) - d["byes_runs"].fillna(0) - d["legbyes_runs"].fillna(0)
    d["is_legal_ball_int"] = d["is_legal_ball"].fillna(False).astype(int)

    # Over-level aggregation
    over_agg = (
        d.groupby(
            ["bowler_canonical_id", "bowler_canonical_name", "match_id", "innings_number", "over_number", "start_year"],
            dropna=False,
        )
        .agg(
            legal_balls=("is_legal_ball_int", "sum"),
            runs=("bowler_runs", "sum"),
        )
        .reset_index()
    )

    over_agg = over_agg.sort_values(
        ["bowler_canonical_id", "match_id", "innings_number", "over_number"]
    ).reset_index(drop=True)

    grp_keys = ["bowler_canonical_id", "match_id", "innings_number"]
    gap = over_agg.groupby(grp_keys)["over_number"].diff().fillna(99) > 1
    over_agg["spell_id"] = gap.groupby([over_agg[k] for k in grp_keys]).cumsum()

    spells = (
        over_agg.groupby(
            ["bowler_canonical_id", "start_year", "match_id", "innings_number", "spell_id"],
            dropna=False,
        )
        .agg(
            legal_balls=("legal_balls", "sum"),
            runs=("runs", "sum"),
        )
        .reset_index()
    )

    spells = spells[spells["legal_balls"] > 0].copy()
    spells["spell_economy"] = spells["runs"] / (spells["legal_balls"] / 6.0)

    # Population variance (ddof=0) across spells in each player-season
    var_df = (
        spells.groupby(["bowler_canonical_id", "start_year"])["spell_economy"]
        .agg(lambda s: float(np.var(s, ddof=0)) if len(s) > 1 else 0.0)
        .reset_index()
        .rename(
            columns={
                "bowler_canonical_id": "player_id",
                "spell_economy": "economy_variance_across_spells",
            }
        )
    )
    return var_df


def compute_bowling_features(fact: pd.DataFrame) -> pd.DataFrame:
    """Compute season bowling metrics from delivery-level fact data."""
    if len(fact) == 0:
        return pd.DataFrame(
            columns=[
                "player_id", "player_name", "start_year", "legal_balls", "overs_bowled",
                "runs_conceded", "wickets", "economy_rate", "bowling_strike_rate",
                "dot_ball_pct", "boundary_concession_pct", "wicket_rate_per_over",
                "economy_variance_across_spells",
            ]
        )

    d = fact.copy()
    d["bowler_runs"] = d["total_runs"].fillna(0) - d["byes_runs"].fillna(0) - d["legbyes_runs"].fillna(0)
    d["is_legal_ball_int"] = d["is_legal_ball"].fillna(False).astype(int)
    
    d["bowler_wicket"] = (
        d["is_wicket"].astype(bool) & d["dismissal_type"].apply(is_bowler_credited)
    ).astype(int)

    d["dots"] = d["is_dot_ball"].fillna(0).astype(int)
    d["fours"] = d["is_boundary_four"].fillna(0).astype(int)
    d["sixes"] = d["is_boundary_six"].fillna(0).astype(int)

    stats = (
        d.groupby(
            ["bowler_canonical_id", "bowler_canonical_name", "start_year"],
            dropna=False,
        )
        .agg(
            legal_balls=("is_legal_ball_int", "sum"),
            runs_conceded=("bowler_runs", "sum"),
            wickets=("bowler_wicket", "sum"),
            dots=("dots", "sum"),
            fours=("fours", "sum"),
            sixes=("sixes", "sum"),
        )
        .reset_index()
        .rename(
            columns={
                "bowler_canonical_id": "player_id",
                "bowler_canonical_name": "player_name",
            }
        )
    )

    spell_var = compute_spell_variance(fact)
    df = stats.merge(spell_var, on=["player_id", "start_year"], how="left")
    df["economy_variance_across_spells"] = df["economy_variance_across_spells"].fillna(0.0)

    # Core mathematical formulas
    df["overs_bowled"] = df["legal_balls"] / 6.0
    has_balls = df["legal_balls"] > 0
    has_wickets = df["wickets"] > 0

    df["economy_rate"] = np.where(has_balls, df["runs_conceded"] / df["overs_bowled"], 0.0)
    df["bowling_strike_rate"] = np.where(has_wickets, df["legal_balls"] / df["wickets"], np.nan)
    df["dot_ball_pct"] = np.where(has_balls, (df["dots"] / df["legal_balls"]) * 100.0, 0.0)
    df["boundary_concession_pct"] = np.where(
        has_balls, ((df["fours"] + df["sixes"]) / df["legal_balls"]) * 100.0, 0.0
    )
    df["wicket_rate_per_over"] = np.where(has_balls, df["wickets"] / df["overs_bowled"], 0.0)

    return df


def main() -> Path:
    root = get_project_root()
    out_dir = root / "data" / "features"
    out_dir.mkdir(parents=True, exist_ok=True)

    fact = prepare_fact(root)

    # Dual scope: all_t20_2018_2026 + ipl_2018_2026
    all_feats = compute_bowling_features(fact)
    all_feats["scope"] = "all_t20_2018_2026"

    ipl_fact = fact.loc[fact["competition"].eq("ipl")]
    ipl_feats = compute_bowling_features(ipl_fact)
    ipl_feats["scope"] = "ipl_2018_2026"

    features = pd.concat([all_feats, ipl_feats], ignore_index=True)
    features["qualified"] = features["overs_bowled"] >= QUALIFIED_OVERS_SEASON

    cols = [
        "scope",
        "player_id",
        "player_name",
        "start_year",
        "qualified",
        "overs_bowled",
        "legal_balls",
        "runs_conceded",
        "wickets",
        "economy_rate",
        "bowling_strike_rate",
        "dot_ball_pct",
        "boundary_concession_pct",
        "wicket_rate_per_over",
        "economy_variance_across_spells",
    ]
    features = features[cols].sort_values(["scope", "player_name", "start_year"]).reset_index(drop=True)

    out_path = out_dir / "bowling_features.parquet"
    features.to_parquet(out_path, index=False)
    print(f"Saved: {out_path} ({len(features):,} rows: {len(all_feats):,} all_t20 + {len(ipl_feats):,} ipl)")
    return out_path


if __name__ == "__main__":
    main()
