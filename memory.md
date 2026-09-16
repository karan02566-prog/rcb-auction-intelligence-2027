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

## Bug Fix: is_wicket derivation (found via Phase 3.1 sanity check)
- **Root cause**: `build_delivery_features.py` checked `df[dismissal_col].dtype in [int, float]` to branch its wicket logic. `dismissal_count` is pandas nullable `Int64`, which never matches Python's built-in `int`/`float` types, so every row fell to the `.notna()` branch — and since non-wicket rows have `dismissal_count == 0` (not null), **100% of the 871,141 deliveries were flagged as wickets.**
- **Impact**: `is_wicket` in `fact_deliveries.parquet`, and `wickets` in `bowler_phase_features.csv`/`player_phase_features.parquet`, were wrong in every prior run (including the Phase 4.4 output logged above and the Phase 2.7 QA run — the old `wicket_sanity` check only verified values were in `{0,1}`, which 100%-wickets still satisfies).
- **Fix**: switched to `pd.api.types.is_numeric_dtype(...)` and compare `> 0` regardless of dtype family. Verified: wicket rate now 5.42% of legal balls (correct order of magnitude for T20 cricket).
- **Hardened**: Phase 2.7's `wicket_sanity` check now also asserts the overall wicket rate falls in a plausible 1%-15% band, not just that values are binary — this specific bug would now fail Phase 2.7 QA instead of passing silently.
- **Action required downstream**: `player_phase_features.parquet` and `bowler_phase_features.csv` (Phase 4.4 outputs) must be regenerated — done as part of this fix by rerunning `build_delivery_features.py`. Any report or model built on the old wicket counts before this fix should be treated as invalid.

## Phase 3.1: League Scoring Environments & Baseline Comparison (Completed)
- **Script**: `src/analytics/eda_leagues.py`
- **Output Artifacts**: `reports/eda_league_baselines.json`
- **Scope**: Seasons 2018-2026, super overs excluded (different format, not a truncation case); no DLS/rain-truncation adjustment (scoped down per phase.md v1.1).
- **Result** (run rate / boundary% / wicket rate per 100 legal balls): IPL 8.89 / 19.05% / 5.18 — highest run rate and boundary% of all 8 competitions in range. Full ranked table in the JSON report.
- **Validation**: Computed IPL run rate (8.89) checked against published IPL season summaries (~7.0-9.5 historical band) — within range.

## Gap Fix: dim_players.parquet was never built (found while starting Phase 3.3)
- **Root cause**: Phase 2.3 spec'd `processed/dim_players.parquet` as a deliverable, but the implemented pipeline (`generate_player_mapping.py` -> `apply_player_mapping.py` -> `apply_fuzzy_overrides.py`) only ever produced `configs/player_mapping.json`. No script wrote the dimension table itself.
- **Fix**: Added `src/cleaning/build_dim_players.py` — collapses `player_mapping.json`'s `mapped` entries to one row per `canonical_id` (best confidence + majority name kept), joins Cricsheet register fields (`identifier`, `name`, `unique_name`, key_* ids) where available, and attaches batter/bowler appearance counts from `fact_deliveries.parquet`. Validates zero duplicate/null `player_id`. Also fixed `apply_player_mapping.py`'s mapping-file path to be project-root-relative (`get_project_root()`) instead of cwd-relative, since it's now imported from a different working directory.
- **Result**: **3,048 unique canonical players.**

## Phase 3.3: Batter Distributions & Milestone Profile Analysis (Completed)
- **Script**: `src/analytics/eda_batting.py`
- **Output Artifacts**: `reports/eda_batting_distributions.parquet` (+ .csv), scoped both `all_t20_2018_2026` and `ipl_2018_2026`.
- **Not-out handling (the failure mode phase.md explicitly warns about)**: not-out innings are censored, not treated as completed/failed scores. Milestone reach rates reported three ways per threshold (20/30/50): `naive` (not-outs below threshold count as failures), `complete_case` (drop not-outs that never reached it), and `kaplan_meier` (product-limit survival estimate of true latent score). `retired hurt`/`retired not out` are treated as censored, matching batting-average convention; other dismissal kinds count. Handles pipe-separated multi-dismissal Cricsheet records and run-out non-strikers who never faced a ball.
- **Validation**: pooled median 11.0 < mean 18.55 (skew 1.673, n=40,338 innings) — right-skewed as required, check passes.
- **IPL qualified batters (>=10 innings, 2018-2026)**: 202 players; median<mean holds for 96.5% of them. Duck rate distribution: p10=0%, median=7.5%, p90=20%.
- **V Kohli, IPL 2018-2026**: avg 43.52 across 134 innings, median 31.5, duck rate 4.5%, Kaplan-Meier P(50+) 34.8%.
- **Tests**: 11/11 pass (`tests/test_dim_players.py`, `tests/test_eda_batting.py`) — covers not-out-zero-not-a-duck, retired-hurt censoring, KM correctness, conversion excluding stranded not-outs, right-skew assertion.