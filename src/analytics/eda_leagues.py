"""
Phase 3.1: League Scoring Environments & Baseline Comparison.

Scope status (v1.1): SCOPED DOWN -- quick sanity-check macro numbers per
competition, not a full comparative study (no truncation/DLS adjustment for
rain-affected matches -- see Common Failure Modes in phase.md; excluded
super overs instead since they're a different format, not a truncation).

Inputs: data/processed/fact_deliveries.parquet, data/processed/dim_competitions.parquet
Output: reports/eda_league_baselines.json
"""
import json
from pathlib import Path

import pandas as pd


def main():
    processed_dir = Path("data/processed")
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    fact = pd.read_parquet(processed_dir / "fact_deliveries.parquet")
    dim_comp = pd.read_parquet(processed_dir / "dim_competitions.parquet")

    # fact_deliveries carries competition_id (from Phase 2.7's join) but not
    # start_year -- pull that in from dim_competitions rather than re-running
    # the whole processed-layer join.
    fact = fact.merge(
        dim_comp[["competition_id", "start_year"]],
        on="competition_id",
        how="left",
    )

    n_before = len(fact)
    fact = fact[(fact["start_year"] >= 2018) & (fact["start_year"] <= 2026)]
    fact = fact[fact["is_super_over"] == False]  # different format, not a truncation case
    print(f"Filtered to seasons 2018-2026, non-super-over: {len(fact):,} / {n_before:,} rows")

    grouped = fact.groupby(["competition", "competition_category"]).agg(
        legal_balls=("is_legal_delivery", "sum"),
        total_runs=("total_runs", "sum"),
        fours=("is_boundary_four", "sum"),
        sixes=("is_boundary_six", "sum"),
        dot_balls=("is_dot_ball", "sum"),
        wickets=("is_wicket", "sum"),
        matches=("match_id", "nunique"),
        seasons=("start_year", "nunique"),
        season_min=("start_year", "min"),
        season_max=("start_year", "max"),
    ).reset_index()

    grouped["overs"] = (grouped["legal_balls"] / 6).round(2)
    grouped["run_rate"] = (grouped["total_runs"] / (grouped["legal_balls"] / 6)).round(3)
    grouped["boundary_pct"] = ((grouped["fours"] + grouped["sixes"]) / grouped["legal_balls"] * 100).round(2)
    grouped["dot_pct"] = (grouped["dot_balls"] / grouped["legal_balls"] * 100).round(2)
    grouped["wicket_rate_per_100_balls"] = (grouped["wickets"] / grouped["legal_balls"] * 100).round(3)
    grouped["balls_per_wicket"] = (grouped["legal_balls"] / grouped["wickets"]).round(2)

    grouped = grouped.sort_values("run_rate", ascending=False)

    output_cols = ["competition", "competition_category", "matches", "seasons",
                    "season_min", "season_max", "overs", "run_rate", "boundary_pct",
                    "dot_pct", "wicket_rate_per_100_balls", "balls_per_wicket"]
    records = grouped[output_cols].to_dict(orient="records")

    ipl_row = grouped[grouped["competition"] == "ipl"]
    ipl_run_rate = float(ipl_row["run_rate"].iloc[0]) if len(ipl_row) else None
    # Sanity band from published IPL season summaries: full-innings run rate
    # has historically sat ~7.5-8.5, with powerplay/death overs pulling higher
    # in recent seasons (ESPNcricinfo, Hindustan Times season reports).
    validation_note = None
    if ipl_run_rate is not None:
        in_band = 7.0 <= ipl_run_rate <= 9.5
        validation_note = (
            f"Computed IPL run rate {ipl_run_rate} is "
            f"{'within' if in_band else 'OUTSIDE'} the ~7.0-9.5 sanity band "
            f"from published IPL season summaries."
        )
        print(validation_note)

    report = {
        "seasons_filtered": "2018-2026",
        "rows_after_filter": int(len(fact)),
        "competitions": records,
        "ipl_validation": validation_note,
    }

    out_path = reports_dir / "eda_league_baselines.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"\n{'Competition':<25}{'Category':<20}{'RunRate':>8}{'Bdry%':>8}{'WktRate':>9}")
    for r in records:
        print(f"{r['competition']:<25}{r['competition_category']:<20}{r['run_rate']:>8}{r['boundary_pct']:>8}{r['wicket_rate_per_100_balls']:>9}")

    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
