"""
Phase 3.4: Bowler Distributions & Spell Profile Analysis.

Inputs: data/processed/fact_deliveries.parquet, data/processed/dim_players.parquet
Output: reports/eda_bowling_distributions.parquet (one row per bowler)

Grain note: uses `is_legal_ball` (excludes wides AND no-balls -- the true
6-ball-over count), not `is_legal_delivery` (excludes only wides, used
elsewhere for batter balls-faced). Using the wrong flag here would silently
misstate every economy rate.

Runs conceded excludes byes/leg-byes (not the bowler's fault) but includes
wides/no-balls (are the bowler's fault), matching scorecard convention.

Common failure mode this avoids (per phase.md): aggregating partial overs
incorrectly during mid-over injuries/suspensions. Overs are aggregated at
(bowler, match, innings, over_number) grain using each delivery's own bowler
column -- so if a bowler leaves mid-over and another completes it, each
bowler is only charged for the balls they actually bowled, not the whole over.

Spell = a maximal run of consecutive overs (over_number increasing by 1) bowled
by the same bowler in the same innings, uninterrupted by another bowler.
"""
from pathlib import Path

import numpy as np
import pandas as pd

MIN_SPELLS_FOR_STATS = 10
EXPENSIVE_OVER_RUNS = 12  # runs conceded threshold, T20 convention (2+ boundaries)
BOWLER_CREDITED_KINDS = frozenset({
    "bowled", "caught", "caught and bowled", "lbw", "stumped", "hit wicket",
})


def is_bowler_credited(dismissal_type: str) -> bool:
    if not isinstance(dismissal_type, str) or not dismissal_type:
        return False
    kinds = [k.strip().lower() for k in dismissal_type.split("|") if k.strip()]
    return any(k in BOWLER_CREDITED_KINDS for k in kinds)


