"""
Phase 6.3: Consistency & Floor/Ceiling Filtering.

Inputs: data/interim/funnel_stage2_performance.parquet (passes_stage2 == True rows),
        data/features/consistency_features.parquet
Output: data/interim/funnel_stage3_consistency.parquet, updates reports/funnel_audit.json

Reuses the pre-built consistency_badge column directly (Elite / High Floor /
Boom-or-Bust / Moderate / Unqualified) from Phase 4.3 -- no new consistency
metric invented here. Per that module's own docstring, the badge is
batting-specific ("Unit of observation for score: batting innings"), so
this filter only applies to candidates eligible on batting (meets_batting_threshold
from Stage 1, carried through Stage 2); bowling-only candidates pass through
unaffected.

Common failure mode guarded (per phase.md, spec's own wording): "uniformly
penalizing high-ceiling death finishers for natural high variance." The
Boom-or-Bust badge (high failure_rate AND high high_impact_rate) is exactly
that profile and is explicitly NOT filtered out here -- only Moderate
(high failure, low impact: no floor, no ceiling) fails.

Recent-season badge lookup: prefers the 2026 season badge if the player was
`qualified` (>=10 batting innings, Phase 4.3's own threshold) that season;
falls back to 2025; if qualified in neither, badge is "Unqualified" and the
candidate passes through (a data-sufficiency gap in the recent window, not
evidence of inconsistency).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.utils.config import get_project_root

RECENT_SEASONS_PRIORITY = [2026, 2025]  # prefer most recent qualified season
SCOPE = "all_t20_2018_2026"
PASSING_BADGES = {"Elite", "High Floor", "Boom-or-Bust"}


def get_recent_badge(consistency: pd.DataFrame) -> pd.DataFrame:
    """Per player, pick the badge from the most recent qualified season in the window."""
    df = consistency.loc[
        (consistency["scope"] == SCOPE) & (consistency["start_year"].isin(RECENT_SEASONS_PRIORITY))
    ].copy()
    qualified_df = df.loc[df["qualified"]]

    df["season_priority"] = df["start_year"].map({y: i for i, y in enumerate(RECENT_SEASONS_PRIORITY)})
    qualified_df = qualified_df.copy()
    qualified_df["season_priority"] = qualified_df["start_year"].map(
        {y: i for i, y in enumerate(RECENT_SEASONS_PRIORITY)}
    )
    best = (
        qualified_df.sort_values(["player_id", "season_priority"])
        .groupby("player_id", as_index=False)
        .first()[["player_id", "consistency_badge"]]
    )
    return best.rename(columns={"consistency_badge": "recent_consistency_badge"})


def apply_stage3_filter(stage2: pd.DataFrame, recent_badge: pd.DataFrame) -> pd.DataFrame:
    df = stage2.loc[stage2["passes_stage2"]].copy()
    df = df.merge(recent_badge, on="player_id", how="left")
    df["recent_consistency_badge"] = df["recent_consistency_badge"].fillna("Unqualified")

    batting_eligible = df["meets_batting_threshold"]
    badge_ok = df["recent_consistency_badge"].isin(PASSING_BADGES) | (
        df["recent_consistency_badge"] == "Unqualified"
    )

    df["passes_stage3"] = ~batting_eligible | badge_ok
    return df


def main() -> Path:
    root = get_project_root()
    interim_dir = root / "data" / "interim"

    stage2 = pd.read_parquet(interim_dir / "funnel_stage2_performance.parquet")
    consistency = pd.read_parquet(root / "data" / "features" / "consistency_features.parquet")

    recent_badge = get_recent_badge(consistency)
    result = apply_stage3_filter(stage2, recent_badge)

    n_in = int(stage2["passes_stage2"].sum())
    n_passed = int(result["passes_stage3"].sum())
    n_dropped = n_in - n_passed

    out_path = interim_dir / "funnel_stage3_consistency.parquet"
    result.to_parquet(out_path, index=False)

    audit_path = root / "reports" / "funnel_audit.json"
    audit = json.loads(audit_path.read_text()) if audit_path.exists() else {}
    audit["stage3_consistency_filter"] = {
        "note": "Boom-or-Bust badge explicitly NOT filtered (high-ceiling death-finisher profile); "
                "only Moderate badge fails; bowling-only candidates pass through unaffected "
                "(badge is batting-specific)",
        "stage2_input_count": n_in,
        "passed_stage3": n_passed,
        "dropped_stage3": n_dropped,
        "dropped_badge_breakdown": result.loc[~result["passes_stage3"], "recent_consistency_badge"]
            .value_counts().to_dict(),
    }
    audit_path.write_text(json.dumps(audit, indent=2))

    print(f"Stage 2 input: {n_in:,} | Passed Stage 3: {n_passed:,} | Dropped: {n_dropped:,}")
    print(f"Saved: {out_path}")
    return out_path


if __name__ == "__main__":
    main()
