# RCB Auction Intelligence Engine — Implementation Roadmap (`phases.md`)

**Document status:** Approved v1.0, amended v1.1 (internship-timeline scope amendment — see below)

**Authoritative context:** `PRD.md`, `architecture.md`, `rules.md`

---

## Standard Subphase Execution Workflow

To guarantee incremental progress, zero technical debt accumulation, and strict auditability, every subphase across Phase 0 through Phase 11 must strictly follow this mandatory 5-step exit protocol before moving to the next task:

1. **Working Output:** Executable code, passing unit/integration tests, and verified artifacts stored in designated pipeline paths.
2. **Validation:** Automated test pass (`pytest`), schema contract check (`pandera`), and manual spot-check of produced data files.
3. **Documentation Update:** Record architectural changes, feature definitions, or schema updates in relevant project markdown files.
4. **Git Commit:** Execute a atomic Git commit adhering strictly to the commit convention specified in `rules.md`.
5. **Memory Update:** Log subphase completion, decision rationale, and state in `memory.md`.

## Scope Amendment (v1.1) — Internship-Timeline Descope

**Reason:** The original v1.0 roadmap targets a comprehensive, portfolio-grade system (Power BI dashboard, full OR-Tools optimizer, SHAP explainability, exhaustive QA). The actual near-term goal is a credible, well-reasoned RCB IPL 2027 auction target shortlist to send to RCB's coaching staff, on a 1-2 month timeline. Every subphase below is tagged with its status under this amendment. **No subphase content below has been deleted or altered** — this amendment only adds scope tags so v1.0 remains fully recoverable if the timeline changes later.

**Tags:**
- **IN SCOPE** — required for the shortlist deliverable; do this.
- **SCOPED DOWN** — do a lighter version than v1.0 describes (see note under the subphase); do not build the full version described.
- **DESCOPED** — skip entirely for this timeline; revisit only if time remains or a future iteration is planned.

**Known correction folded into this amendment:** Phase 1.4.1's locked 27-field auction schema (`retention_status`, `retention_price_inr_lakh`, `season_franchise_purse_crore`, etc.) was written before the chosen Kaggle source was checked against it. The source (`sunnyyadav754/ipl-auction-dataset-20132026`) only provides 7 raw columns (`Name`, `Nationality`, `BasePrices in Rs`, `Winning Bid in Rs`, `TeamName`, `Capped/UnCapped`, plus an index) — it has no retention data and no unsold-player records. Phase 1.4's exit criteria are revised down to match what this source can actually supply; the "verify sum of franchise spends aligns with purse caps" validation check is satisfied instead by `src/validation/purse_cap_check.py`, using an externally-sourced purse-cap-per-year reference table (`configs/purse_caps.yaml`) rather than a per-row field, since the source has no such field to provide.

**Replacement deliverable for Phase 9 (Power BI):** a written PDF/deck (folded into Phase 11.1) rather than an interactive dashboard.

---

## PHASE 0 — Project Foundation

### 0.1 Repository Setup & Folder Hierarchy

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Establish the foundational directory layout, repository, and core tracking files per `architecture.md`.
* **Inputs:** `PRD.md`, `architecture.md`, `rules.md`.
* **Work:** Create standard root directory structure (`data/{raw,interim,processed,features,exports}`, `notebooks/`, `src/{ingestion,cleaning,validation,features,models,optimization,analytics,utils}`, `tests/`, `models/`, `reports/`, `powerbi/`, `configs/`, `scripts/`). Initialize Git repository. Create initial `.gitignore` (ignoring data binaries, local environments, `.pbix` cache).
* **Deliverables:** Directory tree created; `.gitignore` configured; initial repository committed.
* **Validation Checks:** Run `git status` to verify untracked files match `.gitignore` rules; verify directory existence via script.
* **Common Failure Modes:** Accidentally committing large data binaries to Git; missing empty placeholder `.gitkeep` files in data directories.
* **Commit Message:** `feat(repo): initialize directory structure and git configuration`
* **memory.md Update Requirement:** Record Phase 0.1 completion and commit hash.
* **Exit Criteria:** Clean Git tree with standard project layout in place.

### 0.2 Environment & Dependency Management

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Configure Python runtime environment and pinned dependency management.
* **Inputs:** `rules.md` (Section 13 on approved libraries).
* **Work:** Create `requirements.txt` with pinned versions (`pandas`, `numpy`, `duckdb`, `pyarrow`, `scikit-learn`, `xgboost`, `scipy`, `matplotlib`, `plotly`, `pytest`, `pandera`, `ortools`, `pyyaml`). Create `setup.py` / `pyproject.toml` for local editable package installation (`pip install -e .`).
* **Deliverables:** `requirements.txt`, editable installation script, isolated virtual environment.
* **Validation Checks:** Execute `pip check` inside virtual environment to verify zero dependency conflicts; run `python -c "import duckdb, pandas, sklearn, ortools"`.
* **Common Failure Modes:** Unpinned packages leading to non-reproducible builds; installing unapproved libraries.
* **Commit Message:** `build(env): define base dependencies and local package installation`
* **memory.md Update Requirement:** Document Python version and exact library versions.
* **Exit Criteria:** Environment cleanly installs and all imports succeed without warnings.

### 0.3 Quality & Configuration Foundation

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Implement logging, configuration loading, custom exception classes, and `pytest` foundation.
* **Inputs:** `rules.md` (Section 10 & 11).
* **Work:** Build `src/utils/config.py` to parse YAML configurations from `configs/`. Build `src/utils/logger.py` for structured logging. Define custom exceptions in `src/utils/exceptions.py`. Set up basic `conftest.py` in `tests/`.
* **Deliverables:** Operational config parser, centralized logger, custom error classes, passing baseline test.
* **Validation Checks:** Run `pytest` to confirm test runner works; run sample script generating structured log outputs.
* **Common Failure Modes:** Hardcoded path assumptions; uncaught exception handling in configuration loader.
* **Commit Message:** `feat(infra): add logger, config loader, custom exceptions, and test runner`
* **memory.md Update Requirement:** Log baseline infrastructure setup and logging formats.
* **Exit Criteria:** `pytest tests/` runs cleanly with 100% pass rate on core utility tests.

---

## PHASE 1 — Data Acquisition

### 1.1 Source Inventory & Manifest Framework

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Document and structure all external data sources and define source manifest schemas.
* **Inputs:** `PRD.md` Section 7.2, `rules.md` Section 2.
* **Work:** Build `configs/source_manifest.json` cataloging Cricsheet formats, auction price datasets, player biographical links, and venue metadata. Create `src/ingestion/manifest.py` to validate source integrity and file hashes.
* **Deliverables:** `configs/source_manifest.json`, manifest validation utility.
* **Validation Checks:** Verify manifest file exists and adheres to valid JSON schema; run manifest check script against sample files.
* **Common Failure Modes:** Unversioned external URLs; missing metadata fields (retrieval date, license, scope).
* **Commit Message:** `docs(data): establish data source manifest and integrity catalog`
* **memory.md Update Requirement:** Document all cataloged data sources and retrieval dates.
* **Exit Criteria:** Source catalog fully populated for all required competitions (IPL, BBL, CPL, SA20, ILT20, MLC, The Hundred, Indian Domestic T20s).

### 1.2 Cricsheet Ball-by-Ball Ingestion

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Automated download, extraction, and verification of Cricsheet T20 ball-by-ball JSON/CSV datasets.
* **Inputs:** `configs/source_manifest.json`.
* **Work:** Implement `src/ingestion/cricsheet.py` to download match datasets for designated competitions. Store raw zip/json archives in `data/raw/cricsheet/`. Calculate and verify SHA-256 hashes against manifest.
* **Deliverables:** Raw Cricsheet data files in `data/raw/cricsheet/`, raw ingestion execution script `scripts/ingest_cricsheet.py`.
* **Validation Checks:** Verify file count and non-zero byte size for each competition; test hash match for downloaded archives.
* **Common Failure Modes:** Network timeout handling failure; incomplete zip extractions.
* **Commit Message:** `feat(ingestion): implement Cricsheet ball-by-ball data ingestion`
* **memory.md Update Requirement:** Log match counts per competition downloaded.
* **Exit Criteria:** Raw ball-by-ball match files saved in `data/raw/cricsheet/` with verified checksums.

### 1.3 Metadata & Biographical Ingestion

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Ingest player rosters, official player IDs, roles, bowling styles, batting positions, and competition metadata.
* **Inputs:** Official competition records, Cricsheet player registry.
* **Work:** Implement `src/ingestion/metadata.py` to pull player profile attributes, official team historical rosters, and competition schedules into `data/raw/metadata/`.
* **Deliverables:** Raw player and team metadata tables in `data/raw/metadata/`.
* **Validation Checks:** Validate presence of key demographic fields (age, role, primary skill, nationality) for candidate pool.
* **Common Failure Modes:** Missing player metadata for emerging domestic players; conflicting team names across seasons.
* **Commit Message:** `feat(ingestion): ingest player biographical and competition metadata`
* **memory.md Update Requirement:** Record count of ingested unique player profiles and teams.
* **Exit Criteria:** Player metadata files stored cleanly under `data/raw/metadata/`.

### 1.4 Auction Data Ingestion

> **Scope status (v1.1):** SCOPED DOWN — exit criteria revised; see Scope Amendment note on the source's actual 7-column schema (no retention/unsold data available).

* **Objective:** Ingest historical IPL auction prices, retention amounts, player price bands, and unsold lists (2018–2026).
* **Inputs:** Public IPL auction records, official press releases.
* **Work:** Implement `src/ingestion/auction.py` to structure historical auction datasets into `data/raw/auction/`. Capture player name, year, franchise, sold price, base price, retention status, and currency.
* **Deliverables:** `data/raw/auction/ipl_auction_history.csv` and parser script.
* **Validation Checks:** Verify sum of franchise spends per season aligns with official purse caps; check for missing historical price entries.
* **Common Failure Modes:** Currency conversion errors (USD vs INR Lakhs/Crores); name mismatches in auction lists vs match scorecards.
* **Commit Message:** `feat(ingestion): ingest historical IPL auction prices and retention records`
* **memory.md Update Requirement:** Record historical price database summary (years covered, total bid records).
* **Exit Criteria:** Complete historical auction table saved in `data/raw/auction/`.

### 1.5 Provenance & Source Manifest Verification

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Execute full verification of raw data layer and generate immutable source manifest report.
* **Inputs:** Ingested files across `data/raw/`.
* **Work:** Implement `src/ingestion/verify_provenance.py` to audit all downloaded files against `configs/source_manifest.json`. Generate `reports/data_provenance_manifest.json`.
* **Deliverables:** Automated provenance verification report in `reports/`.
* **Validation Checks:** 100% match on file SHA-256 signatures; zero untracked files in `data/raw/`.
* **Common Failure Modes:** Ingestion script modifying raw file contents during download/decompression.
* **Commit Message:** `test(ingestion): generate data provenance and verification manifest`
* **memory.md Update Requirement:** Log complete data provenance confirmation.
* **Exit Criteria:** Provenance verification script passes with 0 errors.

---

## PHASE 2 — Data Engineering & Normalization

### 2.1 Raw Data Normalization

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Parse raw JSON/CSV data structures into clean relational representations without altering underlying facts.
* **Inputs:** `data/raw/cricsheet/*`.
* **Work:** Write `src/cleaning/normalize_raw.py` to parse complex nested Cricsheet JSON structures into standardized tables (`interim/matches.parquet`, `interim/deliveries.parquet`). Handle extra/penalty runs, dismissal classifications, and legal ball flags.
* **Deliverables:** Normalized interim Parquet datasets in `data/interim/`.
* **Validation Checks:** Check that total legal balls per match equals expected over count; verify delivery sequence integrity.
* **Common Failure Modes:** Incorrect handling of super overs, wide balls, or no-balls in ball numbering logic.
* **Commit Message:** `feat(cleaning): parse and normalize raw Cricsheet data to interim Parquet`
* **memory.md Update Requirement:** Record parsed row counts for deliveries and matches.
* **Exit Criteria:** Clean Parquet tables generated under `data/interim/`.

### 2.2 Match & Delivery Schema Construction

> **Scope status (v1.1):** IN SCOPE - COMPLETE

