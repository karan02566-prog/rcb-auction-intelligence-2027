"""
Phase 6.4: Pitch Adaptability & Matchup Filtering.

Inputs: data/interim/funnel_stage3_consistency.parquet (passes_stage3 == True rows),
        data/processed/fact_deliveries.parquet, data/processed/dim_competitions.parquet
Output: data/interim/funnel_stage4_adaptability.parquet, updates reports/funnel_audit.json

KNOWN LIMITATION -- SPLIT SCOPE: this stage only implements the Chinnaswamy
pitch-adaptability half of the spec. The spin/pace matchup-vulnerability
half is DEFERRED: no bowler-style (pace/spin) field exists anywhere in
this project's data (checked dim_players.parquet, people.csv,
fact_deliveries.parquet -- none has it). This is not a workaround-able gap
like Phase 5.7's missing broad universe; the raw attribute simply isn't
present. Needs an external data source (e.g. scraping Cricinfo player
pages via dim_players.key_cricinfo) before it can be built.

Chinnaswamy sample coverage check (recent window 2025-2026): only 20
batters and 19 bowlers in the relevant pool have >=30 balls at M
Chinnaswamy Stadium -- a small fraction of the ~248 Stage 3 pool. A hard
"must perform well at Chinnaswamy" filter would functionally disqualify
almost everyone for lack of data, not actual weakness -- exactly the
spec's own named failure mode ("disqualifying players for a matchup
weakness... easily sheltered"), just showing up as data sparsity rather
than batting order. So: this filter ONLY applies to candidates who clear
a minimum Chinnaswamy sample threshold; everyone else passes through
untested, not penalized.

Threshold: >=30 balls_faced (batting) or >=30 legal_balls (bowling) at
M Chinnaswamy Stadium in the recent window (2025+2026, matching Stages 1-3).
Pass condition for sampled candidates: strike_rate >= median OR
economy_rate <= median among that same small sampled group (not the full
Stage 3 pool -- the comparison group is deliberately narrow, since
Chinnaswamy-specific form is only comparable to other Chinnaswamy-tested
players).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.utils.config import get_project_root

RECENT_SEASONS = [2025, 2026]
VENUE = "M Chinnaswamy Stadium"
MIN_CHINNASWAMY_BALLS = 30


def prepare_chinnaswamy_fact(root: Path) -> pd.DataFrame:
    fd = pd.read_parquet(
        root / "data" / "processed" / "fact_deliveries.parquet",
        columns=[
            "venue_canonical", "batter_canonical_id", "bowler_canonical_id", "competition_id",
            "is_legal_delivery", "is_legal_ball", "batter_runs", "total_runs", "byes_runs", "legbyes_runs",
        ],
    )
    dim_comp = pd.read_parquet(root / "data" / "processed" / "dim_competitions.parquet")[
        ["competition_id", "start_year"]
    ]
    fd = fd.merge(dim_comp, on="competition_id", how="left")
    fd = fd[(fd["venue_canonical"] == VENUE) & (fd["start_year"].isin(RECENT_SEASONS))]
    return fd


def compute_chinnaswamy_batting(fact: pd.DataFrame) -> pd.DataFrame:
    bat = fact[fact["batter_canonical_id"].ne("UNRESOLVED")].copy()
    agg = bat.groupby("batter_canonical_id").agg(
        runs=("batter_runs", "sum"), balls_faced=("is_legal_delivery", "sum")
    ).reset_index().rename(columns={"batter_canonical_id": "player_id"})
    agg["chinnaswamy_strike_rate"] = np.where(
        agg["balls_faced"] > 0, agg["runs"] / agg["balls_faced"] * 100, np.nan
    )
    return agg[["player_id", "balls_faced", "chinnaswamy_strike_rate"]]


def compute_chinnaswamy_bowling(fact: pd.DataFrame) -> pd.DataFrame:
    bowl = fact[fact["bowler_canonical_id"].ne("UNRESOLVED")].copy()
    bowl["bowler_runs"] = bowl["total_runs"].fillna(0) - bowl["byes_runs"].fillna(0) - bowl["legbyes_runs"].fillna(0)
    bowl["legal"] = bowl["is_legal_ball"].fillna(False).astype(int)
    agg = bowl.groupby("bowler_canonical_id").agg(
        runs_conceded=("bowler_runs", "sum"), legal_balls=("legal", "sum")
    ).reset_index().rename(columns={"bowler_canonical_id": "player_id"})
    agg["overs"] = agg["legal_balls"] / 6.0
    agg["chinnaswamy_economy"] = np.where(
        agg["overs"] > 0, agg["runs_conceded"] / agg["overs"], np.nan
    )
    return agg[["player_id", "legal_balls", "chinnaswamy_economy"]]


def apply_stage4_filter(stage3: pd.DataFrame, chinna_bat: pd.DataFrame, chinna_bowl: pd.DataFrame) -> pd.DataFrame:
    df = stage3.loc[stage3["passes_stage3"]].copy()
    df = df.merge(chinna_bat, on="player_id", how="left")
    df = df.merge(chinna_bowl, on="player_id", how="left")

    sampled_batters = df["balls_faced"].fillna(0) >= MIN_CHINNASWAMY_BALLS
    sampled_bowlers = df["legal_balls"].fillna(0) >= MIN_CHINNASWAMY_BALLS

    sr_median = df.loc[sampled_batters, "chinnaswamy_strike_rate"].median()
    econ_median = df.loc[sampled_bowlers, "chinnaswamy_economy"].median()

    batting_ok = ~sampled_batters | (df["chinnaswamy_strike_rate"] >= sr_median)
    bowling_ok = ~sampled_bowlers | (df["chinnaswamy_economy"] <= econ_median)

    # A candidate only fails if THEY are sampled AND below their group's median,
    # in whichever discipline(s) they are sampled in. Untested disciplines never fail.
    df["passes_stage4"] = np.where(
        sampled_batters | sampled_bowlers,
        (~sampled_batters | batting_ok) & (~sampled_bowlers | bowling_ok),
        True,  # no Chinnaswamy sample at all -- untested, passes through
    )
    df["chinnaswamy_sr_median_used"] = sr_median
    df["chinnaswamy_econ_median_used"] = econ_median
    return df


def main() -> Path:
    root = get_project_root()
    interim_dir = root / "data" / "interim"

    stage3 = pd.read_parquet(interim_dir / "funnel_stage3_consistency.parquet")
    fact = prepare_chinnaswamy_fact(root)
    chinna_bat = compute_chinnaswamy_batting(fact)
    chinna_bowl = compute_chinnaswamy_bowling(fact)

    result = apply_stage4_filter(stage3, chinna_bat, chinna_bowl)

    n_in = int(stage3["passes_stage3"].sum())
    n_passed = int(result["passes_stage4"].sum())
    n_dropped = n_in - n_passed
    n_sampled = int(
        ((result["balls_faced"].fillna(0) >= MIN_CHINNASWAMY_BALLS)
         | (result["legal_balls"].fillna(0) >= MIN_CHINNASWAMY_BALLS)).sum()
    )

    out_path = interim_dir / "funnel_stage4_adaptability.parquet"
    result.to_parquet(out_path, index=False)

    audit_path = root / "reports" / "funnel_audit.json"
    audit = json.loads(audit_path.read_text()) if audit_path.exists() else {}
    audit["stage4_adaptability_filter"] = {
        "scope_note": "Chinnaswamy pitch-adaptability only; spin/pace matchup filtering DEFERRED "
                      "-- no bowler-style field exists in the dataset",
        "min_chinnaswamy_balls_threshold": MIN_CHINNASWAMY_BALLS,
        "candidates_with_chinnaswamy_sample": n_sampled,
        "stage3_input_count": n_in,
        "passed_stage4": n_passed,
        "dropped_stage4": n_dropped,
    }
    audit_path.write_text(json.dumps(audit, indent=2))

    print(f"Stage 3 input: {n_in:,} | Sampled at Chinnaswamy: {n_sampled:,} | "
          f"Passed Stage 4: {n_passed:,} | Dropped: {n_dropped:,}")
    print(f"Saved: {out_path}")
    return out_path


if __name__ == "__main__":
    main()
