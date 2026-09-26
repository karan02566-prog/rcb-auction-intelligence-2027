"""
Phase 4.10: Domestic-to-Franchise Translation Features

Inputs: data/processed/fact_deliveries.parquet (filtered to SMAT, competition == "sma")
Output: data/features/domestic_translation_features.parquet (grain: player x season x player_type)

Reuses compute_batting_features/compute_bowling_features from Phase 4.1/4.2
(src.features.batting / src.features.bowling) on a SMAT-only fact slice, so
metric formulas and qualified thresholds (QUALIFIED_BALLS_SEASON=150,
QUALIFIED_OVERS_SEASON=20.0) stay identical to the rest of the pipeline --
no new formulas invented here.

"Uncapped" = canonical player_id appears in SMAT (as batter or bowler) but
never appears in IPL (as batter or bowler) anywhere in fact_deliveries.

Domestic performance percentile = per-season percentile rank (0-100) among
QUALIFIED SMAT players that season, for strike_rate & batting_average
(batting) and economy_rate & wicket_rate_per_over (bowling). economy_rate
is lower-is-better, so it's ranked on its negative so a higher percentile
always means "better" across all four metrics.

Domain dominance ratio = player's season metric / season mean among the
same qualified pool that season.

Transition variance flag = True if a player's career (multi-season,
qualified-only) variance of a metric is above the population median
variance for that metric -- i.e. an inconsistent domestic performer,
higher translation risk. NaN (not False) when a player has <2 qualified
seasons -- variance is undefined on one point, that is a missing-data
case per this project's established NaN-vs-0.0 convention, not a
"consistent" case.

Leakage guard (phase.md validation check): main() asserts the SMAT input
slice contains zero 'ipl' competition rows before any feature is computed.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.features.batting import (
    prepare_fact as prepare_batting_fact,
    compute_batting_features,
    QUALIFIED_BALLS_SEASON,
)
from src.features.bowling import (
    compute_bowling_features,
    QUALIFIED_OVERS_SEASON,
)
from src.cleaning.apply_player_mapping import get_mapping_lookups
from src.utils.config import get_project_root

SMAT_COMPETITION = "sma"


def filter_to_smat(fact: pd.DataFrame) -> pd.DataFrame:
    smat = fact.loc[fact["competition"].eq(SMAT_COMPETITION)].copy()
    assert (smat["competition"] == "ipl").sum() == 0, "leakage: ipl rows present in SMAT slice"
    return smat


def compute_uncapped_ids(fact: pd.DataFrame) -> set:
    """Canonical player_ids in SMAT (batter or bowler) never seen in IPL."""
    ipl = fact.loc[fact["competition"].eq("ipl")]
    ipl_players = set(ipl.loc[ipl["batter_canonical_id"].ne("UNRESOLVED"), "batter_canonical_id"]) | \
                  set(ipl.loc[ipl["bowler_canonical_id"].ne("UNRESOLVED"), "bowler_canonical_id"])
    sma = fact.loc[fact["competition"].eq(SMAT_COMPETITION)]
    sma_players = set(sma.loc[sma["batter_canonical_id"].ne("UNRESOLVED"), "batter_canonical_id"]) | \
                  set(sma.loc[sma["bowler_canonical_id"].ne("UNRESOLVED"), "bowler_canonical_id"])
    return sma_players - ipl_players


def add_percentile_and_dominance(df: pd.DataFrame, metric: str, higher_is_better: bool) -> pd.DataFrame:
    df = df.copy()
    pct_col, dom_col = f"{metric}_percentile", f"{metric}_dominance_ratio"
    df[pct_col] = np.nan
    df[dom_col] = np.nan
    for _, group in df.loc[df["qualified"]].groupby("start_year"):
        vals = group[metric]
        rank_vals = vals if higher_is_better else -vals
        df.loc[group.index, pct_col] = rank_vals.rank(pct=True) * 100
        mean_val = vals.mean()
        df.loc[group.index, dom_col] = np.where(mean_val != 0, group[metric] / mean_val, np.nan)
    return df


def transition_variance_flag(df: pd.DataFrame, metric: str) -> pd.Series:
    qualified = df.loc[df["qualified"]]
    variances = qualified.groupby("player_id")[metric].agg(
        lambda s: float(np.var(s, ddof=0)) if len(s) > 1 else np.nan
    )
    valid = variances.dropna()
    median_var = valid.median() if len(valid) else np.nan
    flag_by_player = variances.apply(lambda v: np.nan if pd.isna(v) else (v > median_var))
    return df["player_id"].map(flag_by_player)


def build_batting_translation(fact: pd.DataFrame, exact_lookup, norm_lookup) -> pd.DataFrame:
    feats = compute_batting_features(fact, exact_lookup, norm_lookup)
    feats["qualified"] = feats["balls_faced"] >= QUALIFIED_BALLS_SEASON
    feats = add_percentile_and_dominance(feats, "strike_rate", higher_is_better=True)
    feats = add_percentile_and_dominance(feats, "batting_average", higher_is_better=True)
    feats["sr_transition_variance_flag"] = transition_variance_flag(feats, "strike_rate")
    feats["avg_transition_variance_flag"] = transition_variance_flag(feats, "batting_average")
    return feats


def build_bowling_translation(fact: pd.DataFrame) -> pd.DataFrame:
    feats = compute_bowling_features(fact)
    feats["qualified"] = feats["overs_bowled"] >= QUALIFIED_OVERS_SEASON
    feats = add_percentile_and_dominance(feats, "economy_rate", higher_is_better=False)
    feats = add_percentile_and_dominance(feats, "wicket_rate_per_over", higher_is_better=True)
    feats["economy_transition_variance_flag"] = transition_variance_flag(feats, "economy_rate")
    feats["wicket_rate_transition_variance_flag"] = transition_variance_flag(feats, "wicket_rate_per_over")
    return feats


def main() -> Path:
    root = get_project_root()
    out_dir = root / "data" / "features"
    out_dir.mkdir(parents=True, exist_ok=True)

    fact = prepare_batting_fact(root)  # same season/gender/super-over/resolved filters as 4.1/4.2
    uncapped_ids = compute_uncapped_ids(fact)
    print(f"Uncapped candidate pool (SMAT, never in IPL): {len(uncapped_ids):,} players")

    smat_fact = filter_to_smat(fact)
    assert (smat_fact["competition"] == "ipl").sum() == 0, "leakage: IPL rows in SMAT input"
    print("Leakage check passed: zero IPL rows in SMAT input slice")

    exact_lookup, norm_lookup = get_mapping_lookups()
    if not exact_lookup:
        raise RuntimeError("player_mapping.json lookups are empty; run from the repo root")

    batting = build_batting_translation(smat_fact, exact_lookup, norm_lookup)
    batting["player_type"] = "batter"
    batting["is_uncapped"] = batting["player_id"].isin(uncapped_ids)

    bowling = build_bowling_translation(smat_fact)
    bowling["player_type"] = "bowler"
    bowling["is_uncapped"] = bowling["player_id"].isin(uncapped_ids)

    bat_cols = ["player_id", "player_name", "start_year", "player_type", "is_uncapped", "qualified",
                "strike_rate", "strike_rate_percentile", "strike_rate_dominance_ratio",
                "batting_average", "batting_average_percentile", "batting_average_dominance_ratio",
                "sr_transition_variance_flag", "avg_transition_variance_flag"]
    bowl_cols = ["player_id", "player_name", "start_year", "player_type", "is_uncapped", "qualified",
                 "economy_rate", "economy_rate_percentile", "economy_rate_dominance_ratio",
                 "wicket_rate_per_over", "wicket_rate_per_over_percentile", "wicket_rate_per_over_dominance_ratio",
                 "economy_transition_variance_flag", "wicket_rate_transition_variance_flag"]

    features = pd.concat([batting[bat_cols], bowling[bowl_cols]], ignore_index=True)
    features = features.sort_values(["player_type", "player_name", "start_year"]).reset_index(drop=True)

    out_path = out_dir / "domestic_translation_features.parquet"
    features.to_parquet(out_path, index=False)
    print(f"Saved: {out_path} ({len(features):,} rows: {len(batting):,} batting + {len(bowling):,} bowling)")
    return out_path


if __name__ == "__main__":
    main()