def main():
    processed_dir = Path("data/processed")
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    fact = pd.read_parquet(processed_dir / "fact_deliveries.parquet")
    dim_comp = pd.read_parquet(processed_dir / "dim_competitions.parquet")
    matches_gender = pd.read_parquet(Path("data/interim/matches.parquet"))[["match_id", "gender"]]

    if "start_year" not in fact.columns:
        fact = fact.merge(dim_comp[["competition_id", "start_year"]], on="competition_id", how="left")
    fact = fact.merge(matches_gender, on="match_id", how="left")

    n_before = len(fact)
    fact = fact[(fact["start_year"] >= 2018) & (fact["start_year"] <= 2026)]
    fact = fact[fact["is_super_over"] == False]
    fact = fact[fact["bowler_canonical_id"] != "UNRESOLVED"]
    fact = fact[fact["gender"] == "male"]  # matches.gender is a real source field, not inferred
    print(f"Filtered to 2018-2026, non-super-over, resolved bowlers, men's matches: {len(fact):,} / {n_before:,} rows")

    fact = fact.copy()
    fact["bowler_runs"] = fact["total_runs"] - fact["byes_runs"] - fact["legbyes_runs"]
    fact["bowler_wicket"] = fact["is_wicket"] & fact["dismissal_type"].apply(is_bowler_credited)

    # --- Over-level aggregation (grain: bowler, match, innings, over -- handles
    # mid-over bowler changes correctly since it's grouped by the actual bowler
    # column on each delivery, not assumed constant across the over) ---
    over_agg = fact.groupby(
        ["bowler_canonical_id", "bowler_canonical_name", "match_id", "innings_number", "over_number"]
    ).agg(
        legal_balls=("is_legal_ball", "sum"),
        runs=("bowler_runs", "sum"),
        wickets=("bowler_wicket", "sum"),
        dots=("is_dot_ball", "sum"),
        competition=("competition", "first"),
    ).reset_index()

    # --- Spell detection: consecutive over_numbers by the same bowler in the
    # same innings, broken by any gap (another bowler took an over) ---
    over_agg = over_agg.sort_values(
        ["bowler_canonical_id", "match_id", "innings_number", "over_number"]
    )
    grp_keys = ["bowler_canonical_id", "match_id", "innings_number"]
    gap = over_agg.groupby(grp_keys)["over_number"].diff().fillna(99) > 1
    over_agg["spell_id"] = gap.groupby([over_agg[k] for k in grp_keys]).cumsum()

    spells = over_agg.groupby(
        ["bowler_canonical_id", "bowler_canonical_name", "match_id", "innings_number", "spell_id"]
    ).agg(
        overs_in_spell=("over_number", "count"),
        legal_balls=("legal_balls", "sum"),
        runs=("runs", "sum"),
        wickets=("wickets", "sum"),
        dots=("dots", "sum"),
        competition=("competition", "first"),
    ).reset_index()
    spells["economy"] = spells["runs"] / (spells["legal_balls"] / 6)
    spells["is_2plus_wicket_spell"] = spells["wickets"] >= 2
    spells = spells[spells["legal_balls"] > 0].copy()  # drop 0-legal-ball "spells" (all-extras over)

    # --- Bowler-level rollup ---
    def bowler_stats(g):
        legal_balls = int(g["legal_balls"].sum())
        wickets = int(g["wickets"].sum())
        runs = int(g["runs"].sum())
        n_spells = len(g)
        econ = g["economy"]
        return pd.Series({
            "spells": n_spells,
            "overs_bowled": round(legal_balls / 6, 2),
            "legal_balls": legal_balls,
            "runs_conceded": runs,
            "wickets": wickets,
            "economy_overall": round(runs / (legal_balls / 6), 3) if legal_balls else None,
            "strike_rate_balls_per_wicket": round(legal_balls / wickets, 2) if wickets else None,
            "spell_economy_p10": round(float(econ.quantile(0.10)), 3) if n_spells else None,
            "spell_economy_p50": round(float(econ.quantile(0.50)), 3) if n_spells else None,
            "spell_economy_p90": round(float(econ.quantile(0.90)), 3) if n_spells else None,
            "two_plus_wicket_spell_rate": round(float(g["is_2plus_wicket_spell"].mean()), 4) if n_spells else None,
            "dot_ball_pct": round(float(g["dots"].sum() / g["legal_balls"].sum() * 100), 2) if legal_balls else None,
            "qualified": n_spells >= MIN_SPELLS_FOR_STATS,
        })

    bowler_summary = (
        spells.groupby(["bowler_canonical_id", "bowler_canonical_name"])
        .apply(bowler_stats, include_groups=False)
        .reset_index()
    )

    # expensive-over frequency, from over_agg (per-over grain, not per-spell)
    over_counts = over_agg.groupby(["bowler_canonical_id"]).agg(
        overs_bowled_count=("over_number", "count"),
        expensive_overs=("runs", lambda s: int((s >= EXPENSIVE_OVER_RUNS).sum())),
    ).reset_index()
    over_counts["expensive_over_rate"] = round(
        over_counts["expensive_overs"] / over_counts["overs_bowled_count"], 4
    )
    bowler_summary = bowler_summary.merge(
        over_counts[["bowler_canonical_id", "expensive_over_rate"]],
        on="bowler_canonical_id", how="left",
    )

    # --- Recency: last season each bowler actually appeared in, across ALL
    # competitions already in this dataset (IPL + 4 domestic leagues + 3
    # overseas franchise T20 leagues). NOTE: this pipeline has no international
    # (bilateral/World Cup) ball-by-ball data at all -- "international" can't be
    # filtered here because it isn't in the source; it only shows up later in
    # phase.md as a feature column ("international experience") fed from
    # elsewhere, not from this delivery-level dataset.
    last_active = fact.groupby("bowler_canonical_id")["start_year"].max().rename("last_active_season")
    bowler_summary = bowler_summary.merge(last_active, on="bowler_canonical_id", how="left")
    bowler_summary["is_recently_active"] = bowler_summary["last_active_season"] >= 2025

    bowler_summary = bowler_summary.sort_values("legal_balls", ascending=False).reset_index(drop=True)

    # --- Also emit a recently-active shortlist, since the full table is
    # dominated by long-retired low-sample domestic names once you sort by
    # rate stats alone. ---
    active_qualified = bowler_summary[bowler_summary["is_recently_active"] & bowler_summary["qualified"]]
    active_path = reports_dir / "eda_bowling_active_shortlist.csv"
    active_qualified.sort_values("economy_overall").to_csv(active_path, index=False)

    ipl_bowler_ids = set(spells.loc[spells["competition"] == "ipl", "bowler_canonical_id"])
    ipl_active_qualified = active_qualified[active_qualified["bowler_canonical_id"].isin(ipl_bowler_ids)]
    ipl_active_path = reports_dir / "eda_bowling_active_shortlist_ipl.csv"
    ipl_active_qualified.sort_values("economy_overall").to_csv(ipl_active_path, index=False)

    # --- Validation: cross-check bowling strike rate against known T20 scorecard
    # aggregates (~15-26 balls per wicket is the typical published IPL band) ---
    total_balls = int(over_agg["legal_balls"].sum())
    total_wkts = int(over_agg["wickets"].sum())
    overall_sr = total_balls / total_wkts
    in_band = 15.0 <= overall_sr <= 26.0
    print(f"Overall strike rate: {overall_sr:.2f} balls/wicket -- "
          f"{'within' if in_band else 'OUTSIDE'} the ~15-26 sanity band from published scorecard aggregates.")

    out_path = reports_dir / "eda_bowling_distributions.parquet"
    bowler_summary.to_parquet(out_path, index=False)
    bowler_summary.to_csv(reports_dir / "eda_bowling_distributions.csv", index=False)

    print(f"IPL-only recently active + qualified (stats still pooled across all their "
          f"leagues, not IPL-specific): {len(ipl_active_qualified):,} bowlers -> {ipl_active_path}")

    print(f"\nBowlers analyzed: {len(bowler_summary):,} | spells: {len(spells):,} | overs: {len(over_agg):,}")
    print(f"Recently active (last_active_season >= 2025) and qualified (>= {MIN_SPELLS_FOR_STATS} spells): "
          f"{len(active_qualified):,} bowlers -> {active_path}")
    top10 = active_qualified.nsmallest(10, "economy_overall")
    print(f"\nTop 10 RECENTLY ACTIVE (min {MIN_SPELLS_FOR_STATS} spells) by economy:")
    print(top10[["bowler_canonical_name", "last_active_season", "spells", "economy_overall",
                  "strike_rate_balls_per_wicket", "two_plus_wicket_spell_rate", "expensive_over_rate"]]
          .to_string(index=False))

    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