* **Objective:** Define explicit `pandera` schemas for matches and ball-by-ball delivery tables.
* **Inputs:** `data/interim/*.parquet`.
* **Work:** Implemented `src/validation/schemas.py` with strict, non-coercing Pandera schemas for the exact Phase 2.1 match and delivery columns, plus separate semantic, referential, metadata, key, and ordering checks.
* **Deliverables:** `MATCH_SCHEMA` and `DELIVERY_SCHEMA`, real-Parquet validator, and focused tests in `tests/test_schemas.py`.
* **Validation Checks:** Passed schema and cross-table validation over both generated `interim` Parquet datasets, including miscounted-over, super-over, and extra-run edge cases.
* **Common Failure Modes:** Silent type coercions (e.g., string to float for integer IDs); unhandled boundary values.
* **Commit Message:** `feat(validation): create pandera schemas for match and delivery records`
* **memory.md Update Requirement:** Record schema rules and validation outcomes.
* **Exit Criteria:** Complete. Pandera validation succeeds across 100% of interim delivery records and all focused tests pass.

### 2.3 Player Identity Resolution & Canonical Mapping

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Resolve player name spelling variants across Cricsheet, auction files, and metadata into unique `player_id`s.
* **Inputs:** `data/interim/deliveries.parquet`, `data/raw/metadata/`, `data/raw/auction/`.
* **Work:** Build `src/cleaning/entity_resolution.py` using explicit mapping dictionary (`configs/player_mapping.json`) supplemented with string similarity matching. Map all historical occurrences to a canonical `player_id`.
* **Deliverables:** Canonical `configs/player_mapping.json` and resolved `processed/dim_players.parquet`.
* **Validation Checks:** Assert zero unmapped player names in match/delivery logs; verify zero duplicate canonical IDs.
* **Common Failure Modes:** Collapsing two distinct players with identical initials; leaving name variants unlinked.
* **Commit Message:** `feat(cleaning): implement canonical player identity resolution pipeline`
* **memory.md Update Requirement:** Document unique player count resolved and mapping rules.
* **Exit Criteria:** All player references across match and auction data resolve to single canonical `player_id`.

### 2.4 Competition & Season Normalization

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Standardize competition names, season formats, and match dates into uniform reference structures.
* **Inputs:** `data/interim/matches.parquet`.
* **Work:** Build `src/cleaning/normalize_competitions.py` mapping diverse season nomenclature (e.g., "2023/24", "2023", "Season 10") into standard year/season keys and linking to competition tiers (`dim_competitions.parquet`).
* **Deliverables:** `data/processed/dim_competitions.parquet` and updated `matches` metadata.
* **Validation Checks:** Verify all dates follow ISO-8601; check that competition categories map correctly (IPL, Domestic, Overseas Franchise).
* **Common Failure Modes:** Overlapping season keys across northern/southern hemisphere tournaments.
* **Commit Message:** `feat(cleaning): standardize competition and season metadata schema`
* **memory.md Update Requirement:** Record mapped competition categories and season ranges.
* **Exit Criteria:** `dim_competitions` populated cleanly in `data/processed/`.

### 2.5 Venue Normalization & Mapping

> **Scope status (v1.1):** SCOPED DOWN — basic venue name/city normalization only, not full physical-characteristics profiling.

* **Objective:** Standardize ground/venue names, city locations, and physical ground identity.
* **Inputs:** `data/interim/matches.parquet`.
* **Work:** Implement `src/cleaning/normalize_venues.py` mapping raw venue strings (e.g., "M. Chinnaswamy Stadium", "Chinnaswamy", "M Chinnaswamy Stadium, Bengaluru") to a canonical `venue_id` in `dim_venues.parquet`.
* **Deliverables:** `configs/venue_mapping.json`, `data/processed/dim_venues.parquet`.
* **Validation Checks:** Ensure venue separation from pitch archetype per PRD §6.1; check zero unmapped venues in match history.
* **Common Failure Modes:** Conflating ground name changes (e.g., Feroz Shah Kotla -> Arun Jaitley Stadium) into separate physical venues without lineage.
* **Commit Message:** `feat(cleaning): build canonical venue reference and normalization mapping`
* **memory.md Update Requirement:** Log unique canonical venue count.
* **Exit Criteria:** 100% of venues mapped to canonical `venue_id` in `data/processed/dim_venues.parquet`.

### 2.6 DuckDB & Parquet Storage Layer Integration

> **Scope status (v1.1):** DESCOPED — plain pandas + CSV/Parquet files are sufficient at this scale; skip the DuckDB query layer.

* **Objective:** Build DuckDB analytical engine wrapper and persist processed tables to columnar Parquet format.
* **Inputs:** `data/interim/*.parquet`, `data/processed/dim_*.parquet`.
* **Work:** Implement `src/utils/db.py` setting up embedded DuckDB instance. Write ETL script `scripts/build_processed_layer.py` joining interim tables with resolved dimension keys, creating `data/processed/fact_deliveries.parquet` and `data/processed/fact_matches.parquet`.
* **Deliverables:** Structured `data/processed/` Parquet storage layer and DuckDB database helper interface.
* **Validation Checks:** Query DuckDB directly to verify join integrity between fact and dimension tables; measure query latency (< 500ms for full aggregations).
* **Common Failure Modes:** Out-of-memory errors on unoptimized joins; schema drift during parquet export.
* **Commit Message:** `feat(storage): build DuckDB analytical engine layer and processed Parquet tables`
* **memory.md Update Requirement:** Record Parquet file sizes and DuckDB table row counts.
* **Exit Criteria:** DuckDB queries run cleanly over `data/processed/*.parquet` files.

### 2.7 Automated Data-Quality Checks & Contract Validation

> **Scope status (v1.1):** SCOPED DOWN — targeted checks on the fields the models actually use, not a full contract-validation suite.

* **Objective:** Implement comprehensive data quality suite enforcing contract requirements before feature engineering.
* **Inputs:** `data/processed/*.parquet`.
* **Work:** Build `src/validation/quality_checks.py` running automated data quality tests: null value checks, duplicate delivery detection, referential integrity across foreign keys, and run/wicket sanity assertions.
* **Deliverables:** Executable QA pipeline `scripts/run_data_qa.py` producing `reports/data_quality_report.json`.
* **Validation Checks:** Assert 0 foreign key violations, 0 duplicate deliveries, and 0 orphan matches.
* **Common Failure Modes:** Suppressing QA test failures; soft warnings masking critical data omissions.
* **Commit Message:** `test(cleaning): implement data quality validation suite and contract checks`
* **memory.md Update Requirement:** Log QA test suite results and audit status.
* **Exit Criteria:** Data quality suite passes with zero blocking errors across all processed tables.

---

## PHASE 3 — Exploratory Data Analysis (EDA)

### 3.1 League Scoring Environments & Baseline Comparison

> **Scope status (v1.1):** SCOPED DOWN — quick sanity-check plots only, not a full comparative study.

* **Objective:** Quantify baseline scoring environments (run rate, boundary %, wicket rate) across target competitions.
* **Inputs:** `data/processed/fact_deliveries.parquet`, `data/processed/dim_competitions.parquet`.
* **Work:** Build `src/analytics/eda_leagues.py` to calculate macro league parameters across seasons (2018–2026). Save output summary to `reports/eda_league_baselines.json`.
* **Deliverables:** League baseline statistics report and comparative dataset.
* **Validation Checks:** Compare computed IPL average run rate against official IPL season summaries to verify alignment.
* **Common Failure Modes:** Including rain-affected truncated matches without over-adjustment.
* **Commit Message:** `feat(analytics): analyze league scoring environments and baseline benchmarks`
* **memory.md Update Requirement:** Document baseline run rates and wicket rates by competition.
* **Exit Criteria:** Baseline scoring metric export generated in `reports/`.

### 3.2 Venue Characteristics & Physical Environment Analysis

> **Scope status (v1.1):** DESCOPED — not required for the shortlist; venue depth isn't the differentiator here.

* **Objective:** Perform exploratory spatial and environmental profile analysis per canonical venue.
* **Inputs:** `data/processed/fact_deliveries.parquet`, `data/processed/dim_venues.parquet`.
* **Work:** Build `src/analytics/eda_venues.py` computing per-venue average 1st innings score, pace vs spin bowling average/economy ratio, boundary distance impact proxy, and toss decision win rates.
* **Deliverables:** `reports/eda_venue_profiles.csv`.
* **Validation Checks:** Verify M. Chinnaswamy Stadium parameters (high boundary rate, higher run rate) reflect known ground characteristics.
* **Common Failure Modes:** Small sample bias on venues with under 3 recorded matches.
* **Commit Message:** `feat(analytics): perform exploratory analysis on venue physical environments`
* **memory.md Update Requirement:** Record key venue analytical insights.
* **Exit Criteria:** Venue EDA dataset saved under `reports/`.

### 3.3 Batter Distributions & Milestone Profile Analysis

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Analyze batting performance distributions, variance, and milestone conversion rates.
* **Inputs:** `data/processed/fact_deliveries.parquet`, `data/processed/dim_players.parquet`.
* **Work:** Implement `src/analytics/eda_batting.py` calculating score distributions, skewness, median innings score, 20+/30+/50+ transition rates, and duck frequencies across player cohorts.
* **Deliverables:** `reports/eda_batting_distributions.parquet`.
* **Validation Checks:** Assert median score is consistently lower than mean score across batting distributions (typical right-skewed property).
* **Common Failure Modes:** Treating not-out innings as complete scores without survival probability adjustment.
* **Commit Message:** `feat(analytics): evaluate batting performance distribution and milestone rates`
* **memory.md Update Requirement:** Note key distribution properties of top IPL batters.
* **Exit Criteria:** Batting EDA distribution dataset exported to `reports/`.

### 3.4 Bowler Distributions & Spell Profile Analysis

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Analyze bowling spell variance, economy rate stability, and wicket-taking frequency.
* **Inputs:** `data/processed/fact_deliveries.parquet`, `data/processed/dim_players.parquet`.
* **Work:** Implement `src/analytics/eda_bowling.py` computing per-spell economy rate percentiles, 2+ wicket spell frequency, dot-ball concentration, and expensive over frequency.
* **Deliverables:** `reports/eda_bowling_distributions.parquet`.
* **Validation Checks:** Cross-check computed bowling strike rates against scorecard aggregates.
* **Common Failure Modes:** Aggregating partial overs incorrectly during mid-over injuries or suspensions.
* **Commit Message:** `feat(analytics): evaluate bowling spell distributions and economy variance`
* **memory.md Update Requirement:** Record bowling distribution summary insights.
* **Exit Criteria:** Bowling EDA summary exported to `reports/`.

### 3.5 Domestic vs Franchise Competition Comparison

> **Scope status (v1.1):** IN SCOPE — directly supports the domestic-to-franchise translation work, which matters for uncapped/domestic targets.

* **Objective:** Explore statistical divergence between domestic T20 performance (e.g., SMAT) and franchise T20s (IPL).
* **Inputs:** `data/processed/fact_deliveries.parquet`.
* **Work:** Implement `src/analytics/eda_domestic_translation.py` tracking crossover players who played both domestic and IPL in adjacent seasons. Compare scoring rates, dot ball percentages, and boundary concessions.
* **Deliverables:** Exploratory crossover analysis report in `reports/eda_domestic_vs_franchise.json`.
* **Validation Checks:** Ensure crossover cohort includes a minimum of 30 qualified players.
* **Common Failure Modes:** Survivorship bias (only analyzing domestic players who succeeded in IPL).
* **Commit Message:** `feat(analytics): execute comparative analysis between domestic and franchise data`
* **memory.md Update Requirement:** Document observed performance drop-off/increase ratios for crossover players.
* **Exit Criteria:** Crossover EDA output generated and logged.

### 3.6 Auction Economics & Historical Price Dynamics

> **Scope status (v1.1):** IN SCOPE — partially complete via the purse-cap ceiling validation already built.

* **Objective:** Explore historical auction price distributions, inflation rates, and role-based spending trends (2018–2026).
* **Inputs:** `data/raw/auction/ipl_auction_history.csv`.
* **Work:** Build `src/analytics/eda_auction.py` calculating median and peak prices by player role, overseas vs Indian spend ratios, and price retention premiums.
* **Deliverables:** `reports/eda_auction_economics.json`.
* **Validation Checks:** Verify total yearly auction spend sum matches total purse expanded across all franchises.
* **Common Failure Modes:** Failing to normalize for purse expansion across different auction cycles.
* **Commit Message:** `feat(analytics): explore historical auction price distributions and role premiums`
* **memory.md Update Requirement:** Record historical price thresholds per player role category.
* **Exit Criteria:** Auction economics exploratory script complete and report output generated.

