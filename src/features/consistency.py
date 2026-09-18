"""
Phase 4.3: Consistency Features.

Inputs: data/processed/fact_deliveries.parquet
Output: data/features/consistency_features.parquet (grain: player x season)

Computes percentile-based outcome distributions, floor/ceiling metrics,
and transparent rule-based consistency badges per PRD §5 and Phase 4.3.

Definitions:
  - Unit of observation for score: batting innings (runs scored per innings).
  - P10, P25, P50, P75, P90: percentiles of innings runs distribution.
  - median_score: median innings runs; asserted equal to P50.
  - failure_rate: share of batting innings with score < 10 runs.
  - high_impact_rate: share of appearances with score > 45 runs OR 3+ wicket spells.
  - Consistency badges (100% coverage of qualified players, zero nulls):
      * Elite: low failure rate (<= 0.35) AND high impact rate (>= 0.20)
      * High Floor: low failure rate (<= 0.40) AND moderate impact (< 0.20)
      * Boom-or-Bust: high failure rate (> 0.35) AND high impact rate (>= 0.20)
      * Moderate: remaining qualified players (failure > 0.40 and impact < 0.20)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.analytics.eda_bowling import is_bowler_credited
from src.utils.config import get_project_root

SEASON_MIN = 2018
SEASON_MAX = 2026

# Explicit, traceable badge thresholds
QUALIFIED_INNINGS_SEASON = 10  # Minimum innings to evaluate distribution shape
ELITE_MAX_FAILURE_RATE = 0.35
ELITE_MIN_HIGH_IMPACT_RATE = 0.20
HIGH_FLOOR_MAX_FAILURE_RATE = 0.40
BOOM_MIN_HIGH_IMPACT_RATE = 0.20


def prepare_fact(root: Path) -> pd.DataFrame:
    """Load and filter fact_deliveries to men's non-super-over deliveries."""
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
    print(
        f"Filtered to {SEASON_MIN}-{SEASON_MAX}, men's, non-super-over: "
        f"{len(fact):,} / {n_before:,} rows"
    )
    return fact


def build_player_match_performances(fact: pd.DataFrame) -> pd.DataFrame:
    """Aggregate batting innings runs and bowling match wickets per (player, match)."""
    # Batting innings aggregation
    d_bat = fact[fact["batter_canonical_id"].ne("UNRESOLVED")].copy()
    bat_agg = (
        d_bat.groupby(
            ["batter_canonical_id", "batter_canonical_name", "match_id", "start_year"],
            dropna=False,
        )
        .agg(
            runs=("batter_runs", "sum"),
            balls_faced=("is_legal_delivery", "sum"),
        )
        .reset_index()
        .rename(
            columns={
                "batter_canonical_id": "player_id",
                "batter_canonical_name": "player_name",
            }
        )
    )

    # Bowling match aggregation (wickets credited to bowler in match)
    d_bowl = fact[fact["bowler_canonical_id"].ne("UNRESOLVED")].copy()
    d_bowl["bowler_wicket"] = (
        d_bowl["is_wicket"].astype(bool) & d_bowl["dismissal_type"].apply(is_bowler_credited)
    ).astype(int)
    bowl_agg = (
        d_bowl.groupby(
            ["bowler_canonical_id", "bowler_canonical_name", "match_id", "start_year"],
            dropna=False,
        )
        .agg(
            wickets=("bowler_wicket", "sum"),
        )
        .reset_index()
        .rename(
            columns={
                "bowler_canonical_id": "player_id",
                "bowler_canonical_name": "player_name",
            }
        )
    )

    # Full outer join to capture both batting and bowling contributions per match
    merged = pd.merge(
        bat_agg,
        bowl_agg,
        on=["player_id", "player_name", "match_id", "start_year"],
        how="outer",
    )
    merged["wickets"] = merged["wickets"].fillna(0).astype(int)
    # runs is NaN if player did not bat in that match
    return merged


def assign_consistency_badge(failure_rate: float, high_impact_rate: float, qualified: bool) -> str:
    """Assign rule-based consistency badge covering 100% of qualified players."""
    if not qualified:
        return "Unqualified"
    if np.isnan(failure_rate) or np.isnan(high_impact_rate):
        return "Unqualified"

    if failure_rate <= ELITE_MAX_FAILURE_RATE and high_impact_rate >= ELITE_MIN_HIGH_IMPACT_RATE:
        return "Elite"
    elif failure_rate <= HIGH_FLOOR_MAX_FAILURE_RATE and high_impact_rate < ELITE_MIN_HIGH_IMPACT_RATE:
        return "High Floor"
    elif failure_rate > ELITE_MAX_FAILURE_RATE and high_impact_rate >= BOOM_MIN_HIGH_IMPACT_RATE:
        return "Boom-or-Bust"
    else:
        return "Moderate"


