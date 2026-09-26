"""
Phase 6.1: Universe Definition & Minimum Sample Filtering.

KNOWN LIMITATION (Phase 5 deferred): the spec's input,
data/processed/candidate_universe_broad.parquet, does not exist yet --
it depends on Phase 5.7, which is blocked on RCB's retained squad list
and target role profiles (Phase 5 not started). In its place, this
script builds a minimal standalone universe = every player_id appearing
in batting_features.parquet or bowling_features.parquet (all_t20 scope).
This means: no retained-player exclusion, and no target-role-profile
matching yet. Both must be re-applied once Phase 5 unblocks -- this
Stage 1 output should be treated as provisional, not final.

Inputs: data/features/batting_features.parquet, data/features/bowling_features.parquet
Output: data/interim/funnel_stage1_sample.parquet, reports/funnel_audit.json

Recent window = last 2 seasons (2025, 2026) pooled, using the
all_t20_2018_2026 scope (not ipl_2018_2026) -- per this phase's own
stated safeguard against dropping domestic-only prospects who have zero
IPL appearances. 2026 alone was checked and found to be a partial season
(397 batting rows vs ~600-770 for 2022-2025), too thin to use standalone.

Sample thresholds (per spec): minimum 100 batting balls_faced OR minimum
60 bowling legal_balls, summed across the pooled 2-season window. A
player qualifies if they clear EITHER threshold (batting or bowling) --
not both -- since pure specialists (e.g. a bowler with negligible batting
balls) must not be excluded for failing the other discipline's cutoff.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.utils.config import get_project_root

RECENT_SEASONS = [2025, 2026]
SCOPE = "all_t20_2018_2026"
MIN_BATTING_BALLS = 100
MIN_BOWLING_BALLS = 60


def load_recent_pooled(root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    bat = pd.read_parquet(root / "data" / "features" / "batting_features.parquet")
    bowl = pd.read_parquet(root / "data" / "features" / "bowling_features.parquet")

    bat_recent = bat.loc[(bat["scope"] == SCOPE) & (bat["start_year"].isin(RECENT_SEASONS))]
    bowl_recent = bowl.loc[(bowl["scope"] == SCOPE) & (bowl["start_year"].isin(RECENT_SEASONS))]

    bat_pooled = bat_recent.groupby(["player_id", "player_name"], as_index=False)["balls_faced"].sum()
    bowl_pooled = bowl_recent.groupby(["player_id", "player_name"], as_index=False)["legal_balls"].sum()

    return bat_pooled, bowl_pooled


def build_universe(bat_pooled: pd.DataFrame, bowl_pooled: pd.DataFrame) -> pd.DataFrame:
    universe = pd.merge(
        bat_pooled.rename(columns={"balls_faced": "batting_balls_faced_recent"}),
        bowl_pooled.rename(columns={"legal_balls": "bowling_legal_balls_recent"}),
        on=["player_id", "player_name"],
        how="outer",
    )
    universe["batting_balls_faced_recent"] = universe["batting_balls_faced_recent"].fillna(0).astype("int64")
    universe["bowling_legal_balls_recent"] = universe["bowling_legal_balls_recent"].fillna(0).astype("int64")
    return universe


def apply_stage1_filter(universe: pd.DataFrame) -> pd.DataFrame:
    df = universe.copy()
    df["meets_batting_threshold"] = df["batting_balls_faced_recent"] >= MIN_BATTING_BALLS
    df["meets_bowling_threshold"] = df["bowling_legal_balls_recent"] >= MIN_BOWLING_BALLS
    df["passes_stage1"] = df["meets_batting_threshold"] | df["meets_bowling_threshold"]
    return df


def main() -> Path:
    root = get_project_root()
    interim_dir = root / "data" / "interim"
    reports_dir = root / "reports"
    interim_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    bat_pooled, bowl_pooled = load_recent_pooled(root)
    universe = build_universe(bat_pooled, bowl_pooled)
    result = apply_stage1_filter(universe)

    n_total = len(result)
    n_passed = int(result["passes_stage1"].sum())
    n_dropped = n_total - n_passed

    out_path = interim_dir / "funnel_stage1_sample.parquet"
    result.to_parquet(out_path, index=False)

    audit = {
        "stage1_sample_filter": {
            "provisional_universe_note": "no candidate_universe_broad.parquet input (Phase 5 deferred); "
                                          "universe built from batting/bowling feature tables directly, "
                                          "no retained-player exclusion or role-profile matching applied yet",
            "recent_seasons_used": RECENT_SEASONS,
            "scope": SCOPE,
            "min_batting_balls": MIN_BATTING_BALLS,
            "min_bowling_balls": MIN_BOWLING_BALLS,
            "total_universe": n_total,
            "passed_stage1": n_passed,
            "dropped_stage1": n_dropped,
        }
    }
    audit_path = reports_dir / "funnel_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2))

    print(f"Universe: {n_total:,} players | Passed Stage 1: {n_passed:,} | Dropped: {n_dropped:,}")
    print(f"Saved: {out_path}")
    print(f"Saved: {audit_path}")
    return out_path


if __name__ == "__main__":
    main()