---

## PHASE 4 — Advanced Feature Engineering

### 4.1 Batting Features

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Engineer comprehensive volume, rate, acceleration, and boundary dependency features for batters.
* **Inputs:** `data/processed/fact_deliveries.parquet`.
* **Work:** Implement `src/features/batting.py`. Compute metrics per player-season: runs, balls faced, batting average, strike rate, dot ball %, boundary %, boundary dependency (boundary runs / total runs), rotation rate (singles+doubles / non-boundary balls), and scoring acceleration rate.
* **Deliverables:** `data/features/batting_features.parquet`, unit tests in `tests/test_batting_features.py`.
* **Validation Checks:** Verify mathematical correctness of boundary dependency formula ($0.0 \le \text{dep} \le 1.0$); test edge cases (0 runs, 0 balls faced).
* **Common Failure Modes:** Division by zero on 0 balls faced; miscalculating non-boundary strike rate.
* **Commit Message:** `feat(features): build core batting rate, volume, and acceleration metrics`
* **memory.md Update Requirement:** Document computed batting feature list and column schema.
* **Exit Criteria:** `pytest tests/test_batting_features.py` passes 100%.

### 4.2 Bowling Features

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Engineer bowling rate, volume, spell-shape, and economy stability features.
* **Inputs:** `data/processed/fact_deliveries.parquet`.
* **Work:** Implement `src/features/bowling.py`. Calculate per player-season: wickets, overs bowled, runs conceded, economy rate, bowling strike rate, dot ball %, boundary concession %, wicket rate per over, and economy rate variance across spells.
* **Deliverables:** `data/features/bowling_features.parquet`, unit tests in `tests/test_bowling_features.py`.
* **Validation Checks:** Validate economy rate formula ($\text{runs} / \text{overs}$); check partial over handling ($1 \text{ ball} = 0.1667 \text{ overs}$).
* **Common Failure Modes:** Incorrectly summing balls faced instead of legal balls bowled for economy calculations.
* **Commit Message:** `feat(features): build core bowling economy, wicket rate, and spell metrics`
* **memory.md Update Requirement:** Document computed bowling feature list and column schema.
* **Exit Criteria:** `pytest tests/test_bowling_features.py` passes 100%.

### 4.3 Consistency Features

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Compute percentile-based outcome distributions, floor/ceiling metrics, and transparent consistency badges per PRD §5.
* **Inputs:** `data/processed/fact_deliveries.parquet`.
* **Work:** Implement `src/features/consistency.py`. Calculate player score/spell percentiles (P10, P25, P50, P75, P90), median score, failure rate (scores < 10 runs), high-impact rate (scores > 45 or 3+ wicket spells), and derive rule-based consistency badges ("High Floor", "Boom-or-Bust", "Elite").
* **Deliverables:** `data/features/consistency_features.parquet`, unit tests in `tests/test_consistency.py`.
* **Validation Checks:** Confirm P50 equals median; check that consistency badge assignment logic covers 100% of qualified players.
* **Common Failure Modes:** Black-box label generation without traceable distribution thresholds.
* **Commit Message:** `feat(features): engineer percentile consistency metrics and badge derivation`
* **memory.md Update Requirement:** Log consistency metric formulas and badge mapping definitions.
* **Exit Criteria:** Consistency feature dataset generated with passing unit tests.

### 4.4 Phase Features

> **Scope status (v1.1):** SCOPED DOWN — basic powerplay/middle/death split only, not full granularity.

* **Objective:** Compute phase-specific (Powerplay overs 1–6, Middle overs 7–15, Death overs 16–20) performance splits for batters and bowlers.
* **Inputs:** `data/processed/fact_deliveries.parquet`.
* **Work:** Build `src/features/phase.py`. Aggregate runs, wickets, balls, strike rate, economy rate, dot %, and boundary % segmented explicitly by match phase for every player.
* **Deliverables:** `data/features/phase_features.parquet`, unit tests in `tests/test_phase_features.py`.
* **Validation Checks:** Assert sum of phase runs equals total season runs for every player; check over boundaries (e.g. over 5.6 is PP, over 6.0 is Middle).
* **Common Failure Modes:** Off-by-one errors in over classification indexing (0-indexed vs 1-indexed over numbers).
* **Commit Message:** `feat(features): calculate phase-wise performance splits across PP, Middle, and Death`
* **memory.md Update Requirement:** Record phase split feature schema.
* **Exit Criteria:** Phase features generated and validated against match totals.

### 4.5 Matchup Features

> **Scope status (v1.1):** DESCOPED — too time-intensive for this timeline relative to what it adds to a shortlist.

* **Objective:** Build fine-grained matchup interaction features (vs Pace, vs Spin, vs LHB, vs RHB, vs Bowling sub-types) subject to sample limits.
* **Inputs:** `data/processed/fact_deliveries.parquet`.
* **Work:** Build `src/features/matchups.py`. Compute batter strike rate/average/dismissal rate against pace vs spin and bowling sub-types (Left-arm pace, Wrist spin, Off spin); compute bowler stats against LHB vs RHB. Enforce minimum sample threshold (e.g., minimum 30 deliveries) before reporting.
* **Deliverables:** `data/features/matchup_features.parquet`, unit tests in `tests/test_matchup_features.py`.
* **Validation Checks:** Assert metrics for matchups below minimum sample threshold are assigned `null` / flagged low-confidence per PRD §4.
* **Common Failure Modes:** Presenting matchup stats based on tiny ball samples (e.g., 4 balls faced).
* **Commit Message:** `feat(features): build head-to-head matchup metrics with sample threshold enforcement`
* **memory.md Update Requirement:** Document matchup feature definitions and sample cutoff thresholds.
* **Exit Criteria:** Matchup dataset exported with low-sample records flagged or masked.

### 4.6 Venue Features

> **Scope status (v1.1):** DESCOPED — depends on descoped 2.5/3.2 venue depth.

* **Objective:** Compute descriptive venue-level historical baseline statistics.
* **Inputs:** `data/processed/fact_deliveries.parquet`, `data/processed/dim_venues.parquet`.
* **Work:** Implement `src/features/venues.py`. Aggregate venue historical average run rate, boundary rate, phase scoring profile, pace vs spin wicket split, and chasing win percentage.
* **Deliverables:** `data/features/venue_features.parquet`, unit tests in `tests/test_venue_features.py`.
* **Validation Checks:** Verify venue feature values fall within realistic cricket bounds ($6.0 \le \text{run rate} \le 11.0$).
* **Common Failure Modes:** Merging match-specific pitch performance into ground-level static venue features.
* **Commit Message:** `feat(features): calculate descriptive historical venue profile metrics`
* **memory.md Update Requirement:** Record venue feature fields.
* **Exit Criteria:** Venue feature pipeline runs cleanly and outputs Parquet artifact.

### 4.7 Pitch/Environment Classification & Archetype Clustering

> **Scope status (v1.1):** DESCOPED.

* **Objective:** Empirical, data-driven clustering of match pitch environments per PRD §6.
* **Inputs:** `data/processed/fact_deliveries.parquet`, `data/processed/fact_matches.parquet`.
* **Work:** Implement `src/analytics/pitch_clustering.py`. Build feature matrix per match (1st innings run rate, boundary %, spin economy vs pace economy, phase 1-3 scoring gradient). Apply k-means / hierarchical clustering to classify match pitches into archetypes ("High-Scoring", "Spin-Friendly", "Pace/Movement", "Two-Paced/Tricky"). Assign cluster confidence score; tag unclassified/low-sample matches as "Unclassified".
* **Deliverables:** `data/features/pitch_archetypes.parquet`, clustering methodology documentation in `docs/pitch_clustering.md`.
* **Validation Checks:** Verify zero external pitch commentary used; confirm confidence metrics attached to every assignment.
* **Common Failure Modes:** Hardcoding subjective pitch labels; forcing a cluster on matches with insufficient ball data.
* **Commit Message:** `feat(analytics): build empirical pitch archetype clustering model and confidence scoring`
* **memory.md Update Requirement:** Record cluster centroids, archetype definitions, and classification counts.
* **Exit Criteria:** Pitch archetype dataset exported with explicit confidence scores.

### 4.8 Pressure & Situational Context Features

> **Scope status (v1.1):** DESCOPED — nice-to-have, not decision-critical.

* **Objective:** Engineer situational features capturing performance under high pressure (high required run rate, close finishes, collapsed top-order).
* **Inputs:** `data/processed/fact_deliveries.parquet`.
* **Work:** Build `src/features/pressure.py`. Define pressure contexts (Required Run Rate > 10.0 in chase, team score < 30/3 in PP, defending < 15 runs in death overs). Compute player strike rate, economy, and survival rates under defined pressure flags.
* **Deliverables:** `data/features/pressure_features.parquet`, unit tests in `tests/test_pressure_features.py`.
* **Validation Checks:** Assert pressure context conditions accurately trigger on historical match situations.
* **Common Failure Modes:** Over-defining situational rules leading to zero qualified balls for most players.
* **Commit Message:** `feat(features): engineer situational pressure metrics and leverage index splits`
* **memory.md Update Requirement:** Document pressure scenario definitions.
* **Exit Criteria:** Pressure feature matrix exported with unit tests passing.

### 4.9 League-Strength Adjustment Features

> **Scope status (v1.1):** IN SCOPE — needed so BBL/CPL/SA20/domestic stats are comparable to IPL at all.

* **Objective:** Compute empirical competition difficulty adjustment factors to enable cross-league comparability per PRD §7.3.
* **Inputs:** `data/features/batting_features.parquet`, `data/features/bowling_features.parquet`.
* **Work:** Implement `src/analytics/league_adjustment.py`. Compute relative competition strength indexing using crossover player performance differentials between IPL and external leagues (BBL, CPL, SA20, SMAT, etc.). Calculate league difficulty multiplier $M_{\text{league}}$.
* **Deliverables:** `configs/league_strength_factors.json`, `data/features/league_adjusted_features.parquet`.
* **Validation Checks:** Verify IPL baseline factor equals 1.0; check that lower-tier leagues have appropriate adjustment factors ($< 1.0$).
* **Common Failure Modes:** Manually setting opinionated league ratings instead of deriving from crossover player data.
* **Commit Message:** `feat(analytics): build empirical league-strength adjustment factors and adjusted feature layer`
* **memory.md Update Requirement:** Record calculated league adjustment factors per competition.
* **Exit Criteria:** Adjusted feature tables produced with transparent adjustment factor documentation.

### 4.10 Domestic-to-Franchise Translation Features

> **Scope status (v1.1):** IN SCOPE — core to identifying strong uncapped/domestic targets, likely RCB's real gap area.

* **Objective:** Engineer specific translation features for domestic uncapped entrants transitioning to IPL.
* **Inputs:** `data/features/league_adjusted_features.parquet`.
* **Work:** Build `src/features/domestic_translation.py`. Calculate domestic performance percentiles, age trajectory factors, domain dominance ratios (SMAT performance vs domestic baseline), and transition variance flags for domestic players without prior IPL experience.
* **Deliverables:** `data/features/domestic_translation_features.parquet`, unit tests in `tests/test_domestic_translation.py`.
* **Validation Checks:** Validate that feature set contains zero lookahead IPL data for uncapped candidates.
* **Common Failure Modes:** Mixing IPL match features into the domestic translation feature vector.
* **Commit Message:** `feat(features): engineer domestic-to-franchise translation feature matrix`
* **memory.md Update Requirement:** Document domestic feature mapping rules.
* **Exit Criteria:** Domestic feature pipeline completes with zero data leakage.

---

## PHASE 5 — RCB Squad Diagnosis & Gap Analysis

### 5.1 Squad Inventory & Roster State Assessment

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Ingest and structure RCB's pre-auction retained squad, released list, remaining purse, and overseas slot counts.
* **Inputs:** Official IPL 2026 pre-auction retention releases, `data/processed/dim_players.parquet`.
* **Work:** Build `configs/rcb_squad_state.json` detailing retained players, contract prices, remaining purse cap, total open slots, and open overseas slots. Write script `src/analytics/squad_inventory.py` to compile current roster table.
* **Deliverables:** `data/processed/rcb_squad_inventory.parquet`, `configs/rcb_squad_state.json`.
* **Validation Checks:** Assert sum of retained prices + remaining purse = total team purse cap (e.g. ₹120 Crore); check slot counts sum to 25 max.
* **Common Failure Modes:** Inaccurate retained price figures; incorrect overseas slot tracking.
* **Commit Message:** `feat(squad): establish RCB retained roster state, purse balance, and slot limits`
* **memory.md Update Requirement:** Log current RCB retained players, remaining purse, and open slot counts.
* **Exit Criteria:** RCB current squad state verified and saved in `configs/`.

