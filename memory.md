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
## Phase 3.4: Bowler Distributions & Spell Profile Analysis (Completed)
- **Script**: `src/analytics/eda_bowling.py`
- **Output Artifacts**: `reports/eda_bowling_distributions.parquet` (+ .csv), one row per bowler.
- **Grain fix**: used `is_legal_ball` (excludes wides AND no-balls — true 6-ball-over count), not `is_legal_delivery` (excludes only wides, used for batter balls-faced). Using the wrong flag would have silently misstated every economy rate.
- **Runs conceded**: excludes byes/leg-byes (not bowler's fault), includes wides/no-balls (is bowler's fault) — matches scorecard convention.
- **Partial-over handling (the failure mode phase.md warns about)**: overs aggregated at (bowler, match, innings, over) grain using each delivery's own bowler column, so a bowler injured/replaced mid-over is only charged for balls they actually bowled.
- **Spell definition**: maximal run of consecutive over_numbers by the same bowler in the same innings; broken by any gap.
- **Validation**: overall strike rate 19.37 balls/wicket — within ~15-26 sanity band from published scorecard aggregates.
- **Scale**: 1,666 bowlers, 97,805 spells, 2018-2026, super overs excluded.
- **Top economy (min 10 spells)**: mostly low-sample domestic bowlers (10-32 spells) — best read as a shortlist worth cross-checking, not a definitive ranking, given the qualification threshold is only 10 spells.

## Add-on: recency filtering for batting/bowling distributions (active-players ask)
- **Gap confirmed**: this pipeline has NO international (bilateral/World Cup) ball-by-ball data at all — only IPL + 4 domestic leagues (hnd/ilt/sat/sma) + 3 overseas franchise T20 leagues (bbl/cpl/mlc). "International experience" appears later in phase.md only as a feature column fed from elsewhere (auction data), not derivable from this dataset.
- **Data-quality note**: the bowler/batter pools mix men's and women's cricket (e.g. M Kapp, DB Sharma, SL Bates appear in the active bowling shortlist) — the dataset has no gender/competition-tier split. Flagged, not fixed (would need a different data source to separate WPL/women's leagues from men's competitions).
- **Fix**: added `last_active_season` (max start_year of any appearance, per scope) and `is_recently_active` (>= 2025) to both `eda_batting.py` and `eda_bowling.py` outputs. Added `reports/eda_batting_active_shortlist.csv` (533 batters) and `reports/eda_bowling_active_shortlist.csv` (482 bowlers) — qualified + recently active, sorted by batting average / economy respectively.

## Fix: men's-only filter for batting/bowling distributions
- **Root cause resolved**: `matches.parquet` has a real `gender` field (male/female) straight from the Cricsheet source, not inferred. Only `hnd` (The Hundred) mixes genders (201 male, 188 female matches); all 7 other competitions were already men's-only.
- **Fix**: both `eda_batting.py` and `eda_bowling.py` now merge `matches.gender` and filter to `gender == "male"` before all other processing.
- **Verified surgical**: IPL-specific numbers (Kohli avg 43.52, etc.) unchanged since IPL was already men's-only; only `hnd` rows and the previously-mixed active shortlists changed. Women's players (Kapp, Deepti Sharma, Bates) no longer appear. Bowling active shortlist top 10 is now: SP Narine, R Sai Kishore, Imad Wasim, Haider Ali, etc. — all correctly men's T20.

## Add-on: year-by-year breakdowns (IPL only)
- **Script changes**: `eda_batting.py` adds `season_distribution_table()` (same stats as the pooled table, grain = player x season, min 5 innings/season to qualify) -> `reports/eda_batting_by_season_ipl.csv` (1,429 rows). `eda_bowling.py` adds a season-grouped rollup from the same over-level data (min 10 overs/season to qualify) -> `reports/eda_bowling_by_season_ipl.csv` (1,059 rows).
- **Sanity check passed**: Bumrah's season table has no 2023 row — he missed IPL 2023 with a back injury, a real known fact, confirming the season split is correctly picking up match-level absence rather than defaulting/interpolating.
- **Kohli trend** (IPL by season): dipped to a 22.7 average in 2022, recovered to 53-62 average range 2023-2026.

