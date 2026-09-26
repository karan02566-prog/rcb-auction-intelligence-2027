"""
Phase 6.2: Performance Threshold & Role Alignment Filtering.

KNOWN LIMITATION (Phase 5 deferred): the spec calls for filtering against
configs/target_role_profiles.json (Phase 5.5 output), which doesn't
exist. In its place, this stage filters against the global median
league-adjusted performance among Stage 1-passed candidates in each
discipline -- not role-specific thresholds. Must be re-applied with real
role profiles once Phase 5 unblocks.

Inputs: data/interim/funnel_stage1_sample.parquet (passes_stage1 == True rows),
        data/processed/fact_deliveries.parquet, configs/league_strength_factors.json
Output: data/interim/funnel_stage2_performance.parquet, updates reports/funnel_audit.json

League adjustment formula (reused exactly from Phase 4.9's
src/analytics/league_adjustment.py, NOT re-derived): adjusted_batting_avg =
raw_avg * M_batting; adjusted_economy = raw_economy * M_bowling. Computed
here per-competition on the RECENT window (2025+2026, matching Stage 1),
not the full 2018-2026 pooled window that Phase 4.9 used -- Phase 4.9's own
league_adjusted_features.parquet uses NaN (not 1.0, corrected from an
earlier assumption) for all_t20-scope rows and can't be reused directly.

Cross-competition combination: per player, adjusted runs (raw runs *
M_batting) are summed across every competition played in the recent
window, divided by summed dismissals -- equivalent to a dismissals-weighted
average of each competition's adjusted average. Same pattern for economy,
weighted by overs bowled.

Pass condition (Stage 2): a candidate passes if EITHER of their eligible
disciplines (as determined by Stage 1's meets_batting_threshold /
meets_bowling_threshold) clears the global median for that discipline --
batting: adjusted_avg >= median; bowling: adjusted_economy <= median
(lower is better). A batter with 0 dismissals (adjusted_avg is NaN, never
dismissed) passes the batting check automatically -- undefined-by-never-out
is not "below median."
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.utils.config import get_project_root

RECENT_SEASONS = [2025, 2026]
SEASON_MIN = 2018
SEASON_MAX = 2026


def prepare_recent_fact(root: Path) -> pd.DataFrame:
    processed = root / "data" / "processed"
    fact = pd.read_parquet(processed / "fact_deliveries.parquet")
    if "start_year" not in fact.columns:
        dim_comp = pd.read_parquet(processed / "dim_competitions.parquet")
        fact = fact.merge(dim_comp[["competition_id", "start_year"]], on="competition_id", how="left")
    matches_gender = pd.read_parquet(root / "data" / "interim" / "matches.parquet")[["match_id", "gender"]]
    fact = fact.merge(matches_gender, on="match_id", how="left")
    fact = fact[fact["gender"] == "male"]
    fact = fact[fact["start_year"].isin(RECENT_SEASONS)]
    fact = fact[~fact["is_super_over"].fillna(False)]
    return fact


def compute_adjusted_batting(fact: pd.DataFrame, factors: dict) -> pd.DataFrame:
    bat = fact[fact["batter_canonical_id"].ne("UNRESOLVED")].copy()
    bat["own_dismissal"] = (bat["is_wicket"] == 1) & (bat["dismissal_player_out"] == bat["batter"])
    agg = (
        bat.groupby(["batter_canonical_id", "competition"])
        .agg(runs=("batter_runs", "sum"), dismissals=("own_dismissal", "sum"))
        .reset_index()
        .rename(columns={"batter_canonical_id": "player_id"})
    )
    agg["M_batting"] = agg["competition"].map(lambda c: factors.get(c, {}).get("M_batting"))
    agg["adjusted_runs"] = agg["runs"] * agg["M_batting"]

    totals = agg.groupby("player_id").agg(
        adjusted_runs_sum=("adjusted_runs", "sum"),
        dismissals_sum=("dismissals", "sum"),
    ).reset_index()
    totals["adjusted_batting_avg"] = np.where(
        totals["dismissals_sum"] > 0, totals["adjusted_runs_sum"] / totals["dismissals_sum"], np.nan
    )
    return totals[["player_id", "adjusted_batting_avg"]]


def compute_adjusted_bowling(fact: pd.DataFrame, factors: dict) -> pd.DataFrame:
    bowl = fact[fact["bowler_canonical_id"].ne("UNRESOLVED")].copy()
    bowl["bowler_runs"] = bowl["total_runs"].fillna(0) - bowl["byes_runs"].fillna(0) - bowl["legbyes_runs"].fillna(0)
    bowl["legal"] = bowl["is_legal_ball"].fillna(False).astype(int)
    agg = (
        bowl.groupby(["bowler_canonical_id", "competition"])
        .agg(runs_conceded=("bowler_runs", "sum"), legal_balls=("legal", "sum"))
        .reset_index()
        .rename(columns={"bowler_canonical_id": "player_id"})
    )
    agg["overs"] = agg["legal_balls"] / 6.0
    agg["M_bowling"] = agg["competition"].map(lambda c: factors.get(c, {}).get("M_bowling"))
    agg["adjusted_runs_conceded"] = agg["runs_conceded"] * agg["M_bowling"]

    totals = agg.groupby("player_id").agg(
        adjusted_runs_conceded_sum=("adjusted_runs_conceded", "sum"),
        overs_sum=("overs", "sum"),
    ).reset_index()
    totals["adjusted_economy"] = np.where(
        totals["overs_sum"] > 0, totals["adjusted_runs_conceded_sum"] / totals["overs_sum"], np.nan
    )
    return totals[["player_id", "adjusted_economy"]]


def apply_stage2_filter(stage1: pd.DataFrame, adj_bat: pd.DataFrame, adj_bowl: pd.DataFrame) -> pd.DataFrame:
    df = stage1.loc[stage1["passes_stage1"]].copy()
    df = df.merge(adj_bat, on="player_id", how="left")
    df = df.merge(adj_bowl, on="player_id", how="left")

    bat_median = df.loc[df["meets_batting_threshold"], "adjusted_batting_avg"].median()
    bowl_median = df.loc[df["meets_bowling_threshold"], "adjusted_economy"].median()

    batting_ok = (
        ~df["meets_batting_threshold"]
        | df["adjusted_batting_avg"].isna()  # never dismissed -- not "below median"
        | (df["adjusted_batting_avg"] >= bat_median)
    )
    bowling_ok = (
        ~df["meets_bowling_threshold"]
        | (df["adjusted_economy"] <= bowl_median)
    )
    eligible_batting = df["meets_batting_threshold"]
    eligible_bowling = df["meets_bowling_threshold"]

    df["passes_stage2"] = np.where(
        eligible_batting | eligible_bowling,
        (eligible_batting & batting_ok) | (eligible_bowling & bowling_ok),
        False,
    )
    df["batting_median_used"] = bat_median
    df["bowling_median_used"] = bowl_median
    return df


def main() -> Path:
    root = get_project_root()
    interim_dir = root / "data" / "interim"

    stage1 = pd.read_parquet(interim_dir / "funnel_stage1_sample.parquet")
    with open(root / "configs" / "league_strength_factors.json") as f:
        factors = json.load(f)

    fact = prepare_recent_fact(root)
    adj_bat = compute_adjusted_batting(fact, factors)
    adj_bowl = compute_adjusted_bowling(fact, factors)

    result = apply_stage2_filter(stage1, adj_bat, adj_bowl)

    n_in = int(stage1["passes_stage1"].sum())
    n_passed = int(result["passes_stage2"].sum())
    n_dropped = n_in - n_passed

    out_path = interim_dir / "funnel_stage2_performance.parquet"
    result.to_parquet(out_path, index=False)

    audit_path = root / "reports" / "funnel_audit.json"
    audit = json.loads(audit_path.read_text()) if audit_path.exists() else {}
    audit["stage2_performance_filter"] = {
        "provisional_note": "no target_role_profiles.json input (Phase 5 deferred); "
                             "filtered against global median of Stage 1-passed candidates "
                             "per discipline, not role-specific thresholds",
        "recent_seasons_used": RECENT_SEASONS,
        "batting_median_adjusted_avg": None if pd.isna(result["batting_median_used"].iloc[0]) else float(result["batting_median_used"].iloc[0]),
        "bowling_median_adjusted_economy": None if pd.isna(result["bowling_median_used"].iloc[0]) else float(result["bowling_median_used"].iloc[0]),
        "stage1_input_count": n_in,
        "passed_stage2": n_passed,
        "dropped_stage2": n_dropped,
    }
    audit_path.write_text(json.dumps(audit, indent=2))

    print(f"Stage 1 input: {n_in:,} | Passed Stage 2: {n_passed:,} | Dropped: {n_dropped:,}")
    print(f"Saved: {out_path}")
    return out_path


if __name__ == "__main__":
    main()