### 5.2 Role Classification & Skill Tagging

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Map retained players and entire player pool into explicit role taxonomy per PRD §8.
* **Inputs:** `data/processed/dim_players.parquet`, `data/features/*.parquet`.
* **Work:** Build `src/analytics/role_classification.py`. Classify every player into standard primary and secondary roles: Top-Order Batter, Middle-Order Anchor, Death Finisher, Wicketkeeper-Batter, Pace All-Rounder, Spin All-Rounder, Express Pace, Powerplay Bowler, Death Specialist Bowler, Mystery/Wrist Spinner.
* **Deliverables:** `data/processed/player_roles.parquet`, taxonomy configuration in `configs/role_taxonomy.json`.
* **Validation Checks:** Verify every player receives exactly one primary role and zero or more secondary skills.
* **Common Failure Modes:** Ambiguous role boundaries leading to unclassified players.
* **Commit Message:** `feat(squad): build role classification taxonomy and player skill assignment`
* **memory.md Update Requirement:** Record role distribution across entire player database.
* **Exit Criteria:** 100% of candidate players assigned structured role tags.

### 5.3 Existing Strengths Assessment

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Quantify the aggregated performance metrics of RCB's retained core to isolate existing strengths.
* **Inputs:** `data/processed/rcb_squad_inventory.parquet`, `data/features/*.parquet`.
* **Work:** Implement `src/analytics/squad_strengths.py`. Calculate retained squad's expected run contribution, phase-wise scoring rates, and bowling overs coverage based on prior season features.
* **Deliverables:** `reports/rcb_squad_strengths_analysis.json`.
* **Validation Checks:** Cross-check retained player metrics against feature tables to ensure calculation consistency.
* **Common Failure Modes:** Assuming retained players will bowl overs they haven't historically bowled.
* **Commit Message:** `feat(squad): evaluate retained squad strengths and phase coverage`
* **memory.md Update Requirement:** Document identified core strengths of retained squad.
* **Exit Criteria:** Squad strength report generated in `reports/`.

### 5.4 Squad Weaknesses & Critical Gap Identification

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Identify explicit tactical gaps in RCB's squad by comparing retained coverage against winning T20 benchmarks.
* **Inputs:** `reports/rcb_squad_strengths_analysis.json`, `configs/role_taxonomy.json`.
* **Work:** Implement `src/analytics/squad_gaps.py`. Identify missing overs by phase (e.g., lack of domestic death overs bowling), missing batting profile gaps (e.g., spin-hitting middle order batter), and keeper availability gaps.
* **Deliverables:** `reports/rcb_squad_gaps_summary.json`.
* **Validation Checks:** Ensure every identified gap explicitly states required role, phase, and minimum volume.
* **Common Failure Modes:** Generic claims ("needs better bowling") without phase or role specificity.
* **Commit Message:** `feat(squad): diagnose critical squad gaps by phase, role, and skill set`
* **memory.md Update Requirement:** Record prioritized list of RCB squad gaps.
* **Exit Criteria:** Squad gap diagnostic report produced and saved.

### 5.5 Required Role Specifications & Target Profiles

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Convert identified squad gaps into explicit mathematical target profile criteria for candidate searching.
* **Inputs:** `reports/rcb_squad_gaps_summary.json`.
* **Work:** Build `src/analytics/role_profiles.py`. Define quantitative target criteria for each gap (e.g., Gap 1: Death Bowler -> Minimum 30% death overs bowled, Death Economy < 9.5, Death Wicket Rate > 0.05).
* **Deliverables:** `configs/target_role_profiles.json`.
* **Validation Checks:** Verify target profile thresholds align with upper-quartile league feature distributions.
* **Common Failure Modes:** Unrealistic multi-skill target specifications that zero players satisfy.
* **Commit Message:** `feat(squad): specify quantitative target profiles for identified squad gaps`
* **memory.md Update Requirement:** Document target role profile specifications.
* **Exit Criteria:** Target profile criteria documented in `configs/`.

### 5.6 Budget & Roster Slot Constraint Definition

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Define formal mathematical constraint equations for auction purse, overseas caps, and slot minimums.
* **Inputs:** `configs/rcb_squad_state.json`.
* **Work:** Build `src/optimization/constraints.py`. Construct linear constraint matrices for purse ($\sum \text{price}_i \le \text{Purse}_{\text{rem}}$), total roster ($18 \le N_{\text{total}} \le 25$), and overseas count ($N_{\text{overseas}} \le 8$).
* **Deliverables:** `src/optimization/constraints.py`, unit tests in `tests/test_constraints.py`.
* **Validation Checks:** Test constraint validator with mock valid and invalid squad combinations.
* **Common Failure Modes:** Forgetting minimum squad size constraints (18 players).
* **Commit Message:** `feat(optimization): build formal purse, roster, and overseas slot constraint rules`
* **memory.md Update Requirement:** Record optimization constraint equations.
* **Exit Criteria:** Constraint validation module passes all unit tests.

### 5.7 Candidate Search Universe Generation

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Filter entire global player database into the broad candidate search universe for evaluation.
* **Inputs:** `data/processed/dim_players.parquet`, `configs/target_role_profiles.json`.
* **Work:** Build `src/analytics/candidate_universe.py`. Extract all players registered/available for auction who match at least one target role profile.
* **Deliverables:** `data/processed/candidate_universe_broad.parquet`.
* **Validation Checks:** Confirm broad search universe contains 200+ candidates before filtering; check zero retained players included.
* **Common Failure Modes:** Accidental exclusion of uncapped domestic players due to overly strict initial filters.
* **Commit Message:** `feat(squad): generate broad candidate search universe from available auction pool`
* **memory.md Update Requirement:** Record broad candidate pool count.
* **Exit Criteria:** Broad candidate dataset generated in `data/processed/`.

---

## PHASE 6 — Candidate Filtering & Funnel Pipeline

### 6.1 Universe Definition & Minimum Sample Filtering

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Apply Stage 1 funnel filtering based strictly on minimum sample thresholds.
* **Inputs:** `data/processed/candidate_universe_broad.parquet`, `data/features/*.parquet`.
* **Work:** Implement `src/analytics/funnel_sample.py`. Filter candidate pool against minimum sample cutoffs (e.g., minimum 100 batting balls or 60 bowling balls in recent window). Flag emerging uncapped players meeting domestic sample limits.
* **Deliverables:** `data/interim/funnel_stage1_sample.parquet`, step log in `reports/funnel_audit.json`.
* **Validation Checks:** Verify candidates dropped are strictly due to sample thresholds; record count of dropped players.
* **Common Failure Modes:** Dropping top domestic prospects who lack IPL volume but clear domestic volume cutoffs.
* **Commit Message:** `feat(funnel): execute Stage 1 sample size filtering with domestic candidate safeguards`
* **memory.md Update Requirement:** Log Stage 1 candidate reduction count.
* **Exit Criteria:** Stage 1 filtered dataset generated with step log.

### 6.2 Performance Threshold & Role Alignment Filtering

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Apply Stage 2 funnel filtering based on league-adjusted baseline performance and gap alignment.
* **Inputs:** `data/interim/funnel_stage1_sample.parquet`, `data/features/league_adjusted_features.parquet`.
* **Work:** Implement `src/analytics/funnel_performance.py`. Filter candidates whose league-adjusted performance falls below median for target role profile requirements.
* **Deliverables:** `data/interim/funnel_stage2_performance.parquet`, update `reports/funnel_audit.json`.
* **Validation Checks:** Confirm performance metrics used are league-adjusted, not raw stats.
* **Common Failure Modes:** Evaluating domestic candidates against raw IPL performance cutoffs without adjustment.
* **Commit Message:** `feat(funnel): execute Stage 2 performance threshold and role alignment filter`
* **memory.md Update Requirement:** Log Stage 2 candidate count.
* **Exit Criteria:** Stage 2 funnel output saved.

### 6.3 Consistency & Floor/Ceiling Filtering

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Apply Stage 3 funnel filtering removing high-variance "boom-or-bust" candidates where squad gap demands floor reliability.
* **Inputs:** `data/interim/funnel_stage2_performance.parquet`, `data/features/consistency_features.parquet`.
* **Work:** Implement `src/analytics/funnel_consistency.py`. Evaluate candidate percentile distributions; filter candidates with high failure rates unless applying for high-ceiling lower-order roles.
* **Deliverables:** `data/interim/funnel_stage3_consistency.parquet`, update `reports/funnel_audit.json`.
* **Validation Checks:** Verify consistency badge filtering matches role requirements (e.g., top-order needs high floor).
* **Common Failure Modes:** Uniformly penalizing high-ceiling death finishers for natural high variance.
* **Commit Message:** `feat(funnel): execute Stage 3 consistency and outcome variance filtering`
* **memory.md Update Requirement:** Log Stage 3 candidate count.
* **Exit Criteria:** Stage 3 funnel output saved.

### 6.4 Pitch Adaptability & Matchup Filtering

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Apply Stage 4 funnel filtering testing candidate performance across pitch archetypes and critical matchups.
* **Inputs:** `data/interim/funnel_stage3_consistency.parquet`, `data/features/pitch_archetypes.parquet`, `data/features/matchup_features.parquet`.
* **Work:** Implement `src/analytics/funnel_adaptability.py`. Assess candidate performance on M. Chinnaswamy home archetype (high scoring/boundary ground) and spin/pace matchup vulnerabilities. Filter candidates with critical unmitigated weaknesses.
* **Deliverables:** `data/interim/funnel_stage4_adaptability.parquet`, update `reports/funnel_audit.json`.
* **Validation Checks:** Verify Chinnaswamy specific suitability metrics applied correctly.
* **Common Failure Modes:** Disqualifying players for a matchup weakness that is easily sheltered by batting order position.
* **Commit Message:** `feat(funnel): execute Stage 4 pitch adaptability and matchup vulnerability filtering`
* **memory.md Update Requirement:** Log Stage 4 candidate count.
* **Exit Criteria:** Stage 4 funnel output saved.

### 6.5 League Translation & Availability Filtering (Final Shortlist ~30–40 Candidates)

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Apply final funnel stage incorporating domestic translation confidence, injury/availability records, and producing target ~30–40 candidate shortlist per PRD §1.4.
* **Inputs:** `data/interim/funnel_stage4_adaptability.parquet`, `data/features/domestic_translation_features.parquet`.
* **Work:** Implement `src/analytics/funnel_final.py`. Incorporate national availability/NOC status and domestic translation confidence scores. Produce final data-driven shortlist. Do NOT artificially force exactly 40 players; let thresholds dictate natural count ($30 \le N \le 40$).
* **Deliverables:** `data/processed/candidate_shortlist_30_40.parquet`, complete audit trail in `reports/funnel_audit.json`.
* **Validation Checks:** Assert final candidate count is between 30 and 40; verify multi-role representation across all identified gaps.
* **Common Failure Modes:** Hardcoding candidate selection to hit 40 players; omitting availability checks.
* **Commit Message:** `feat(funnel): finalize data-driven 30-40 candidate shortlist with availability and translation filtering`
* **memory.md Update Requirement:** Document final candidate shortlist count, role breakdown, and funnel drop counts per stage.
* **Exit Criteria:** Final candidate shortlist table generated and fully documented.

---

## PHASE 7 — ML Modelling & Valuation

### 7.1 Statistical Baseline Models

> **Scope status (v1.1):** IN SCOPE

* **Objective:** Establish simple statistical baseline models for auction price and performance before training ML models per PRD §9.1.
* **Inputs:** `data/processed/candidate_shortlist_30_40.parquet`, `data/raw/auction/ipl_auction_history.csv`.
* **Work:** Implement `src/models/baselines.py`. Build simple linear/percentile baseline models: (1) Price baseline = historical role median price, (2) Performance baseline = raw domestic percentile. Calculate baseline MAE / RMSE.
* **Deliverables:** `src/models/baselines.py`, `reports/baseline_metrics.json`.
* **Validation Checks:** Verify baseline metrics provide explicit benchmark scores that ML models must beat.
* **Common Failure Modes:** Comparing ML models against unrecorded or moving baseline benchmarks.
* **Commit Message:** `feat(models): establish simple statistical baselines for auction price and performance`
* **memory.md Update Requirement:** Record baseline MAE and performance metrics.
* **Exit Criteria:** Baseline evaluation script runs and writes metrics to `reports/`.