## Phase 3.5: Domestic vs Franchise Competition Comparison (Completed)
- **Script**: `src/analytics/eda_domestic_translation.py`
- **Output Artifacts**: `reports/eda_domestic_vs_franchise.json`
- **Scope**: BATTERS ONLY -- "scoring rate"/"dot-ball %"/"boundary concessions" are batting-innings metrics; bowler-side comparison would double scope and isn't required by the single 30-player validation check. Not done for bowlers.
- **Crossover definition**: player has >=1 Domestic-category season (start_year) and >=1 IPL season with |domestic_year - ipl_year| <= 1 (adjacent seasons). Domestic = `competition_category == "Domestic"` (real column: sat/hnd/ilt/sma; verified against `eda_league_baselines.json`).
- **Survivorship-bias guard**: cohort membership decided purely by adjacent-season participation timing, never by IPL outcome. Same >=60-legal-balls-faced floor applied symmetrically to both tiers (not tuned toward IPL success).
- **Validation Check**: cohort must have >=30 qualified players -- run against real data and record actual count here (do not lower threshold to force a pass).
- **Result**: cohort = 146 qualified crossover players (>= 30 required, validation passed). Mean scoring-rate ratio (IPL/Domestic) = 1.015, median = 1.005 -- near parity. IPL shows higher dot% (37.16% vs domestic 35.77%) AND higher boundary% (18.41% vs 17.96%) than domestic -- tougher bowling forces more dots, but batters offset with more boundaries, netting near-equal scoring rate (domestic 137.98 vs IPL 138.43 runs/100 balls).

## Phase 3.6: Auction Economics & Historical Price Dynamics (Completed)
- **Script**: `src/analytics/eda_auction.py`
- **Output Artifacts**: `reports/eda_auction_economics.json`
- **Source schema gaps (documented, not fabricated)**: `role` missing for 2025-2026 (source dropped the column that era -- role-based stats incomplete for those years, flagged in `data_gaps`). `nationality` present only 2022-2026 -- overseas-vs-Indian ratio computed only over that window. No pre-auction retention-cost field exists anywhere in the source (only in-auction `sold_price`); "price retention premiums" is computed as `resale_premium` -- price ratio for players sold in >1 auction year -- explicitly labelled as a proxy, not real retention data.
- **Purse-expansion normalization (named failure mode)**: raw crore totals aren't comparable across years since the league cap itself grew (60cr 2014 -> 125cr 2026); every year's total spend is also reported as `spend_as_pct_of_cap`, using only years with a confirmed cap in `configs/purse_caps.yaml`.
- **Validation Check**: league-wide ceiling check -- total sold_price per year must not exceed (confirmed cap x franchise count) that year, checked only for years with a confirmed cap.
- **Result**: Ceiling check passed — 5 years with confirmed cap, 0 violations. Resale premium: 391 repeat-sale player-pairs, mean ratio 3.350x, median 1.091x (mean pulled up by outliers, max 118.75x). Overseas median price (2cr) is 4x Indian median (50L, 2022-2026 window); overseas total spend (93.11cr) slightly exceeds Indian total (87.26cr), ratio 1.067.
- **Bugs found & fixed during testing (before push)**: (1) `nationality` values are `"Indian"`/`"Overseas"`, not country names -- an initial `.eq("india")` match silently zeroed out the entire Indian-spend total. (2) `role` is spelled inconsistently within 2013-2024 itself (`Batsman`/`Batter`, `Wicket Keeper`/`Wicket-Keeper`) -- was splitting into 6 buckets instead of 4; fixed via `normalize_role()`/`ROLE_CANONICAL_MAP`. Both confirmed via `value_counts()` on the raw CSV before fixing, not guessed.

