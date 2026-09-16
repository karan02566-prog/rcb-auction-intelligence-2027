"""
Phase 3.1 prerequisite: join fact_deliveries with dim_competitions and dim_venues.

fact_deliveries.parquet (from src/features/build_delivery_features.py) carries raw
'competition'/'season' but no dimension keys and no venue at all (deliveries.parquet
has no venue column -- venue lives on matches.parquet, keyed by match_id).

This script:
  1. Loads fact_deliveries.parquet, dim_competitions.parquet, dim_venues.parquet,
     matches.parquet (for match_id -> venue), and configs/venue_mapping.json
     (raw venue string -> venue_id).
  2. Joins competition_id/competition_category onto fact_deliveries via
     (competition, season) == (competition_raw, season_raw).
  3. Joins venue_id/venue_canonical onto fact_deliveries via match_id -> matches.venue
     -> venue_mapping.json -> dim_venues.
  4. Reports join-integrity counts (unmatched rows) before saving.
  5. Overwrites data/processed/fact_deliveries.parquet (+ .csv) with the joined table.

NOTE: this intentionally does NOT stand up a DuckDB layer -- Phase 2.6 (DuckDB &
Parquet Storage Layer) is descoped per phase.md v1.1. This is a plain pandas merge.
"""
import json
from pathlib import Path

import pandas as pd


def main():
    processed_dir = Path("data/processed")
    interim_dir = Path("data/interim")
    configs_dir = Path("configs")

    fact_path = processed_dir / "fact_deliveries.parquet"
    dim_comp_path = processed_dir / "dim_competitions.parquet"
    dim_venues_path = processed_dir / "dim_venues.parquet"
    matches_path = interim_dir / "matches.parquet"
    venue_mapping_path = configs_dir / "venue_mapping.json"

    for p in [fact_path, dim_comp_path, dim_venues_path, matches_path, venue_mapping_path]:
        if not p.exists():
            raise FileNotFoundError(f"Required input missing: {p}")

    fact = pd.read_parquet(fact_path)
    dim_comp = pd.read_parquet(dim_comp_path)
    dim_venues = pd.read_parquet(dim_venues_path)
    matches = pd.read_parquet(matches_path)
    venue_mapping = json.loads(venue_mapping_path.read_text(encoding="utf-8"))

    n_before = len(fact)
    print(f"Loaded fact_deliveries: {n_before:,} rows")

    # --- Join 1: competition dimension, on (competition, season) ---
    comp_cols = ["competition_id", "competition_category", "competition_canonical",
                 "season_canonical", "competition_raw", "season_raw"]
    fact = fact.merge(
        dim_comp[comp_cols],
        left_on=["competition", "season"],
        right_on=["competition_raw", "season_raw"],
        how="left",
    ).drop(columns=["competition_raw", "season_raw"])

    unmatched_comp = fact["competition_id"].isna().sum()
    print(f"Competition join: {unmatched_comp:,} / {n_before:,} rows unmatched "
          f"({unmatched_comp / n_before:.4%})")

    # --- Join 2: venue dimension, via match_id -> matches.venue -> mapping -> dim_venues ---
    match_venue = matches[["match_id", "venue"]].drop_duplicates()
    fact = fact.merge(match_venue, on="match_id", how="left")

    fact["venue_id"] = fact["venue"].map(venue_mapping)
    unmatched_venue_map = fact["venue"].notna().sum() - fact["venue_id"].notna().sum()
    print(f"Venue mapping (raw venue -> venue_id): {unmatched_venue_map:,} rows "
          f"with a venue string but no mapping entry")

    fact = fact.merge(
        dim_venues[["venue_id", "venue_canonical", "city"]],
        on="venue_id",
        how="left",
    )
    unmatched_venue = fact["venue_id"].isna().sum()
    print(f"Venue join: {unmatched_venue:,} / {n_before:,} rows unmatched "
          f"({unmatched_venue / n_before:.4%})")

    orphan_matches = fact.loc[fact["venue"].isna(), "match_id"].nunique()
    if orphan_matches:
        print(f"WARNING: {orphan_matches} distinct match_id(s) in fact_deliveries "
              f"have no matching row in matches.parquet (orphan matches).")

    n_after = len(fact)
    if n_after != n_before:
        print(f"WARNING: row count changed during join ({n_before:,} -> {n_after:,}) "
              f"-- check for duplicate keys on the dimension side.")

    out_parquet = processed_dir / "fact_deliveries.parquet"
    out_csv = processed_dir / "fact_deliveries.csv"
    fact.to_parquet(out_parquet, index=False)
    fact.to_csv(out_csv, index=False)
    print(f"\nSaved joined fact_deliveries: {out_parquet} ({n_after:,} rows, "
          f"{len(fact.columns)} cols)")


if __name__ == "__main__":
    main()