### 7.2 Auction Price Model (Model A1 — Expected Market Price)

> **Scope status (v1.1):** IN SCOPE — needed to set a realistic expected price per target.

* **Objective:** Train time-validated model predicting expected auction market price based on historical price patterns per `architecture.md` §8.
* **Inputs:** Historical auction datasets, historical player feature tables (strictly point-in-time correct).
* **Work:** Implement `src/models/train_price_model.py`. Train XGBoost / Ridge regression model predicting expected auction market price ($Y_{\text{price}}$). Feature set: historical price, role, age, international experience, recent season metrics. Enforce strict temporal validation (train on pre-2024 auctions, validate on 2024-2025).
* **Deliverables:** Serialized model `models/model_a1_price.joblib`, validation metrics in `reports/model_a1_metrics.json`.
* **Validation Checks:** Verify temporal split (no future auction data in training); assert model beats baseline price MAE.
* **Common Failure Modes:** Data leakage: including post-auction performance or actual sale price in feature vector.
* **Commit Message:** `feat(models): build and temporally validate Model A1 expected auction market price model`
* **memory.md Update Requirement:** Log Model A1 hyperparameter settings, temporal MAE, and baseline comparison.
* **Exit Criteria:** Model A1 artifact saved and beats baseline MAE.

### 7.3 Fair-Value Model (Model A2 — Objective Value)

> **Scope status (v1.1):** SCOPED DOWN — a simpler statistical/heuristic fair-value baseline is enough; doesn't need to be a fully separate ML model.

* **Objective:** Build objective performance-and-scarcity-grounded fair value estimation model distinct from market price per PRD §8.2.
* **Inputs:** `data/features/league_adjusted_features.parquet`, `configs/role_taxonomy.json`.
* **Work:** Implement `src/models/train_fair_value.py`. Construct fair value model ($Y_{\text{fair\_value}}$) deriving objective value from league-adjusted run/wicket impact, phase importance weighting, and role scarcity index ($S_{\text{role}}$). Keep separate from price prediction per `architecture.md` §8.
* **Deliverables:** Serialized model `models/model_a2_fair_value.joblib`, metrics in `reports/model_a2_metrics.json`.
* **Validation Checks:** Confirm model outputs positive valuation numbers; check that scarce roles receive appropriate value premiums.
* **Common Failure Modes:** Merging market sentiment or price history into objective fair value calculation.
* **Commit Message:** `feat(models): build Model A2 objective fair-value model based on impact and scarcity`
* **memory.md Update Requirement:** Record Fair-Value model logic and scarcity index multipliers.
* **Exit Criteria:** Model A2 serialized artifact generated and metrics logged.

### 7.4 Domestic-to-Franchise Translation Model (Model B)

> **Scope status (v1.1):** IN SCOPE — same reason as 4.10/3.5.

* **Objective:** Train transition model predicting IPL performance percentiles for domestic entrants based on domestic track records.
* **Inputs:** Historical crossover player cohort features (domestic features vs subsequent IPL performance).
* **Work:** Implement `src/models/train_translation_model.py`. Build translation model (Model B) using crossover player training set. Apply temporal/cohort validation. Predict IPL performance percentile ($\hat{P}_{\text{IPL}}$) for domestic candidate shortlist.
* **Deliverables:** Serialized model `models/model_b_translation.joblib`, validation metrics in `reports/model_b_metrics.json`.
* **Validation Checks:** Evaluate model on holdout domestic cohort; document known survivorship bias limitation per PRD §9.3.
* **Common Failure Modes:** Including IPL stats in training features; reporting unvalidated predictions.
* **Commit Message:** `feat(models): build and validate Model B domestic-to-franchise performance translation model`
* **memory.md Update Requirement:** Log Model B validation metrics and survivorship bias disclosures.
* **Exit Criteria:** Model B trained, validated, and serialized under `models/`.

### 7.5 Player Similarity & Clustering Model (Model C — Optional/Unsupervised)

> **Scope status (v1.1):** DESCOPED — the roadmap itself marks this optional.

* **Objective:** Implement unsupervised nearest-neighbor clustering to identify strategic backup alternatives for candidate targets per `architecture.md` §8.
* **Inputs:** `data/features/league_adjusted_features.parquet` (role and style features only; price excluded).
* **Work:** Implement `src/models/train_similarity.py`. Apply k-means / cosine similarity on normalized feature vectors to identify top-3 nearest-neighbor alternative players for every candidate.
* **Deliverables:** `models/model_c_similarity.joblib`, `data/features/player_similarity_matrix.parquet`.
* **Validation Checks:** Verify price and value features are excluded from input vector; test nearest-neighbor outputs for qualitative sense check.
* **Common Failure Modes:** Including auction price in similarity calculation (causes price similarity instead of skill similarity).
* **Commit Message:** `feat(models): build Model C unsupervised player similarity and backup retrieval matrix`
* **memory.md Update Requirement:** Record similarity model feature inputs and cluster stability metrics.
* **Exit Criteria:** Similarity matrix generated and stored in `data/features/`.

### 7.6 Model Validation, Temporal Evaluation & Leakage Audit

> **Scope status (v1.1):** SCOPED DOWN — a basic temporal train/test holdout, not the full leakage-audit ceremony.

* **Objective:** Conduct rigorous end-to-end model validation, temporal integrity audit, and target leakage verification across Models A, B, and C.
* **Inputs:** `models/*.joblib`, `src/models/*.py`.
* **Work:** Implement `src/models/validate_models.py`. Execute temporal validation routines, feature importance checks, and explicit data leakage audits (verifying zero future feature timestamps relative to prediction dates).
* **Deliverables:** `reports/ml_validation_and_leakage_audit.json`.
* **Validation Checks:** Confirm 0 temporal leakage violations across all training datasets.
* **Common Failure Modes:** Random K-fold CV on time-series/auction data masking lookahead leakage.
* **Commit Message:** `test(models): execute temporal validation suite and feature leakage audit`
* **memory.md Update Requirement:** Record complete ML validation pass confirmation.
* **Exit Criteria:** Comprehensive ML audit report passes with zero critical warnings.

### 7.7 Explainability Framework (SHAP / Feature Attribution)

> **Scope status (v1.1):** DESCOPED — SHAP is valuable polish, not required to justify a shortlist in a written document.

* **Objective:** Generate SHAP feature attributions for every candidate prediction to ensure 100% explainable valuations per PRD §9.2 & §12.
* **Inputs:** `models/*.joblib`, `data/processed/candidate_shortlist_30_40.parquet`.
* **Work:** Implement `src/models/explainability.py`. Calculate SHAP values for Model A1, A2, and B predictions for all shortlisted candidates. Export top positive/negative feature drivers per player prediction.
* **Deliverables:** `data/features/model_explainability_shap.parquet`, visual feature summary plots in `reports/shap_plots/`.
* **Validation Checks:** Assert sum of SHAP base value + feature attributions equals model prediction output ($f(x) = \phi_0 + \sum \phi_i$).
* **Common Failure Modes:** Displaying raw SHAP numbers without human-readable feature name translation.
* **Commit Message:** `feat(models): build SHAP feature attribution and prediction explainability pipeline`
* **memory.md Update Requirement:** Record explainability framework integration and sample driver outputs.
* **Exit Criteria:** SHAP attribution dataset exported for all candidate shortlist predictions.

---

## PHASE 8 — Auction Optimization & Scenario Planning

### 8.1 Budget & Purse Allocation Model

> **Scope status (v1.1):** SCOPED DOWN — simple purse-remaining arithmetic, not a standalone model.

* **Objective:** Model purse allocation strategies and target expenditure bands across required squad roles.
* **Inputs:** `configs/rcb_squad_state.json`, `data/processed/candidate_shortlist_30_40.parquet`.
* **Work:** Implement `src/optimization/budget_model.py`. Calculate target purse distribution ranges per gap role (e.g., Tier 1 Marquee Target: 25–35% purse, Tier 2 Core Target: 12–18%, Tier 3 Depth: 3–7%).
* **Deliverables:** `configs/purse_allocation_budget.json`, `src/optimization/budget_model.py`.
* **Validation Checks:** Assert sum of role purse allocations equals 100% of remaining purse.
* **Common Failure Modes:** Allocating 100% of purse to 2 players, leaving insufficient funds for minimum squad size (18 players).
* **Commit Message:** `feat(optimization): build purse allocation model and role spend distribution bands`
* **memory.md Update Requirement:** Log purse allocation strategy limits.
* **Exit Criteria:** Purse allocation configuration saved and validated.

### 8.2 Squad Constraint Solver Setup

> **Scope status (v1.1):** DESCOPED — no OR-Tools solver for this timeline.

* **Objective:** Configure OR-Tools constraint solver engine for squad selection under multi-variable constraints per `architecture.md` §9.
* **Inputs:** `src/optimization/constraints.py`, candidate shortlist model predictions.
* **Work:** Implement `src/optimization/solver.py`. Set up Integer Linear Programming (ILP) formulation using Google OR-Tools: Maximize total expected squad performance subject to purse, roster size, overseas limit, and gap coverage constraints.
* **Deliverables:** `src/optimization/solver.py`, unit tests in `tests/test_solver.py`.
* **Validation Checks:** Verify solver finds optimal solution on synthetic benchmark test cases within 2 seconds.
* **Common Failure Modes:** Infeasible constraint specification causing solver deadlocks.
* **Commit Message:** `feat(optimization): build OR-Tools integer programming solver for constrained squad optimization`
* **memory.md Update Requirement:** Record solver optimization objective function and constraint setup.
* **Exit Criteria:** Solver passes all unit tests and solves baseline mock scenarios.

### 8.3 Maximum Recommended Bid Logic

> **Scope status (v1.1):** IN SCOPE — rule-based bid-ceiling logic (fair value + scarcity/role-need adjustment), computed directly rather than via a solver.

* **Objective:** Calculate player-specific Maximum Rational Bid ceilings distinct from objective Fair Value per PRD §8.2.
* **Inputs:** Model A2 Fair Value, Model A1 Expected Market Price, role scarcity indices, remaining purse.
* **Work:** Implement `src/optimization/max_bid.py`. Compute Maximum Recommended Bid: $\text{MaxBid}_i = \text{FairValue}_i \times (1 + \text{ScarcityAdjustment}) \times \text{SquadFitMultiplier}$, bounded strictly by purse constraints.
* **Deliverables:** `data/features/candidate_max_bids.parquet`, unit tests in `tests/test_max_bid.py`.
* **Validation Checks:** Assert Fair Value, Expected Market Price, and Max Recommended Bid are stored as separate fields per PRD §8.2.
* **Common Failure Modes:** Merging Max Bid and Fair Value into one undifferentiated price metric.
* **Commit Message:** `feat(optimization): calculate distinct maximum recommended bid ceilings with scarcity adjustments`
* **memory.md Update Requirement:** Document Max Bid formula and multi-tier boundary rules.
* **Exit Criteria:** Max bid calculations exported and validated with passing tests.

### 8.4 Player Combination Optimizer

> **Scope status (v1.1):** DESCOPED.

* **Objective:** Run OR-Tools optimization engine to generate globally optimal squad combinations from candidate shortlist.
* **Inputs:** `src/optimization/solver.py`, candidate predictions, max bids.
* **Work:** Implement `scripts/run_squad_optimizer.py`. Execute solver across candidate universe to identify primary recommended 18–25 player target squad combination maximizing total expected performance.
* **Deliverables:** `data/processed/optimal_squad_primary.parquet`, optimization summary report in `reports/optimization_primary.json`.
* **Validation Checks:** Confirm optimal squad strictly satisfies purse cap, overseas cap ($\le 8$), and squad size ($\ge 18$).
* **Common Failure Modes:** Over-optimizing for raw stats while violating overseas playing XI constraints.
* **Commit Message:** `feat(optimization): execute primary squad combination optimization via OR-Tools`
* **memory.md Update Requirement:** Log optimal squad recommendation summary, total projected spend, and role coverage.
* **Exit Criteria:** Primary optimal squad generated with zero constraint violations.

### 8.5 Bargain Scenario Generator