## Phase 4.1: Batting Features (Completed)
- **Script**: `src/features/batting.py`; **Tests**: `tests/test_batting_features.py` (8/8 pass, run locally before push)
- **Output Artifacts**: `data/features/batting_features.parquet`, grain = player x season
- **Reuse**: dismissal/out counting reuses `build_innings` from `src.analytics.eda_batting` (already tested pipe-separated-dismissal parsing) rather than re-deriving it.
- **Formula decisions (spec left implicit, stated explicitly here)**: `batting_average` = runs/dismissals, **NaN** (not 0) when never dismissed, matching real cricket convention. `boundary_dependency` = (4*fours+6*sixes)/runs, guarded to 0.0 at runs==0 (mathematically always in [0,1] since boundary runs are a subset of total runs). `rotation_rate` = (singles+doubles)/(balls_faced-fours-sixes), guarded to 0.0 at zero non-boundary balls. `acceleration_rate` = Death-phase strike rate minus Powerplay-phase strike rate per player-season (phase column from Phase 4.4's build_delivery_features.py); **NaN** (not 0) when a player faced 0 balls in either phase that season -- missing data, not "no acceleration".
- **Validation**: `validate_boundary_dependency()` asserts every row in [0,1]; covered by tests for zero-balls, zero-runs, mixed-scoring (dep==1.0 case), rotation-rate arithmetic, batting-average NaN vs computed, and both acceleration-rate cases.
- **Add-on: dual scope**: output now has both `all_t20_2018_2026` (pooled across every league) and `ipl_2018_2026` (IPL-only) rows per player-season, `scope` column. Needed because pooled numbers for globe-trotting T20 players (e.g. TH David) are much bigger than their IPL-only stats and were initially mistaken for a bug (his pooled 2022 total 761 runs = 354 BBL + 186 IPL + 85 CPL + 84 Hundred + 52 SMAT, confirmed by competition breakdown -- not an error). Also added `qualified` flag (`balls_faced >= 150` that season/scope, ~25 overs, filters cameo/short-stint noise).

## Phase 4.2: Bowling Features (Completed)
- **Script**: `src/features/bowling.py`; **Tests**: `tests/test_bowling_features.py` (8/8 pass, run locally before push)
- **Output Artifacts**: `data/features/bowling_features.parquet` (5,648 rows: 4,589 `all_t20_2018_2026` + 1,059 `ipl_2018_2026`), grain = `(scope, player_id, start_year)`
- **Column Schema**:
  - `scope` (string): `all_t20_2018_2026` or `ipl_2018_2026`
  - `player_id` (string): Canonical player ID
  - `player_name` (string): Canonical player name
  - `start_year` (int): Season calendar year (2018-2026)
  - `qualified` (bool): `overs_bowled >= 20.0` (120 legal balls) in that season/scope
  - `overs_bowled` (float): `legal_balls / 6.0` (unrounded fractional overs, uses `is_legal_ball`)
  - `legal_balls` (int): Total legal balls bowled (excludes wides and no-balls)
  - `runs_conceded` (int): `total_runs - byes_runs - legbyes_runs` (includes wides/no-balls, excludes byes/leg-byes)
  - `wickets` (int): Bowler-credited dismissals (`is_wicket` & `is_bowler_credited(dismissal_type)`)
  - `economy_rate` (float): `runs_conceded / overs_bowled` (0.0 when overs_bowled == 0)
  - `bowling_strike_rate` (float): `legal_balls / wickets` (NaN when wickets == 0, not 0.0 or inf)
  - `dot_ball_pct` (float): `(dots / legal_balls) * 100` (0.0 when legal_balls == 0)
  - `boundary_concession_pct` (float): `((fours + sixes) / legal_balls) * 100` (0.0 when legal_balls == 0)
  - `wicket_rate_per_over` (float): `wickets / overs_bowled` (0.0 when overs_bowled == 0)
  - `economy_variance_across_spells` (float): Population variance (`ddof=0`) of per-spell economy rates within player-season (0.0 when <= 1 spell)
- **Reuse**: Reuses `is_bowler_credited` and `BOWLER_CREDITED_KINDS` from `src.analytics.eda_bowling` for consistent wicket definitions across the pipeline.
- **Spell Detection**: Over-level aggregation (`bowler_canonical_id, match_id, innings_number, over_number`) with consecutive over sequence detection (`diff > 1` triggers new spell).

## Phase 4.3: Consistency Features (Completed)
- **Script**: `src/features/consistency.py`; **Tests**: `tests/test_consistency.py` (5/5 pass)
- **Output Artifacts**: `data/features/consistency_features.parquet` (8,795 rows: 7,158 `all_t20_2018_2026` + 1,637 `ipl_2018_2026`), grain = `(scope, player_id, start_year)`
- **PRD Note**: PRD.md SS5 defines the conceptual framework and badge names but does NOT specify numerical cutoffs. All thresholds below are explicit named constants, not black-box values.
- **Score Definition**: "score" = batting innings runs. Percentiles/median computed strictly on the batting-innings-runs distribution (runs and wickets are never merged into one scalar distribution).
- **Column Schema**:
  - `scope`, `player_id`, `player_name`, `start_year`
  - `qualified` (bool): `innings_batted >= QUALIFIED_INNINGS_SEASON` (10)
  - `matches_played`, `innings_batted`
  - `p10, p25, p50, p75, p90` (float): percentiles of innings-runs distribution
  - `median_score` (float): asserted equal to p50 at computation time
  - `failure_rate` (float): share of batting innings with runs < 10; denominator = innings_batted
  - `high_impact_rate` (float): share of match appearances with runs > 45 OR bowler-credited wickets >= 3 in that match; denominator = matches_played (includes bowling-only appearances) -- intentionally different denominator from failure_rate, documented in code
  - `consistency_badge` (string): one of Elite / High Floor / Boom-or-Bust / Moderate / Unqualified
- **Badge Thresholds** (named constants in consistency.py):
  - `ELITE_MAX_FAILURE_RATE = 0.35`, `ELITE_MIN_HIGH_IMPACT_RATE = 0.20`
  - `HIGH_FLOOR_MAX_FAILURE_RATE = 0.40`, `BOOM_MIN_HIGH_IMPACT_RATE = 0.20`
  - Elite: failure_rate <= 0.35 AND high_impact_rate >= 0.20
  - High Floor: failure_rate <= 0.40 AND high_impact_rate < 0.20
  - Boom-or-Bust: failure_rate > 0.35 AND high_impact_rate >= 0.20
  - Moderate: remaining qualified players
  - Unqualified: innings_batted < 10
- **Actual Badge Distribution**: Unqualified 7117, High Floor 559, Elite 487, Moderate 448, Boom-or-Bust 184
- **Reuse**: Reuses `is_bowler_credited` from `src.analytics.eda_bowling` for wicket crediting, consistent with Phase 4.2.

## Phase 4.9: League-Strength Adjustment Features (Completed)
- **Script**: `src/analytics/league_adjustment.py`; **Tests**: `tests/test_league_adjustment.py` (5/5 pass)
- **Output Artifacts**: `configs/league_strength_factors.json`, `data/features/league_adjusted_features.parquet` (8,795 rows)
- **Methodology**: Empirical crossover-player differential, NOT opinion-based. For each non-IPL competition, found players with qualified samples in both IPL and that competition; averaged the ratio of (other-league stat / IPL stat) across all crossover players. IPL fixed at 1.0 by definition.
- **Sample thresholds**: MIN_DISMISSALS_BATTING = 5, MIN_OVERS_BOWLING = 10.0. A league with zero qualified crossover players gets an explicit null factor + note, never silently defaults to 1.0.
- **Batting factor direction**: M_batting = 1 / mean(other_avg / ipl_avg). Multiplying a raw batting average in that league by M_batting scales it down to an IPL-equivalent.
- **Bowling factor direction**: M_bowling = 1 / mean(other_econ / ipl_econ). Multiplying a raw economy in that league by M_bowling scales it up to an IPL-equivalent (penalizes economies inflated only by easier league conditions).
- **Computed Factors** (M_batting / M_bowling / crossover player counts):
  - SMAT: 0.70 / 1.28 (n=78/94, largest crossover sample, most run-suppressive relative to IPL)
  - Hundred: 0.78 / 1.05 (n=58/48)
  - BBL: 0.79 / 1.11 (n=55/51)
  - MLC: 0.81 / 1.05 (n=44/37)
  - CPL: 0.81 / 1.09 (n=43/44)
  - ILT20: 0.76 / 1.12 (n=38/51)
  - SA20: 1.04 / 1.09 (n=37/47) -- see finding below
  - IPL: 1.00 / 1.00 (baseline, by definition)
- **Known finding**: SA20 does NOT follow the "all non-IPL leagues are easier" pattern -- batting factor is >1.0 (SA20 batting is marginally harder than IPL for crossover players) and bowling factor is >1.0 (SA20 bowling conditions favor bowlers more than IPL). This is reported as-is from real data rather than artificially capped at 1.0, consistent with SA20's reputation as a more bowler-friendly competition. Documented explicitly rather than treated as an anomaly to suppress.
- **Bug fixed during build**: initial implementation had batting and bowling per-competition diagnostic dicts sharing key names (`raw_ratio_other_over_ipl`, `n_crossover_players`, `note`), causing bowling values to silently overwrite batting ones on merge. Fixed by suffixing keys `_batting` / `_bowling`. Also fixed: leagues with zero qualified crossover players were being dropped entirely instead of appearing with a null factor + note (loop now iterates all competitions in raw data, not just those surviving the sample filter).
- **Known limitation**: `league_adjusted_features.parquet` applies factor=1.0 only to `ipl_2018_2026` scope rows; `all_t20_2018_2026` scope rows (which pool all competitions together) are left unadjusted since a single pooled scope cannot be assigned one league factor without breaking it into per-competition components -- would require a further per-competition feature rebuild if a fully adjusted blended metric is needed later.
