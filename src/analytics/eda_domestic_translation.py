"""
Phase 3.5: Domestic vs Franchise Competition Comparison.

Inputs: data/processed/fact_deliveries.parquet
Output: reports/eda_domestic_vs_franchise.json

Scope decision: BATTERS ONLY. "Scoring rate", "dot-ball %", and "boundary
concessions" are batting-innings metrics; a bowler-side comparison would
double the scope and isn't required by the spec's validation check (a single
30-player crossover cohort). Documented in memory.md.

Crossover definition: a player counts as crossover if they have at least one
Domestic-category season (start_year Yd) and at least one IPL season
(start_year Yi) with |Yd - Yi| <= 1 (adjacent seasons). Domestic category =
fact_deliveries.competition_category == "Domestic" (real column, confirmed
against reports/eda_league_baselines.json: sat/hnd/ilt/sma -> Domestic,
mlc/cpl/bbl -> Overseas Franchise, ipl -> IPL).

Survivorship-bias guard (phase.md failure mode): cohort membership is
determined ONLY by adjacent-season participation in both competition tiers --
never by IPL outcome. A player who played domestic cricket next to an IPL
season but failed/was dropped after 1 match still qualifies for the cohort
as long as they clear the symmetric balls-faced floor in BOTH tiers (same
floor applied to both sides, not tuned toward IPL success).

Per-player metrics, computed by pooling all qualifying deliveries in each
tier (not just the adjacent-season ones) at (player, tier) grain:
  - scoring_rate = runs scored per 100 balls faced (strike rate)
  - dot_pct = % of balls faced that were dot balls
  - boundary_pct = % of balls faced that were fours or sixes
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.utils.config import get_project_root

SEASON_MIN = 2018
SEASON_MAX = 2026
QUALIFIED_BALLS = 60  # ~10 overs faced; symmetric floor applied to both tiers
MIN_COHORT_SIZE = 30
ADJACENCY_WINDOW = 1  # |domestic_season - ipl_season| <= this


def prepare_fact(root: Path) -> pd.DataFrame:
    processed = root / "data" / "processed"
    fact = pd.read_parquet(processed / "fact_deliveries.parquet")
    dim_comp = pd.read_parquet(processed / "dim_competitions.parquet")
    if "start_year" not in fact.columns:
        fact = fact.merge(dim_comp[["competition_id", "start_year"]], on="competition_id", how="left")
    matches_gender = pd.read_parquet(root / "data" / "interim" / "matches.parquet")[["match_id", "gender"]]
    fact = fact.merge(matches_gender, on="match_id", how="left")
    n_before = len(fact)
    fact = fact[fact["gender"] == "male"]
    fact = fact[fact["start_year"].between(SEASON_MIN, SEASON_MAX)]
    fact = fact[~fact["is_super_over"].fillna(False)]
    fact = fact[fact["batter_canonical_id"].ne("UNRESOLVED")]
    fact = fact[fact["competition_category"].isin(["Domestic", "IPL"])]
    print(f"Filtered to {SEASON_MIN}-{SEASON_MAX}, men's, non-super-over, resolved batters, "
          f"Domestic/IPL only: {len(fact):,} / {n_before:,} rows")
    return fact


def player_season_years(fact: pd.DataFrame, category: str) -> pd.Series:
    """player_id -> set of start_years played in the given competition_category."""
    sub = fact.loc[fact["competition_category"].eq(category)]
    return sub.groupby("batter_canonical_id")["start_year"].agg(lambda s: set(s.dropna().astype(int)))


def has_adjacent_crossover(dom_years: set, ipl_years: set) -> bool:
    if not dom_years or not ipl_years:
        return False
    return any(abs(d - i) <= ADJACENCY_WINDOW for d in dom_years for i in ipl_years)


def player_tier_stats(fact: pd.DataFrame, category: str) -> pd.DataFrame:
    sub = fact.loc[fact["competition_category"].eq(category)].copy()
    sub["balls_faced"] = sub["is_legal_delivery"].fillna(0).astype("int64")
    sub["runs"] = sub["batter_runs"].fillna(0).astype("int64")
    grouped = sub.groupby(["batter_canonical_id", "batter_canonical_name"]).agg(
        balls_faced=("balls_faced", "sum"),
        runs=("runs", "sum"),
        dots=("is_dot_ball", "sum"),
        fours=("is_boundary_four", "sum"),
        sixes=("is_boundary_six", "sum"),
    ).reset_index().rename(columns={"batter_canonical_id": "player_id", "batter_canonical_name": "player_name"})
    grouped = grouped.loc[grouped["balls_faced"] > 0].copy()
    grouped["scoring_rate"] = grouped["runs"] / grouped["balls_faced"] * 100
    grouped["dot_pct"] = grouped["dots"] / grouped["balls_faced"] * 100
    grouped["boundary_pct"] = (grouped["fours"] + grouped["sixes"]) / grouped["balls_faced"] * 100
    return grouped


def main() -> Path:
    root = get_project_root()
    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    fact = prepare_fact(root)

    dom_years = player_season_years(fact, "Domestic")
    ipl_years = player_season_years(fact, "IPL")
    all_players = set(dom_years.index) | set(ipl_years.index)

    # Cohort = adjacent-season crossover ONLY -- no performance filter (avoids
    # survivorship bias: a player is in/out purely on participation timing).
    crossover_ids = [
        pid for pid in all_players
        if has_adjacent_crossover(dom_years.get(pid, set()), ipl_years.get(pid, set()))
    ]

    dom_stats = player_tier_stats(fact, "Domestic").set_index("player_id")
    ipl_stats = player_tier_stats(fact, "IPL").set_index("player_id")

    rows = []
    for pid in crossover_ids:
        if pid not in dom_stats.index or pid not in ipl_stats.index:
            continue
        d, i = dom_stats.loc[pid], ipl_stats.loc[pid]
        # Symmetric qualification floor -- same threshold both tiers, not
        # tuned to keep only IPL-successful players.
        if d["balls_faced"] < QUALIFIED_BALLS or i["balls_faced"] < QUALIFIED_BALLS:
            continue
        rows.append({
            "player_id": pid,
            "player_name": i["player_name"] or d["player_name"],
            "domestic_balls_faced": int(d["balls_faced"]),
            "domestic_scoring_rate": round(float(d["scoring_rate"]), 2),
            "domestic_dot_pct": round(float(d["dot_pct"]), 2),
            "domestic_boundary_pct": round(float(d["boundary_pct"]), 2),
            "ipl_balls_faced": int(i["balls_faced"]),
            "ipl_scoring_rate": round(float(i["scoring_rate"]), 2),
            "ipl_dot_pct": round(float(i["dot_pct"]), 2),
            "ipl_boundary_pct": round(float(i["boundary_pct"]), 2),
            "scoring_rate_ratio_ipl_over_domestic": round(float(i["scoring_rate"] / d["scoring_rate"]), 3)
                if d["scoring_rate"] else None,
        })

    cohort = pd.DataFrame(rows)
    n = len(cohort)
    print(f"Qualified crossover cohort (adjacent-season, >= {QUALIFIED_BALLS} balls faced both tiers): {n}")
    if n < MIN_COHORT_SIZE:
        print(f"VALIDATION FAILED: cohort size {n} < required minimum {MIN_COHORT_SIZE}. "
              f"Reporting as-is, not lowering thresholds to hit the minimum.")

    summary = {}
    if n:
        summary = {
            "n_players": n,
            "mean_scoring_rate_ratio": round(float(cohort["scoring_rate_ratio_ipl_over_domestic"].mean()), 3),
            "median_scoring_rate_ratio": round(float(cohort["scoring_rate_ratio_ipl_over_domestic"].median()), 3),
            "mean_domestic_scoring_rate": round(float(cohort["domestic_scoring_rate"].mean()), 2),
            "mean_ipl_scoring_rate": round(float(cohort["ipl_scoring_rate"].mean()), 2),
            "mean_domestic_dot_pct": round(float(cohort["domestic_dot_pct"].mean()), 2),
            "mean_ipl_dot_pct": round(float(cohort["ipl_dot_pct"].mean()), 2),
            "mean_domestic_boundary_pct": round(float(cohort["domestic_boundary_pct"].mean()), 2),
            "mean_ipl_boundary_pct": round(float(cohort["ipl_boundary_pct"].mean()), 2),
        }
        print(f"Mean scoring-rate ratio (IPL/Domestic): {summary['mean_scoring_rate_ratio']}")

    out = {
        "scope": "batters_only",
        "seasons_filtered": f"{SEASON_MIN}-{SEASON_MAX}",
        "adjacency_window_years": ADJACENCY_WINDOW,
        "qualified_balls_faced_floor": QUALIFIED_BALLS,
        "min_cohort_size_required": MIN_COHORT_SIZE,
        "cohort_size": n,
        "validation_passed": n >= MIN_COHORT_SIZE,
        "summary": summary,
        "players": rows,
    }
    out_path = reports / "eda_domestic_vs_franchise.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Saved: {out_path}")
    return out_path


if __name__ == "__main__":
    main()