> **Scope status (v1.1):** SCOPED DOWN — flag undervalued players as a simple A1-vs-A2 gap, not a generated scenario set.

* **Objective:** Optimize alternative squad scenario prioritizing high-value bargain targets (Fair Value >> Expected Price) to preserve purse.
* **Inputs:** `src/optimization/solver.py`, candidate value gaps.
* **Work:** Implement `src/optimization/scenarios.py` (Scenario A - Bargain Priority). Re-weight optimization objective to maximize total Value Gap ($\text{Fair Value} - \text{Expected Price}$).
* **Deliverables:** `data/exports/scenario_bargain_squad.parquet`.
* **Validation Checks:** Verify resulting squad total spend is significantly below purse cap while maintaining role coverage.
* **Common Failure Modes:** Selecting cheap low-quality players who fail minimum role performance thresholds.
* **Commit Message:** `feat(optimization): generate Scenario A bargain-focused squad strategy`
* **memory.md Update Requirement:** Record Bargain scenario composition and projected purse savings.
* **Exit Criteria:** Bargain scenario output exported to `data/exports/`.

### 8.6 Star-Player / Anchor Strategy Generator

> **Scope status (v1.1):** DESCOPED.

* **Objective:** Optimize alternative squad scenario prioritizing top-tier marquee anchors (allocating 50%+ purse to 2 marquee targets).
* **Inputs:** `src/optimization/solver.py`.
* **Work:** Modify scenario solver parameters for Scenario B (Marquee Anchor Strategy). Enforce constraint forcing selection of at least 2 Tier-1 marquee targets; optimize remaining purse for depth.
* **Deliverables:** `data/exports/scenario_marquee_squad.parquet`.
* **Validation Checks:** Confirm remaining budget after marquee acquisitions successfully fills all mandatory squad slots.
* **Common Failure Modes:** Marquee targets exhaust purse leaving insufficient funds to reach 18 players at base prices.
* **Commit Message:** `feat(optimization): generate Scenario B marquee anchor squad strategy`
* **memory.md Update Requirement:** Record Marquee scenario composition and risk trade-offs.
* **Exit Criteria:** Marquee scenario output exported to `data/exports/`.

### 8.7 Depth & Balance Scenario Generator

> **Scope status (v1.1):** DESCOPED.

* **Objective:** Optimize alternative squad scenario prioritizing balanced spend distribution across all roles (no single player > 15% purse).
* **Inputs:** `src/optimization/solver.py`.
* **Work:** Modify scenario solver parameters for Scenario C (Balanced Depth Strategy). Add upper-bound constraint capping individual bid at 15% total purse; maximize overall squad depth and floor consistency.
* **Deliverables:** `data/exports/scenario_balanced_squad.parquet`.
* **Validation Checks:** Confirm no single player spend exceeds 15% of purse cap.
* **Common Failure Modes:** Inability to secure high-impact death bowlers within 15% spend cap (handle gracefully via solver exception).
* **Commit Message:** `feat(optimization): generate Scenario C balanced depth squad strategy`
* **memory.md Update Requirement:** Record Balanced scenario composition.
* **Exit Criteria:** Balanced scenario output exported to `data/exports/`.

### 8.8 Multi-Scenario Comparison Framework

> **Scope status (v1.1):** DESCOPED.

* **Objective:** Aggregate primary and alternative optimization scenarios into unified comparative analysis export for Power BI.
* **Inputs:** `data/exports/scenario_*.parquet`.
* **Work:** Build `src/optimization/compare_scenarios.py`. Consolidate primary, bargain, marquee, and balanced scenarios into a single analytical comparison table (`data/exports/optimization_scenarios_comparison.parquet`).
* **Deliverables:** `data/exports/optimization_scenarios_comparison.parquet`.
* **Validation Checks:** Verify schema alignment across all scenario exports; check that scenario IDs uniquely key each run.
* **Common Failure Modes:** Inconsistent column naming across scenario output tables.
* **Commit Message:** `feat(optimization): consolidate multi-scenario optimization outputs into Power BI export layer`
* **memory.md Update Requirement:** Log scenario comparative summary metrics (projected performance vs purse spend).
* **Exit Criteria:** Consolidated scenario comparison Parquet file generated under `data/exports/`.

---

## PHASE 9 — Power BI Dashboard Layer

### 9.1 Data Model & Power Query Data Layer Exports

> **Scope status (v1.1):** DESCOPED — no Power BI dashboard this cycle; see replacement deliverable note above.

* **Objective:** Construct clean, denormalized Power BI export tables in `data/exports/` and build Power BI data model.
* **Inputs:** `data/processed/*.parquet`, `data/features/*.parquet`, `data/exports/*.parquet`.
* **Work:** Implement `scripts/build_powerbi_exports.py`. Create denormalized export tables optimized for Power BI star schema: `fact_candidate_evaluations.parquet`, `dim_players_pbi.parquet`, `dim_venues_pbi.parquet`, `fact_squad_gaps_pbi.parquet`, `fact_scenarios_pbi.parquet`. Load exports into Power BI (`powerbi/rcb_auction_intelligence.pbix`) via Power Query.
* **Deliverables:** `scripts/build_powerbi_exports.py`, `powerbi/rcb_auction_intelligence.pbix` with clean star schema.
* **Validation Checks:** Verify zero complex many-to-many relationships in Power BI data model; check star schema model setup.
* **Common Failure Modes:** Performing statistical transformations inside Power Query/DAX instead of upstream Python scripts.
* **Commit Message:** `feat(powerbi): build denormalized export tables and establish Power BI star schema data model`
* **memory.md Update Requirement:** Record export table schemas and Power BI table relationships.
* **Exit Criteria:** Power BI data model successfully connected and refreshed from `data/exports/`.

### 9.2 Design Theme, Color Palette & Typography

> **Scope status (v1.1):** DESCOPED.

* **Objective:** Create and apply professional, decision-focused visual theme JSON for Power BI per `design.md`.
* **Inputs:** PRD visual guidelines, `design.md`.
* **Work:** Create `powerbi/theme_rcb_intelligence.json` specifying color palette (RCB Red `#D11A2A`, Dark Charcoal `#1E1E1E`, Gold/Amber `#D4AF37`, Neutral Background `#F8F9FA`, Slate Accent `#4A5568`), typography (DIN / Segoe UI), and card container styles. Apply theme to `.pbix`.
* **Deliverables:** `powerbi/theme_rcb_intelligence.json`, styled `.pbix` layout.
* **Validation Checks:** Test visual contrast ratios (WCAG AA compliance) for dark/light text on card backgrounds.
* **Common Failure Modes:** Using overly bright saturated red fills that reduce chart readability.
* **Commit Message:** `style(powerbi): build and apply decision-focused visual theme and color palette`
* **memory.md Update Requirement:** Document theme hex codes and styling standards.
* **Exit Criteria:** Power BI theme JSON imported and active across report template.

### 9.3 Executive Overview Page

> **Scope status (v1.1):** DESCOPED.

* **Objective:** Build Page 1: One-screen executive summary for franchise decision-makers per PRD §11.
* **Inputs:** `powerbi/rcb_auction_intelligence.pbix`, `data/exports/*`.
* **Work:** Design Executive Overview page: Key KPI cards (Remaining Purse, Open Slots, Top Priority Gap, Headline Shortlist Target), Top 3 Squad Gaps summary card, Top Candidate Target shortlist table, and Headline Auction Recommendation banner.
* **Deliverables:** Page 1 completed in `powerbi/rcb_auction_intelligence.pbix`.
* **Validation Checks:** Verify page answers Core Product Question 1 & 14 at a single glance; test cross-filtering on top candidates.
* **Common Failure Modes:** Cluttering page with raw scorecard stats instead of high-level decision KPIs.
* **Commit Message:** `feat(powerbi): build Page 1 Executive Overview summary dashboard`
* **memory.md Update Requirement:** Record Page 1 completion and visual layout structure.
* **Exit Criteria:** Executive Overview page functional and cross-filtering cleanly.

### 9.4 Squad Gap Analysis Page

> **Scope status (v1.1):** DESCOPED.

* **Objective:** Build Page 2: Diagnostic breakdown of RCB's roster weaknesses and phase coverage gaps.
* **Inputs:** `fact_squad_gaps_pbi.parquet`.
* **Work:** Design Squad Gap Analysis page: Phase-wise performance comparison matrix (Retained Core vs IPL Benchmark), Role Coverage Map visual, and prioritized Squad Gap Diagnostic table highlighting required target profiles.
* **Deliverables:** Page 2 completed in `powerbi/rcb_auction_intelligence.pbix`.
* **Validation Checks:** Verify retained squad phase gaps clearly highlight missing death overs bowling and spin-hitting middle order.
* **Common Failure Modes:** Displaying gaps without showing underlying retained player metrics.
* **Commit Message:** `feat(powerbi): build Page 2 Squad Gap Analysis diagnostic page`
* **memory.md Update Requirement:** Record Page 2 layout details.
* **Exit Criteria:** Squad Gap Analysis page completed and verified.

### 9.5 Player Discovery Page

> **Scope status (v1.1):** DESCOPED.

* **Objective:** Build Page 3: Interactive filtering and search visual for the 30–40 candidate shortlist.
* **Inputs:** `fact_candidate_evaluations.parquet`.
* **Work:** Design Player Discovery page: Slicers (Role, Overseas/Indian, Price Band, Gap Fit Score, Consistency Badge), Candidate Matrix table (Player, Role, Age, League Adjusted SR/Econ, Fair Value, Max Bid, Consistency Badge), and candidate detail tooltips.
* **Deliverables:** Page 3 completed in `powerbi/rcb_auction_intelligence.pbix`.
* **Validation Checks:** Confirm slicers filter matrix smoothly; verify candidate count matches shortlist ($30 \le N \le 40$).
* **Common Failure Modes:** Slicers resetting layout unexpectedly; slow table visual rendering.
* **Commit Message:** `feat(powerbi): build Page 3 Player Discovery interactive shortlist filtering page`
* **memory.md Update Requirement:** Record Page 3 slicer logic and visual component layout.
* **Exit Criteria:** Player Discovery page fully interactive with fast response times.

### 9.6 Player Profile Page

> **Scope status (v1.1):** DESCOPED.

* **Objective:** Build Page 4: Deep-dive analytical view for an individual candidate player.
* **Inputs:** Candidate evaluations, consistency distributions, SHAP explainability tables.
* **Work:** Design Player Profile page: Candidate bio card, Consistency Score & Badge display, Scoring/Spell distribution plot, Phase Performance Radar/Bar chart, Matchup breakdown card, Valuation summary (Fair Value vs Expected Price vs Max Bid), and SHAP Valuation Driver chart.
* **Deliverables:** Page 4 completed in `powerbi/rcb_auction_intelligence.pbix`.
* **Validation Checks:** Select multiple candidates via slicer to verify dynamic updating of all profile visuals; check SHAP driver visual alignment.
* **Common Failure Modes:** Static hardcoded text elements breaking when changing player selection.
* **Commit Message:** `feat(powerbi): build Page 4 Player Profile deep-dive evaluation page`
* **memory.md Update Requirement:** Record Page 4 visual setup and SHAP visual integration.
* **Exit Criteria:** Player Profile page dynamic selection fully functional.

### 9.7 Pitch/Venue Intelligence Page

> **Scope status (v1.1):** DESCOPED.

* **Objective:** Build Page 5: Environmental context, ground statistics, and empirical pitch archetype insights.
* **Inputs:** `dim_venues_pbi.parquet`, `pitch_archetypes.parquet`.
* **Work:** Design Pitch/Venue Intelligence page: M. Chinnaswamy home ground analytical summary, Empirical Pitch Archetype distribution breakdown, Venue performance impact matrix, and pitch classification confidence indicators per PRD §6.
* **Deliverables:** Page 5 completed in `powerbi/rcb_auction_intelligence.pbix`.
* **Validation Checks:** Confirm Chinnaswamy Stadium stats accurately show home ground bias; check unclassified pitch tags display clearly.
* **Common Failure Modes:** Displaying pitch labels without showing classification confidence scores.
* **Commit Message:** `feat(powerbi): build Page 5 Pitch and Venue Intelligence context page`
* **memory.md Update Requirement:** Record Page 5 components.
* **Exit Criteria:** Pitch/Venue page built and validated against upstream cluster outputs.

### 9.8 Matchup Intelligence Page

> **Scope status (v1.1):** DESCOPED.

