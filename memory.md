# Project Memory & Progress Log

## Phase 2.3: Player Identity Resolution & Baseline Valuation (Completed)
- **Identity Resolution Strategy**: Multi-pass pipeline (Exact matching, Normalized strings, Fuzzy similarity >= 0.82, Surname + Initial patterns).
- **Match Rates**: Metadata/Participation: 99.88%, Auction Records: 83.13%. Unresolved edge cases: 141 records.
- **Valuation Model**: Pure NumPy/Pandas OLS linear regression model ($R^2 = 0.2645$, MAE = 13.47M, RMSE = 20.97M).
- **Deliverables**: `reports/RCB_Auction_Strategy_Report.md`, `reports/rcb_auction_target_shortlist.csv`.

## Phase 2.4: Competition & Season Normalization (Completed)
- **Script**: `src/cleaning/normalize_competitions.py`
- **Output Artifacts**: `data/processed/dim_competitions.parquet` & `data/processed/dim_competitions.csv` (75 mapped series).

## Phase 2.5: Venue Normalization & Mapping (Completed)
- **Script**: `src/cleaning/normalize_venues.py`
- **Output Artifacts**: `data/processed/dim_venues.parquet`, `configs/venue_mapping.json`
- **Result**: 180 raw venue strings -> 133 canonical venues, 0 unmapped.

## Phase 2.6: DuckDB & Parquet Storage Layer Integration (Descoped)
- **Status**: DESCOPED per phase.md v1.1 specification.
- **Notes**: Pandas + Parquet/CSV storage in `data/processed/` is operating under 2 seconds; DuckDB query layer bypassed.

## [MISLABELED — relabeled from prior "Phase 2.5"] Phase 4.4: Phase Features (build) — validation NOT yet confirmed
- **Script**: `src/features/build_delivery_features.py`
- **Output Artifacts**: `data/processed/fact_deliveries.parquet`, `data/processed/player_phase_features.parquet`, `data/processed/bowler_phase_features.csv`
- **Resolution**: Batter: 99.84%, Bowler: 99.98%.
- **Note**: This work matches Phase 4.4 ("Phase Features") in the real roadmap, not Phase 2.5. Phase 4.4's own spec'd validation checks (phase-run sums = season totals, over-boundary correctness at 5.6->6.0) had not been run against it as of this entry — see Phase 2.7 QA report below for a partial check (over-boundary only; phase-run-sum reconciliation against season totals is still outstanding).

## Phase 2.7: Automated Data-Quality Checks & Contract Validation (Completed)
- **Prerequisite fix**: `dim_competitions.parquet`/`dim_venues.parquet` were never joined to `fact_deliveries.parquet` (needed by Phase 3.1). Added `scripts/build_processed_layer.py` (plain pandas merge, no DuckDB — 2.6 stays descoped) joining on `(competition, season)` -> `dim_competitions` and `match_id` -> `matches.venue` -> `venue_mapping.json` -> `dim_venues`. 0 unmatched rows on both joins across 871,141 deliveries.
- **Script**: `src/validation/quality_checks.py`, runner `scripts/run_data_qa.py`
- **Output Artifacts**: `reports/data_quality_report.json`
- **Result**: 8/8 checks passed (no duplicate deliveries, required fields non-null, competition FK integrity, venue FK integrity, no orphan matches, run sanity, wicket sanity, phase over-boundary at 5.6->6.0).
- **New dependency**: `pandera` was imported by `src/validation/__init__.py` but missing from `requirements.txt` — added `pandera==0.33.1`.