def compute_consistency_features(fact: pd.DataFrame) -> pd.DataFrame:
    """Compute score percentiles, floor/ceiling metrics, and consistency badges."""
    if len(fact) == 0:
        return pd.DataFrame(
            columns=[
                "player_id", "player_name", "start_year", "matches_played", "innings_batted",
                "p10", "p25", "p50", "p75", "p90", "median_score",
                "failure_rate", "high_impact_rate", "qualified", "consistency_badge",
            ]
        )

    match_perf = build_player_match_performances(fact)

    records = []
    grouped = match_perf.groupby(["player_id", "player_name", "start_year"], dropna=False)

    for (player_id, player_name, start_year), group in grouped:
        matches_played = len(group)
        batted = group[group["runs"].notna()]
        innings_batted = len(batted)

        if innings_batted > 0:
            scores = batted["runs"].sort_values()
            p10 = float(scores.quantile(0.10))
            p25 = float(scores.quantile(0.25))
            p50 = float(scores.quantile(0.50))
            p75 = float(scores.quantile(0.75))
            p90 = float(scores.quantile(0.90))
            median_score = float(scores.median())

            # Verification check: P50 must equal computed median
            assert np.isclose(p50, median_score), (
                f"P50 ({p50}) does not equal median ({median_score}) for {player_name} ({player_id})"
            )

            failure_count = (scores < 10).sum()
            failure_rate = float(failure_count / innings_batted)
        else:
            p10 = p25 = p50 = p75 = p90 = median_score = failure_rate = np.nan

        # Denominator note: failure_rate uses innings_batted (batting-specific rate),
        # while high_impact_rate uses matches_played (includes bowling-only appearances).
        # This is intentional: failure is a batting-specific concept (you can only "fail"
        # if you batted), but high-impact credit should include bowling-only match
        # contributions (e.g. a pure bowler taking 3+ wickets), so it is scoped to all
        # match appearances rather than batting innings alone.
        # High-impact performances: score > 45 OR 3+ wicket spell in match
        high_impact_matches = ((group["runs"].fillna(0) > 45) | (group["wickets"] >= 3)).sum()
        high_impact_rate = float(high_impact_matches / matches_played) if matches_played > 0 else 0.0

        qualified = innings_batted >= QUALIFIED_INNINGS_SEASON
        badge = assign_consistency_badge(failure_rate, high_impact_rate, qualified)

        records.append(
            {
                "player_id": player_id,
                "player_name": player_name,
                "start_year": start_year,
                "matches_played": matches_played,
                "innings_batted": innings_batted,
                "p10": p10,
                "p25": p25,
                "p50": p50,
                "p75": p75,
                "p90": p90,
                "median_score": median_score,
                "failure_rate": failure_rate,
                "high_impact_rate": high_impact_rate,
                "qualified": qualified,
                "consistency_badge": badge,
            }
        )

    df = pd.DataFrame(records)
    return df


def main() -> Path:
    root = get_project_root()
    out_dir = root / "data" / "features"
    out_dir.mkdir(parents=True, exist_ok=True)

    fact = prepare_fact(root)

    # Dual scope: all_t20_2018_2026 + ipl_2018_2026
    all_feats = compute_consistency_features(fact)
    all_feats["scope"] = "all_t20_2018_2026"

    ipl_fact = fact.loc[fact["competition"].eq("ipl")]
    ipl_feats = compute_consistency_features(ipl_fact)
    ipl_feats["scope"] = "ipl_2018_2026"

    features = pd.concat([all_feats, ipl_feats], ignore_index=True)

    cols = [
        "scope",
        "player_id",
        "player_name",
        "start_year",
        "qualified",
        "matches_played",
        "innings_batted",
        "p10",
        "p25",
        "p50",
        "p75",
        "p90",
        "median_score",
        "failure_rate",
        "high_impact_rate",
        "consistency_badge",
    ]
    features = features[cols].sort_values(["scope", "player_name", "start_year"]).reset_index(drop=True)

    out_path = out_dir / "consistency_features.parquet"
    features.to_parquet(out_path, index=False)
    print(f"Saved: {out_path} ({len(features):,} rows: {len(all_feats):,} all_t20 + {len(ipl_feats):,} ipl)")
    return out_path


if __name__ == "__main__":
    main()