* **Objective:** Build Page 6: Head-to-head batter vs bowler and skill sub-type interaction matrix.
* **Inputs:** `matchup_features.parquet`.
* **Work:** Design Matchup Intelligence page: Pace vs Spin performance comparison matrix, Bowling sub-type vulnerability grid (vs Left-arm pace, Wrist spin, Off spin), Batter vs Bowler type split visuals, and sample size low-confidence warnings.
* **Deliverables:** Page 6 completed in `powerbi/rcb_auction_intelligence.pbix`.
* **Validation Checks:** Verify low-sample matchup combinations explicitly display low-confidence flags.
* **Common Failure Modes:** Showing confident visual bars for matchups based on under 15 balls faced.
* **Commit Message:** `feat(powerbi): build Page 6 Matchup Intelligence head-to-head analysis page`
* **memory.md Update Requirement:** Record Page 6 layout setup.
* **Exit Criteria:** Matchup page operational with sample indicator safeguards.

### 9.9 Auction Value Page

> **Scope status (v1.1):** DESCOPED.

* **Objective:** Build Page 7: Valuation transparency page comparing Fair Value, Market Price, and Value Gaps.
* **Inputs:** Valuation exports, Model A1/A2 outputs.
* **Work:** Design Auction Value page: Valuation Scatter plot (Expected Market Price vs Objective Fair Value), Bargain Candidates list (Fair Value > Price), Overpayment Risk list (Price > Fair Value), Scarcity Premium adjustment breakdown, and Max Recommended Bid limits table.
* **Deliverables:** Page 7 completed in `powerbi/rcb_auction_intelligence.pbix`.
* **Validation Checks:** Confirm Fair Value, Market Price, and Max Bid remain three distinct visual columns/measures per PRD §8.2.
* **Common Failure Modes:** Confusing bargain status with cheap absolute price.
* **Commit Message:** `feat(powerbi): build Page 7 Auction Value transparency and bargain identification page`
* **memory.md Update Requirement:** Record Page 7 layout details.
* **Exit Criteria:** Auction Value page verified against model outputs.

### 9.10 Scenario Simulator / Auction Simulator Page

> **Scope status (v1.1):** DESCOPED.

* **Objective:** Build Page 8: Interactive "what-if" scenario exploration visual per PRD §11 & `architecture.md` §7.
* **Inputs:** `fact_scenarios_pbi.parquet`, `optimization_scenarios_comparison.parquet`.
* **Work:** Design Auction Simulator page: Scenario selector slicer (Primary Optimal, Bargain Priority, Marquee Anchor, Balanced Depth), Dynamic Purse Allocation gauge, Selected Squad Roster table, Projected Squad Role Coverage vs Gap requirements, and scenario comparison view.
* **Deliverables:** Page 8 completed in `powerbi/rcb_auction_intelligence.pbix`.
* **Validation Checks:** Confirm simulator operates over pre-computed optimization scenario exports (no live optimization script execution inside DAX).
* **Common Failure Modes:** Attempting to write complex squad optimization algorithms in DAX.
* **Commit Message:** `feat(powerbi): build Page 8 Scenario Simulator interactive strategy comparison page`
* **memory.md Update Requirement:** Record Page 8 visual setup and scenario switching logic.
* **Exit Criteria:** Scenario Simulator page switching cleanly across pre-computed optimization outputs.

### 9.11 Final Recommendation Page

> **Scope status (v1.1):** DESCOPED.

* **Objective:** Build Page 9: Definitive actionable target list, bid limits, and auction strategy playbook.
* **Inputs:** All optimization and evaluation exports.
* **Work:** Design Final Recommendation page: Target Shortlist by Role with explicit Max Recommended Bid ceilings, Priority Tier bidding order (Must-Have vs Target vs Value Backup), Purse allocation blueprint visual, and Contingency Backup map (Primary Target -> Model C Secondary Alternative).
* **Deliverables:** Page 9 completed in `powerbi/rcb_auction_intelligence.pbix`.
* **Validation Checks:** Verify every primary target lists a valid Model C backup candidate; check that max bid ceilings sum to valid purse distributions.
* **Common Failure Modes:** Omitting backup target mappings for priority bids.
* **Commit Message:** `feat(powerbi): build Page 9 Final Recommendation actionable strategy playbook`
* **memory.md Update Requirement:** Record Page 9 layout details.
* **Exit Criteria:** Final Recommendation page operational and fully cross-linked.

### 9.12 Methodology & Data Quality Page

> **Scope status (v1.1):** DESCOPED.

* **Objective:** Build Page 10: Complete methodology disclosure, data source catalog, sample thresholds, analytical layer attribution, and limitations per PRD §9.2 & §11.
* **Inputs:** `reports/data_quality_report.json`, PRD §9.2 layer map.
* **Work:** Design Methodology page: Analytical Layer Attribution matrix (Descriptive vs Statistical vs ML vs Optimization), Data Source catalog and retrieval dates, Sample Size threshold rules table, Model validation performance metrics summary, and Disclosed Limitations text box (e.g., lack of ball-tracking tracking, survivorship bias in domestic translation).
* **Deliverables:** Page 10 completed in `powerbi/rcb_auction_intelligence.pbix`.
* **Validation Checks:** Verify every dashboard visual/metric traces back to its explicit analytical layer in the attribution table.
* **Common Failure Modes:** Leaving limitations unstated or hiding statistical assumptions.
* **Commit Message:** `feat(powerbi): build Page 10 Methodology, Data Quality, and analytical layer attribution page`
* **memory.md Update Requirement:** Record Page 10 completion and complete analytical layer mapping.
* **Exit Criteria:** Methodology page complete, transparently displaying all analytical layer attributions and limitations.

---

## PHASE 10 — Validation & Quality Assurance

### 10.1 Data QA & Lineage Validation

> **Scope status (v1.1):** SCOPED DOWN — basic checks; some of this is already covered by purse_cap_check.py.

* **Objective:** Re-run end-to-end data audit scripts validating raw-to-export data lineage.
* **Inputs:** Full pipeline datasets across `data/`.
* **Work:** Execute `scripts/run_data_qa.py`. Validate row counts, primary key uniqueness, foreign key integrity, and zero null values in critical export columns.
* **Deliverables:** `reports/final_data_qa_audit.json`.
* **Validation Checks:** 100% pass rate across all automated data quality assertion tests.
* **Common Failure Modes:** Unresolved orphan keys in export tables.
* **Commit Message:** `test(qa): execute final end-to-end data quality and lineage audit`
* **memory.md Update Requirement:** Record complete data QA pass verification.
* **Exit Criteria:** Data QA script passes with 0 failures.

### 10.2 Formula & Metric Audit

> **Scope status (v1.1):** SCOPED DOWN — spot-check the formulas actually feeding the shortlist, not every metric in the system.

* **Objective:** Audit every custom feature formula in Python against manual benchmark calculations.
* **Inputs:** `src/features/*.py`, manual test benchmarks.
* **Work:** Execute `tests/test_formula_audit.py` comparing computed features for 5 benchmark players against independently computed manual Excel/Python calculations (strike rate, boundary dependency, economy variance, phase splits).
* **Deliverables:** Formula audit test suite and pass report in `reports/formula_audit_results.json`.
* **Validation Checks:** Absolute difference between computed features and manual benchmarks $\le 10^{-5}$.
* **Common Failure Modes:** Discrepancies in boundary run calculations during penalty run scenarios.
* **Commit Message:** `test(qa): audit custom feature metric formulas against independent manual benchmarks`
* **memory.md Update Requirement:** Record formula audit pass verification.
* **Exit Criteria:** Formula audit test suite passes with 100% precision match.

### 10.3 ML Model Evaluation & Temporal Audit

> **Scope status (v1.1):** IN SCOPE — a shortlist sent to a coaching staff needs an honestly-evaluated model behind it.

* **Objective:** Final audit of ML model outputs, temporal split enforcement, and SHAP explainability values.
* **Inputs:** `src/models/validate_models.py`, `models/*.joblib`.
* **Work:** Execute ML audit pipeline verifying zero target leakage, temporal holdout validity, and SHAP value mathematical balance for all predictions.
* **Deliverables:** `reports/final_ml_audit_report.json`.
* **Validation Checks:** Confirm model performance on holdout test set matches or exceeds baseline models.
* **Common Failure Modes:** Model overfit on small candidate shortlist (verify training occurred on full player dataset).
* **Commit Message:** `test(qa): execute final machine learning model validation and temporal leakage audit`
* **memory.md Update Requirement:** Record final ML model performance summary.
* **Exit Criteria:** ML audit report clean with 0 leakage warnings.

### 10.4 Dashboard QA & Interactivity Verification

> **Scope status (v1.1):** DESCOPED — no dashboard to test.

* **Objective:** Audit Power BI dashboard pages for interactivity, filter performance, visual formatting, and cross-filtering accuracy.
* **Inputs:** `powerbi/rcb_auction_intelligence.pbix`.
* **Work:** Manual and semi-automated audit of all 10 Power BI pages: test all slicers, verify drill-through actions, inspect visual alignment, test tooltip population, and check report load times (< 3 seconds per page).
* **Deliverables:** `reports/dashboard_qa_checklist.json`.
* **Validation Checks:** All 10 pages pass layout, slicer, theme, and responsiveness checks.
* **Common Failure Modes:** Broken bookmark links; visual cards displaying `Blank()` on specific filter combinations.
* **Commit Message:** `test(qa): complete Power BI dashboard visual, performance, and interactivity audit`
* **memory.md Update Requirement:** Log dashboard QA audit completion.
* **Exit Criteria:** Dashboard QA checklist 100% marked complete.

### 10.5 Edge-Case, Outlier & Boundary Testing

> **Scope status (v1.1):** SCOPED DOWN — check the edge cases likely to actually occur in the candidate pool.

* **Objective:** Test pipeline resilience against extreme edge cases (0-ball players, unclassified venues, rain-affected matches, extreme price outliers).
* **Inputs:** Pipeline scripts, synthetic edge-case dataset.
* **Work:** Run `tests/test_edge_cases.py` feeding synthetic edge cases into ingestion, feature engineering, and optimization pipelines. Assert graceful handling, logging, and flagging without pipeline crashes.
* **Deliverables:** `tests/test_edge_cases.py`, pass report in `reports/edge_case_report.json`.
* **Validation Checks:** Pipeline handles all synthetic edge cases without unhandled exceptions or silent metric corruption.
* **Common Failure Modes:** Unhandled division by zero in rate metrics for 0-ball faced edge cases.
* **Commit Message:** `test(qa): test pipeline resilience against extreme edge cases and boundary conditions`
* **memory.md Update Requirement:** Document edge cases tested and error handling mechanisms.
* **Exit Criteria:** Edge case test suite passes 100%.

### 10.6 End-to-End Reproducibility & Fresh-Run Verification

> **Scope status (v1.1):** SCOPED DOWN — confirm the pipeline reruns cleanly end-to-end once, not a formal reproducibility protocol.

* **Objective:** Perform clean, automated end-to-end execution of full pipeline from raw data ingestion to export generation on a clean machine environment.
* **Inputs:** Raw datasets, full repository codebase.
* **Work:** Clean all `data/interim/`, `data/processed/`, `data/features/`, and `data/exports/` files. Execute master orchestration script `scripts/run_full_pipeline.py`. Verify all output Parquet files, reports, and export binaries are regenerated cleanly with identical checksums.
* **Deliverables:** Executable master script `scripts/run_full_pipeline.py`, pipeline run log `reports/full_pipeline_run.log`.
* **Validation Checks:** Master script executes end-to-end in single command without errors; generated export tables match benchmark hashes within floating point tolerance.
* **Common Failure Modes:** Unstated manual step dependencies breaking pipeline automation.
* **Commit Message:** `test(qa): execute fresh end-to-end pipeline run and verify total reproducibility`
* **memory.md Update Requirement:** Record full fresh-run execution time, generated file hashes, and total pipeline status.
* **Exit Criteria:** Pipeline executes cleanly end-to-end via single command script.

---

## PHASE 11 — Final Presentation & Narrative Deliverables

### 11.1 Executive Narrative & Decision Deck

> **Scope status (v1.1):** IN SCOPE — this is the primary deliverable, produced as a written document/deck rather than a live dashboard walkthrough.

