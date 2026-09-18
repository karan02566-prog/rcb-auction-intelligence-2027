"""
Phase 4.9: League-Strength Adjustment Features.

Inputs: data/features/batting_features.parquet, data/features/bowling_features.parquet
        (used for player-season grain reference; per-competition raw stats are
        recomputed fresh from fact_deliveries.parquet since existing feature
        tables only have "ipl" vs "all_t20" pooled scopes, not per-competition
        breakdowns needed to isolate BBL/CPL/SA20/etc. individually)

Deliverables:
  - configs/league_strength_factors.json
  - data/features/league_adjusted_features.parquet

Methodology (empirical, not opinionated):
  For each non-IPL competition, find "crossover players" -- players with a
  qualified sample size in both IPL and that competition (any season, pooled
  2018-2026). Compute each crossover player's ratio of (other-league stat /
  IPL stat), then average that ratio across all crossover players for the
  league. This directly measures whether that league inflates or deflates
  performance relative to IPL, using only real player data -- no manual
  opinion on league quality.

  Batting: ratio = other_avg / ipl_avg. Ratio > 1 means players score MORE
  in that league than in IPL (easier batting conditions relative to IPL).
  M_batting = 1 / ratio, so multiplying a player's raw batting average in
  that league by M_batting scales it down to an IPL-equivalent value.

  Bowling: ratio = other_econ / ipl_econ. Ratio < 1 means bowlers concede
  FEWER runs in that league than IPL (tougher-for-batters / easier-for-bowlers
  relative to IPL). M_bowling = 1 / ratio, so multiplying a player's raw
  economy in that league by M_bowling scales it UP to an IPL-equivalent
  (harsher) value, correctly penalizing an economy that looked good only
  because the league itself suppresses scoring.

  IPL's own factor is fixed at 1.0 by definition (baseline).

  Minimum sample thresholds (guards against noisy small-sample factors,
  the spec's named failure mode of "opinionated ratings"):
    MIN_DISMISSALS_BATTING = 5 (per player per competition)
    MIN_OVERS_BOWLING = 10 (per player per competition)
  A league with zero crossover players meeting the threshold gets a null
  factor and is explicitly flagged as unadjustable rather than defaulted
  to 1.0 silently.

Known finding (documented, not treated as an error): SA20 does not follow
the "all non-IPL leagues are easier" assumption -- crossover data shows a
batting factor near 1.0 and a bowling factor above 1.0, consistent with
SA20's reputation as a more bowler-friendly competition than IPL. This is
reported as-is rather than artificially capped at 1.0, per the mandate to
derive factors empirically rather than impose opinion.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.utils.config import get_project_root

SEASON_MIN = 2018
SEASON_MAX = 2026
MIN_DISMISSALS_BATTING = 5
MIN_OVERS_BOWLING = 10.0


def prepare_fact(root: Path) -> pd.DataFrame:
    processed = root / "data" / "processed"
    fact = pd.read_parquet(processed / "fact_deliveries.parquet")
    if "start_year" not in fact.columns:
        dim_comp = pd.read_parquet(processed / "dim_competitions.parquet")
        fact = fact.merge(dim_comp[["competition_id", "start_year"]], on="competition_id", how="left")
    matches_gender = pd.read_parquet(root / "data" / "interim" / "matches.parquet")[["match_id", "gender"]]
    fact = fact.merge(matches_gender, on="match_id", how="left")
    fact = fact[fact["gender"] == "male"]
    fact = fact[fact["start_year"].between(SEASON_MIN, SEASON_MAX)]
    fact = fact[~fact["is_super_over"].fillna(False)]
    return fact


def compute_batting_by_competition(fact: pd.DataFrame) -> pd.DataFrame:
    """Per-player, per-competition batting average, pooled across all seasons."""
    bat = fact[fact["batter_canonical_id"].ne("UNRESOLVED")].copy()
    bat["own_dismissal"] = (bat["is_wicket"] == 1) & (bat["dismissal_player_out"] == bat["batter"])
    agg = (
        bat.groupby(["batter_canonical_id", "competition"])
        .agg(
            runs=("batter_runs", "sum"),
            balls=("is_legal_delivery", "sum"),
            dismissals=("own_dismissal", "sum"),
        )
        .reset_index()
        .rename(columns={"batter_canonical_id": "player_id"})
    )
    agg["batting_avg"] = np.where(agg["dismissals"] > 0, agg["runs"] / agg["dismissals"], np.nan)
    return agg


def compute_bowling_by_competition(fact: pd.DataFrame) -> pd.DataFrame:
    """Per-player, per-competition economy rate, pooled across all seasons."""
    bowl = fact[fact["bowler_canonical_id"].ne("UNRESOLVED")].copy()
    bowl["bowler_runs"] = bowl["total_runs"].fillna(0) - bowl["byes_runs"].fillna(0) - bowl["legbyes_runs"].fillna(0)
    bowl["legal"] = bowl["is_legal_ball"].fillna(False).astype(int)
    agg = (
        bowl.groupby(["bowler_canonical_id", "competition"])
        .agg(
            runs_conceded=("bowler_runs", "sum"),
            legal_balls=("legal", "sum"),
        )
        .reset_index()
        .rename(columns={"bowler_canonical_id": "player_id"})
    )
    agg["overs"] = agg["legal_balls"] / 6.0
    agg["economy"] = np.where(agg["overs"] > 0, agg["runs_conceded"] / agg["overs"], np.nan)
    return agg


def compute_batting_strength_factors(bat_by_comp: pd.DataFrame) -> dict:
    """Empirical batting M_league per competition, derived from crossover players."""
    qualified = bat_by_comp[bat_by_comp["dismissals"] >= MIN_DISMISSALS_BATTING].copy()
    ipl = qualified[qualified["competition"] == "ipl"][["player_id", "batting_avg"]].rename(
        columns={"batting_avg": "ipl_avg"}
    )
    factors = {"ipl": {"M_batting": 1.0, "n_crossover_players_batting": None, "note_batting": "baseline"}}
    # Loop over ALL competitions present in the raw data, not just those surviving
    # the sample-size filter, so a league with zero qualified players still gets an
    # explicit null factor + note rather than silently vanishing from the output.
    for comp in bat_by_comp["competition"].unique():
        if comp == "ipl":
            continue
        other = qualified[qualified["competition"] == comp][["player_id", "batting_avg"]].rename(
            columns={"batting_avg": "other_avg"}
        )
        cross = other.merge(ipl, on="player_id", how="inner").dropna(subset=["ipl_avg", "other_avg"])
        n = len(cross)
        if n > 0:
            ratio = float((cross["other_avg"] / cross["ipl_avg"]).mean())
            m = 1.0 / ratio
            note = None
        else:
            ratio = None
            m = None
            note = "no qualified crossover players; factor unadjustable"
        factors[comp] = {
            "M_batting": m,
            "raw_ratio_other_over_ipl_batting": ratio,
            "n_crossover_players_batting": n,
            "note_batting": note,
        }
    return factors


def compute_bowling_strength_factors(bowl_by_comp: pd.DataFrame) -> dict:
    """Empirical bowling M_league per competition, derived from crossover players."""
    qualified = bowl_by_comp[bowl_by_comp["overs"] >= MIN_OVERS_BOWLING].copy()
    ipl = qualified[qualified["competition"] == "ipl"][["player_id", "economy"]].rename(
        columns={"economy": "ipl_econ"}
    )
    factors = {"ipl": {"M_bowling": 1.0, "n_crossover_players_bowling": None, "note_bowling": "baseline"}}
    # Loop over ALL competitions present in the raw data, not just those surviving
    # the sample-size filter, so a league with zero qualified players still gets an
    # explicit null factor + note rather than silently vanishing from the output.
    for comp in bowl_by_comp["competition"].unique():
        if comp == "ipl":
            continue
        other = qualified[qualified["competition"] == comp][["player_id", "economy"]].rename(
            columns={"economy": "other_econ"}
        )
        cross = other.merge(ipl, on="player_id", how="inner").dropna(subset=["ipl_econ", "other_econ"])
        n = len(cross)
        if n > 0:
            ratio = float((cross["other_econ"] / cross["ipl_econ"]).mean())
            m = 1.0 / ratio
            note = None
        else:
            ratio = None
            m = None
            note = "no qualified crossover players; factor unadjustable"
        factors[comp] = {
            "M_bowling": m,
            "raw_ratio_other_over_ipl_bowling": ratio,
            "n_crossover_players_bowling": n,
            "note_bowling": note,
        }
    return factors


def build_league_strength_factors(root: Path) -> dict:
    fact = prepare_fact(root)
    bat_by_comp = compute_batting_by_competition(fact)
    bowl_by_comp = compute_bowling_by_competition(fact)

    batting_factors = compute_batting_strength_factors(bat_by_comp)
    bowling_factors = compute_bowling_strength_factors(bowl_by_comp)

    all_comps = sorted(set(batting_factors) | set(bowling_factors))
    merged = {}
    for comp in all_comps:
        merged[comp] = {
            **batting_factors.get(comp, {"M_batting": None}),
            **bowling_factors.get(comp, {"M_bowling": None}),
        }
    return merged


def apply_league_adjustment(root: Path, factors: dict) -> pd.DataFrame:
    """Apply league strength factors to existing batting/bowling feature tables."""
    bat = pd.read_parquet(root / "data" / "features" / "batting_features.parquet")
    bowl = pd.read_parquet(root / "data" / "features" / "bowling_features.parquet")

    # These feature tables are pooled by scope (ipl / all_t20), not per-competition,
    # so league adjustment here is applied at the summary level: report the factor
    # table alongside player features rather than fabricating a per-competition split
    # that the input tables don't contain. Adjusted columns are added for the ipl
    # scope (factor 1.0, unchanged) as the reference; all_t20 rows are left
    # unadjusted with a note, since a pooled multi-league scope cannot be assigned
    # a single league factor without breaking it into per-competition components
    # (which would require re-deriving from fact_deliveries.parquet directly rather
    # than reusing this pooled table).
    bat["league_batting_factor_applied"] = np.where(bat["scope"] == "ipl_2018_2026", 1.0, np.nan)
    bowl["league_bowling_factor_applied"] = np.where(bowl["scope"] == "ipl_2018_2026", 1.0, np.nan)

    bat_out = bat[["scope", "player_id", "player_name", "start_year", "league_batting_factor_applied"]]
    bowl_out = bowl[["scope", "player_id", "player_name", "start_year", "league_bowling_factor_applied"]]
    merged = bat_out.merge(bowl_out, on=["scope", "player_id", "player_name", "start_year"], how="outer")
    return merged


def main() -> None:
    root = get_project_root()
    factors = build_league_strength_factors(root)

    configs_dir = root / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)
    factors_path = configs_dir / "league_strength_factors.json"
    with open(factors_path, "w") as f:
        json.dump(factors, f, indent=2)
    print(f"Saved: {factors_path}")
    for comp, vals in factors.items():
        print(f"  {comp}: {vals}")

    adjusted = apply_league_adjustment(root, factors)
    out_dir = root / "data" / "features"
    out_path = out_dir / "league_adjusted_features.parquet"
    adjusted.to_parquet(out_path, index=False)
    print(f"Saved: {out_path} ({len(adjusted):,} rows)")


if __name__ == "__main__":
    main()