* **Objective:** Produce presentation-ready executive decision narrative summarizing findings without requiring source code inspection per PRD §10 & §13.
* **Inputs:** Dashboard exports, optimization scenarios, squad gap reports.
* **Work:** Write standalone executive summary report `reports/RCB_Auction_Strategy_Executive_Deck.md` and export slide PDF outline. Structure: Executive Problem Statement, Identified Squad Gaps, Recommended Target Shortlist, Purse Allocation Blueprint, and Strategic Risk Management.
* **Deliverables:** `reports/RCB_Auction_Strategy_Executive_Deck.md`.
* **Validation Checks:** Document is fully understandable by non-technical stakeholders without opening code files.
* **Common Failure Modes:** Including code snippets or raw SQL queries in executive deck.
* **Commit Message:** `docs(deck): create executive decision narrative and auction strategy deck`
* **memory.md Update Requirement:** Record executive deck completion and key presentation takeaways.
* **Exit Criteria:** Executive deck saved under `reports/`.

### 11.2 Target Player Shortlist & Bid Limits Documentation

> **Scope status (v1.1):** IN SCOPE — this is the actual ask: the shortlist and bid ceilings.

* **Objective:** Document complete 30–40 candidate target list, role fit, max recommended bids, and backup options.
* **Inputs:** `candidate_shortlist_30_40.parquet`, candidate max bids, Model C similarity matrix.
* **Work:** Generate structured documentation table `reports/target_shortlist_and_bid_limits.md` cataloging every shortlisted candidate, role category, Objective Fair Value, Expected Market Price, Max Recommended Bid ceiling, and designated Model C backup player.
* **Deliverables:** `reports/target_shortlist_and_bid_limits.md`.
* **Validation Checks:** Confirm every candidate entry includes all required bid ceiling and backup fields.
* **Common Failure Modes:** Missing backup candidate mappings for marquee targets.
* **Commit Message:** `docs(deck): document 30-40 candidate target shortlist with bid ceilings and backup maps`
* **memory.md Update Requirement:** Record complete shortlist summary documentation status.
* **Exit Criteria:** Shortlist documentation generated and saved in `reports/`.

### 11.3 Alternative Strategy & Contingency Playbook

> **Scope status (v1.1):** SCOPED DOWN — a brief alternatives section, not a full contingency playbook.

* **Objective:** Produce operational auction-room playbook detailing contingency responses during live bidding dynamics (e.g. if target price exceeds Max Bid).
* **Inputs:** Optimization scenarios (Bargain, Marquee, Balanced).
* **Work:** Write `reports/auction_room_contingency_playbook.md`. Define decision trees: "If Target A exceeds Max Recommended Bid by > 10% -> Pivot to Backup Candidate B", "If Purse drops below ₹15 Cr before Death Bowler acquired -> Switch to Scenario A Bargain Strategy".
* **Deliverables:** `reports/auction_room_contingency_playbook.md`.
* **Validation Checks:** Ensure contingency decision trees cover all primary target roles.
* **Common Failure Modes:** Vague contingency advice ("try to find another bowler") without named backup mapping.
* **Commit Message:** `docs(playbook): produce auction-room live bidding contingency decision tree playbook`
* **memory.md Update Requirement:** Record contingency playbook details.
* **Exit Criteria:** Playbook complete and saved under `reports/`.

### 11.4 Key Analytical Insights Summary

> **Scope status (v1.1):** IN SCOPE — kept short.

* **Objective:** Summarize major analytical discoveries (e.g. Chinnaswamy venue bias impact, domestic-to-franchise transition drop-off rate, phase scoring acceleration curves).
* **Inputs:** Feature datasets, EDA reports, ML model outputs.
* **Work:** Compile `reports/key_analytical_insights.md` synthesizing technical and cricket insights discovered across the pipeline.
* **Deliverables:** `reports/key_analytical_insights.md`.
* **Validation Checks:** All insight claims cite specific underlying pipeline metrics or model outputs.
* **Common Failure Modes:** Presenting unsubstantiated cricket opinions not backed by pipeline data.
* **Commit Message:** `docs(insights): summarize key analytical discoveries and statistical findings`
* **memory.md Update Requirement:** Document key analytical insights log.
* **Exit Criteria:** Key insights document saved in `reports/`.

### 11.5 System Limitations & Future Roadmap

> **Scope status (v1.1):** IN SCOPE — should honestly name everything descoped in this amendment.

* **Objective:** Document explicit system limitations and future technical/analytical roadmap per PRD §12 & §13.
* **Inputs:** Data quality reports, model validation audits, PRD non-goals.
* **Work:** Write `reports/system_limitations_and_roadmap.md` detailing: (1) Disclosed Data Limitations (e.g. lack of ball-tracking tracking data for wagon wheels, public availability tracking gaps), (2) Methodological Limitations (survivorship bias in domestic models), and (3) Future Enhancements (e.g. tracking physical fitness telemetry, real-time auction API integration).
* **Deliverables:** `reports/system_limitations_and_roadmap.md`.
* **Validation Checks:** Ensure all limitations cited in PRD §12 & §13 are explicitly documented.
* **Common Failure Modes:** Claiming model perfection or masking known data gaps.
* **Commit Message:** `docs(system): document system limitations, methodology disclosures, and future roadmap`
* **memory.md Update Requirement:** Log system limitations and future enhancements.
* **Exit Criteria:** Limitations and roadmap document complete and saved in `reports/`.

### 11.6 Independent Methodology & Technical Walkthrough

> **Scope status (v1.1):** SCOPED DOWN — a short methodology appendix, not a standalone full walkthrough document.

* **Objective:** Create complete technical portfolio walkthrough document enabling external technical review or interview presentation.
* **Inputs:** Architecture specifications, pipeline codebase, validation reports.
* **Work:** Write comprehensive portfolio walkthrough `reports/technical_methodology_walkthrough.md`. Detail problem framing, local-first DuckDB/Parquet architecture, feature engineering pipeline, ML model design and temporal validation, OR-Tools optimization framework, Power BI integration, and reproducibility guide.
* **Deliverables:** `reports/technical_methodology_walkthrough.md`.
* **Validation Checks:** Walkthrough enables a technical reviewer to understand and evaluate the entire system without opening raw source files.
* **Common Failure Modes:** Incomplete technical explanations of ML models or optimization constraints.
* **Commit Message:** `docs(walkthrough): produce independent technical methodology walkthrough for portfolio review`
* **memory.md Update Requirement:** Log completion of Phase 11 and final project status.
* **Exit Criteria:** Technical walkthrough document completed; full project state updated in `memory.md`.

---

## Master Progress Checklist

* [ ] **PHASE 0 — Project Foundation**
* [ ] 0.1 Repository Setup & Folder Hierarchy
* [ ] 0.2 Environment & Dependency Management
* [ ] 0.3 Quality & Configuration Foundation


* [ ] **PHASE 1 — Data Acquisition**
* [ ] 1.1 Source Inventory & Manifest Framework
* [ ] 1.2 Cricsheet Ball-by-Ball Ingestion
* [ ] 1.3 Metadata & Biographical Ingestion
* [ ] 1.4 Auction Data Ingestion
* [ ] 1.5 Provenance & Source Manifest Verification


* [ ] **PHASE 2 — Data Engineering & Normalization**
* [x] 2.1 Raw Data Normalization
* [ ] 2.2 Match & Delivery Schema Construction
* [ ] 2.3 Player Identity Resolution & Canonical Mapping
* [ ] 2.4 Competition & Season Normalization
* [ ] 2.5 Venue Normalization & Mapping
* [ ] 2.6 DuckDB & Parquet Storage Layer Integration
* [ ] 2.7 Automated Data-Quality Checks & Contract Validation


* [ ] **PHASE 3 — Exploratory Data Analysis (EDA)**
* [ ] 3.1 League Scoring Environments & Baseline Comparison
* [ ] 3.2 Venue Characteristics & Physical Environment Analysis
* [ ] 3.3 Batter Distributions & Milestone Profile Analysis
* [ ] 3.4 Bowler Distributions & Spell Profile Analysis
* [ ] 3.5 Domestic vs Franchise Competition Comparison
* [ ] 3.6 Auction Economics & Historical Price Dynamics


* [ ] **PHASE 4 — Advanced Feature Engineering**
* [ ] 4.1 Batting Features
* [ ] 4.2 Bowling Features
* [ ] 4.3 Consistency Features
* [ ] 4.4 Phase Features
* [ ] 4.5 Matchup Features
* [ ] 4.6 Venue Features
* [ ] 4.7 Pitch/Environment Classification & Archetype Clustering
* [ ] 4.8 Pressure & Situational Context Features
* [ ] 4.9 League-Strength Adjustment Features
* [ ] 4.10 Domestic-to-Franchise Translation Features


* [ ] **PHASE 5 — RCB Squad Diagnosis & Gap Analysis**
* [ ] 5.1 Squad Inventory & Roster State Assessment
* [ ] 5.2 Role Classification & Skill Tagging
* [ ] 5.3 Existing Strengths Assessment
* [ ] 5.4 Squad Weaknesses & Critical Gap Identification
* [ ] 5.5 Required Role Specifications & Target Profiles
* [ ] 5.6 Budget & Roster Slot Constraint Definition
* [ ] 5.7 Candidate Search Universe Generation


* [ ] **PHASE 6 — Candidate Filtering & Funnel Pipeline**
* [ ] 6.1 Universe Definition & Minimum Sample Filtering
* [ ] 6.2 Performance Threshold & Role Alignment Filtering
* [ ] 6.3 Consistency & Floor/Ceiling Filtering
* [ ] 6.4 Pitch Adaptability & Matchup Filtering
* [ ] 6.5 League Translation & Availability Filtering (Final Shortlist ~30–40 Candidates)


* [ ] **PHASE 7 — ML Modelling & Valuation**
* [ ] 7.1 Statistical Baseline Models
* [ ] 7.2 Auction Price Model (Model A1 — Expected Market Price)
* [ ] 7.3 Fair-Value Model (Model A2 — Objective Value)
* [ ] 7.4 Domestic-to-Franchise Translation Model (Model B)
* [ ] 7.5 Player Similarity & Clustering Model (Model C — Optional/Unsupervised)
* [ ] 7.6 Model Validation, Temporal Evaluation & Leakage Audit
* [ ] 7.7 Explainability Framework (SHAP / Feature Attribution)


* [ ] **PHASE 8 — Auction Optimization & Scenario Planning**
* [ ] 8.1 Budget & Purse Allocation Model
* [ ] 8.2 Squad Constraint Solver Setup
* [ ] 8.3 Maximum Recommended Bid Logic
* [ ] 8.4 Player Combination Optimizer
* [ ] 8.5 Bargain Scenario Generator
* [ ] 8.6 Star-Player / Anchor Strategy Generator
* [ ] 8.7 Depth & Balance Scenario Generator
* [ ] 8.8 Multi-Scenario Comparison Framework


* [ ] **PHASE 9 — Power BI Dashboard Layer**
* [ ] 9.1 Data Model & Power Query Data Layer Exports
* [ ] 9.2 Design Theme, Color Palette & Typography
* [ ] 9.3 Executive Overview Page
* [ ] 9.4 Squad Gap Analysis Page
* [ ] 9.5 Player Discovery Page
* [ ] 9.6 Player Profile Page
* [ ] 9.7 Pitch/Venue Intelligence Page
* [ ] 9.8 Matchup Intelligence Page
* [ ] 9.9 Auction Value Page
* [ ] 9.10 Scenario Simulator / Auction Simulator Page
* [ ] 9.11 Final Recommendation Page
* [ ] 9.12 Methodology & Data Quality Page


* [ ] **PHASE 10 — Validation & Quality Assurance**
* [ ] 10.1 Data QA & Lineage Validation
* [ ] 10.2 Formula & Metric Audit
* [ ] 10.3 ML Model Evaluation & Temporal Audit
* [ ] 10.4 Dashboard QA & Interactivity Verification
* [ ] 10.5 Edge-Case, Outlier & Boundary Testing
* [ ] 10.6 End-to-End Reproducibility & Fresh-Run Verification


* [ ] **PHASE 11 — Final Presentation & Narrative Deliverables**
* [ ] 11.1 Executive Narrative & Decision Deck
* [ ] 11.2 Target Player Shortlist & Bid Limits Documentation
* [ ] 11.3 Alternative Strategy & Contingency Playbook
* [ ] 11.4 Key Analytical Insights Summary
* [ ] 11.5 System Limitations & Future Roadmap
* [ ] 11.6 Independent Methodology & Technical Walkthrough