# memory.md

## 1. Project Identity

* **Project Name:** RCB Auction Intelligence Engine


* **Purpose:** Context-aware player evaluation and auction decision-support system


* **Current Version/Stage:** v1.0 / Foundation Setup


* **Repository:** `rcb-auction-intelligence`

* **Current Phase:** Phase 0 — Project Foundation


* **Current Subphase:** 0.3 — Quality & Configuration Foundation



## 2. Product Summary

The RCB Auction Intelligence Engine is a decision-support platform designed to evaluate candidate players, identify squad gaps, compute objective fair value and maximum bid ceilings, and optimize squad construction under purse and roster constraints. Using Cricsheet ball-by-ball records and historical IPL auction data, it evaluates players across context-aware dimensions (innings phase, pitch archetype, matchup profiles, consistency distributions, and league-strength adjustments). The engine filters broad candidate pools into a focused shortlist of 30–40 candidates and delivers actionable auction strategy via an interactive 10-page Power BI dashboard.

## 3. Permanent Principles

* **Evidence first:** All analytical conclusions and recommendations must be grounded in verified empirical data.


* **No fabricated data:** Never invent statistics, approximate missing fields with arbitrary numbers, or treat unverified web data as factual.


* **Explainable recommendations:** Every recommendation, player valuation, or ranking must be traceable to underlying data and explicit model layers.


* **Reproducibility:** The entire pipeline must run deterministically from raw data to export tables with zero manual intervention.


* **Context-aware player evaluation:** Raw aggregate statistics must never be evaluated without phase, venue, pitch, and matchup context.


* **ML only when useful:** Machine learning is employed only where it demonstrably improves decisions over simpler statistical baselines.


* **Power BI for presentation:** Power BI serves purely as an interactive visualization and presentation layer for pre-computed analytical exports.


* **Python for analytical computation:** All data processing, feature engineering, modeling, and optimization logic executes in Python.


* **DuckDB/Parquet for local analytical storage:** Local columnar Parquet files queried via embedded DuckDB serve as the analytical data engine.



## 4. Architecture Snapshot

```
Data sources[cite: 4]
↓
Python ingestion[cite: 4]
↓
Validation[cite: 4]
↓
DuckDB/Parquet[cite: 4]
↓
Feature engineering[cite: 4]
↓
ML[cite: 4]
↓
Optimization[cite: 4]
↓
Power BI[cite: 4]

```

## 5. Technology Stack

* **Runtime & Core Language:** Python 3.11+


* **Data Processing:** pandas, numpy


* **Analytical Storage Engine:** DuckDB, PyArrow (Parquet)


* **Schema Contract & Testing:** pytest, pandera


* **Machine Learning:** scikit-learn, XGBoost


* **Optimization Solver:** Google OR-Tools


* **Utilities & Configuration:** PyYAML


* **Exploratory Plotting:** matplotlib, plotly


* **Presentation Layer:** Power BI Desktop



## 6. Data Sources

* **Cricsheet T20 Ball-by-Ball Data:** Sourced from Cricsheet; covers IPL, BBL, CPL, SA20, ILT20, MLC, The Hundred, and Indian domestic T20s (SMAT); JSON/CSV formats; high reliability.


* **IPL Auction Records:** Historical auction bids, retentions, unsold lists, and purse spent (2018–2026); CSV format; public auction records.


* **Player Metadata & Roster Registry:** Sourced from Cricsheet and official competition records; captures demographics, primary skill, batting/bowling styles, and official team rosters.


* **Venue & Ground Metadata:** Sourced from match records; maps raw venue names to physical grounds and city locations.



## 7. Dataset Status

| Source | Status | Notes |
| --- | --- | --- |
| **Cricsheet Ball-by-Ball** | TODO | Manifest defined in `configs/source_manifest.json`<br> |
| **Auction History Data** | TODO | Ingestion pipeline defined for Phase 1.4

 |
| **Player Metadata** | TODO | Ingestion pipeline defined for Phase 1.3

 |
| **Venue Metadata** | TODO | Mapping framework planned for Phase 2.5

 |
| **Processed Deliveries & Matches** | TODO | Normalization planned for Phase 2.1–2.6

 |

## 8. Current Data Schema

* **Configuration Specifications:** `configs/source_manifest.json`, `configs/player_mapping.json`, `configs/venue_mapping.json`, `configs/role_taxonomy.json`.


* **Data Files:** Zero Parquet data binaries exist in `data/` prior to Phase 1 execution.



## 9. Feature Registry

| Feature Name | Definition | Status | Tested | Source |
| --- | --- | --- | --- | --- |
| **Boundary Dependency** | Proportion of total runs scored from boundaries vs. singles/doubles | PLANNED | NO | `src/features/batting.py`<br> |
| **Phase Rate Metrics** | Strike rate / Economy rate segmented into Powerplay (1–6), Middle (7–15), Death (16–20) | PLANNED | NO | `src/features/phase.py`<br> |
| **Consistency Percentiles** | P10, P25, P50, P75, P90 distribution statistics for batting scores and bowling spells | PLANNED | NO | `src/features/consistency.py`<br> |
| **Pitch Archetype Assignment** | Data-driven match pitch cluster label (High-Scoring, Spin-Friendly, Pace, Tricky) | PLANNED | NO | `src/analytics/pitch_clustering.py`<br> |
| **League Adjustment Multiplier** | Empirical league strength multiplier derived from crossover player performance | PLANNED | NO | `src/analytics/league_adjustment.py`<br> |

## 10. Model Registry

* **Model A1 — Expected Market Price:** XGBoost / Ridge regression model predicting expected auction price band; status: PLANNED; validation: temporal holdout on 2024–2025 auctions.


* **Model A2 — Fair-Value Model:** Performance and scarcity-grounded objective valuation model; status: PLANNED; validation: out-of-sample impact calibration.


* **Model B — Domestic-to-Franchise Translation Model:** Regression/GBDT model predicting IPL performance percentiles for uncapped domestic players; status: PLANNED; validation: temporal holdout on crossover cohort.


* **Model C — Player Similarity & Clustering Model:** Unsupervised nearest-neighbor clustering on normalized skill vectors; status: PLANNED; validation: silhouette scores and cluster stability checks.



## 11. Auction Logic

* **Roster Constraints:** Total squad size $18 \le N_{\text{total}} \le 25$; overseas players $N_{\text{overseas}} \le 8$; total spend $\sum \text{price}_i \le \text{Purse}_{\text{remaining}}$.


* **Role Requirements:** Explicit coverage maps for top-order batters, middle-order spin hiters, wicketkeepers, express pace bowlers, and death specialists.


* **Fair Value Logic:** Derived from league-adjusted impact, phase importance, and role scarcity multipliers.


* **Maximum Bid Logic:** Computed as $\text{MaxBid}_i = \text{FairValue}_i \times (1 + \text{ScarcityAdjustment}) \times \text{SquadFitMultiplier}$, bounded by purse cap.


* **Optimization Framework:** Solved via Google OR-Tools Integer Linear Programming (ILP) across pre-filtered 30–40 candidate shortlist.



## 12. Design State

* **Color System:** Canvas (`#F8F9FA`), Cards (`#FFFFFF`), Text (`#1E1E1E`), Accent Red (`#D11A2A`), Gold (`#D4AF37`), Positive Green (`#16A34A`), Risk Red (`#DC2626`).


* **Typography:** Inter (Primary Sans-Serif), JetBrains Mono (KPI Numbers & Micro Values).


* **Layout Grid:** 12-column grid ($1920 \times 1080\text{ px}$) with $16\text{ px}$ outer margins and $12\text{ px}$ card padding.


* **Completed Pages:** 0 / 10 Power BI dashboard pages completed.


* **Known UI Problems:** None reported.



## 13. Decisions Log

* **Decision:** Adopt DuckDB + Parquet local columnar storage layer.


* **Reason:** Provides serverless, fast analytical SQL querying over local files without external database overhead.


* **Alternatives Considered:** PostgreSQL, SQLite, Pandas in-memory DataFrames.


* **Why Rejected:** PostgreSQL introduces external server requirements; SQLite lacks columnar query performance; Pandas lacks SQL interface across large multi-table joins.


* **Date:** Phase 0.0


* **Phase:** Phase 0




* **Decision:** Keep Fair Value, Expected Market Price, and Maximum Recommended Bid strictly separate.


* **Reason:** Objective worth, market price sentiment, and strategic team bid ceilings measure fundamentally different analytical concepts.


* **Alternatives Considered:** Merging into a single recommended bidding price.


* **Why Rejected:** Blending sentiment and value creates opaque recommendations and hides team context.


* **Date:** Phase 0.0


* **Phase:** Phase 0





## 14. Known Issues

* **Bugs:** None currently open.


* **Data Gaps:** Cricsheet data lacks spatial ball-tracking coordinates (wagon wheel positions); true fielding chance data is unrecorded.


* **Unsupported Assumptions:** Domestic T20 match context assumes baseline environmental consistency prior to statistical adjustment.


* **Model Weaknesses:** Domestic-to-franchise translation models exhibit historical survivorship bias among crossover players.


* **Dashboard Limitations:** Power BI scenario simulation operates over pre-computed OR-Tools optimizer exports rather than dynamic DAX solver logic.



## 15. Open Questions

* **Question 1:** What minimum delivery sample cutoff best balances noise reduction with candidate pool coverage for uncapped domestic bowlers?


* **Status:** Open (Scheduled for resolution in Phase 6.1)




* **Question 2:** Should overseas candidates with partial IPL availability receive a dynamic percentage discount on Fair Value?


* **Status:** Open (Scheduled for resolution in Phase 7.3)





## 16. Completed Work

* **Phase 0.0 — Specification & Architecture Baseline:** Completed (`PRD.md`, `architecture.md`, `rules.md`, `phase.md`, `design.md`, `memory.md`).


* **Phase 0.2 — Environment & Dependency Management:** Completed (`.venv` virtualenv created, core libraries installed, `requirements.txt` generated, imports verified).


* **Phase 0.1 — Repository Setup & Folder Hierarchy:** Completed (Directory tree created with `.gitkeep` placeholder files).



## 17. Git History

| Commit | Purpose | Phase/Subphase |
| --- | --- | --- |
| `3265644` | Baseline project specifications created (`PRD.md`, `architecture.md`, `rules.md`, `phase.md`, `design.md`) | Phase 0.0 |
| `21894a7` | Establish Python virtual environment and dependencies for project foundation | Phase 0.2 |

## 18. Current Next Action

CURRENT PHASE: Phase 0 — Project Foundation
CURRENT SUBPHASE: 0.3 — Quality & Configuration Foundation
NEXT ACTION: Implement local package setup (`setup.py` / `pyproject.toml`) and establish foundational quality/config infrastructure (`src/utils/config.py`, `logger.py`, `exceptions.py`, `tests/conftest.py`).
BLOCKERS: None


## 19. AI-Agent Instructions

Every AI agent must:

1. Read `PRD.md`

2. Read `architecture.md`

3. Read `rules.md`

4. Read `phases.md`

5. Read `design.md`

6. Read `memory.md`

7. Inspect the actual repository


8. Understand current status


9. Make the smallest appropriate change


10. Run validation/tests


11. Update documentation


12. Update `memory.md`

13. Report what changed and what remains



AI agents must never assume that their previous conversation contains the complete project context.

The repository is the source of truth. **memory.md** describes the current state of that repository; it must never pretend unfinished work is complete ai should not strictly waste any tokens reading codes just read memory.md to know current status and from where to resume

## Phase 1.3 Status

**Completed:** Canonical player identity ingestion and competition participation metadata.

**Verified outputs:**
- `data/raw/metadata/player_identity.csv`
- `data/raw/metadata/player_participation.csv`
- `data/raw/metadata/player_competition_summary.csv`
- `reports/phase_1_3_metadata_qa.json`

**Verified scale:**
- 18,507 canonical Cricsheet people
- 18,507 unique identifiers
- 1,973 players appearing in acquired IPL/SMAT matches
- 1,938 unique matches
- 43,333 participation records
- 7,366 player-season-competition records
- 19 IPL seasons
- 9 SMAT seasons

**Important data decision:** The Cricsheet People Register provides canonical identity and external identifiers but does not provide authoritative age, nationality, role, batting position, or bowling style. These fields must not be fabricated or inferred from this source. Authoritative biographical sources remain pending.

**Phase 1.3 QA:** PASS.

**Next:** Phase 1.4 ? IPL Auction Data Ingestion.

## Phase 1.4.1 � Auction Source Discovery & Schema Decisions

**Status:** Schema locked before implementation.

### Locked raw auction schema

The raw auction ingestion table contains 27 fields:

1. uction_year
2. uction_date
3. uction_type
4. player_name_raw
5. cricsheet_player_id
6. entry_mechanism
7. sold_status
8. etention_status
9. ranchise_raw
10. ase_price_inr_lakh
11. ase_price_display
12. sold_price_inr_lakh
13. sold_price_display
14. etention_price_inr_lakh
15. etention_price_display
16. etention_price_type
17. currency
18. price_note
19. player_category
20. season_franchise_purse_crore
21. source_primary
22. source_primary_url
23. source_crosscheck
24. source_crosscheck_url
25. etrieval_date
26. data_confidence
27. source_conflict_note

### Schema decisions

- uction_year is used for auction-cycle identity and aligns with rchitecture.md (uction_history primary key includes uction_year).
- Cricket performance tables continue using season.
- etention_status is explicit and is not inferred from sold_status.
- sold_price_* represents auction purchase price only.
- etention_price_* represents retention-related deduction/contract value and is kept separate from auction sale price.
- etention_price_type values: BCCI_PURSE_DEDUCTION, CONTRACTED_SALARY, UNKNOWN.
- entry_mechanism = DRAFT is used for confirmed 2022 GT/LSG pre-auction draft selections.
- Match fees are excluded from auction price fields.
- Confirmed SOLD, confirmed UNSOLD, and UNKNOWN outcomes are retained.
- ranchise_raw is nullable for UNSOLD and UNKNOWN records.
- Raw player names are preserved exactly as sourced; canonical identity resolution is deferred to Phase 2.3.
- cricsheet_player_id remains nullable unless explicitly supported by approved provenance.
- Human-readable price strings are preserved alongside normalized numeric values in INR lakh.
- Fair Value, Expected Market Price, and Maximum Recommended Bid are model/optimization outputs and are excluded from raw auction ingestion.
- UNKNOWN must be used where available evidence cannot establish an auction outcome; records must not be silently classified as UNSOLD.

### Downstream architecture alignment

The processed uction_history entity will use the canonical player_id + auction_year grain defined in rchitecture.md. Player identity resolution occurs in Phase 2.3 rather than during raw auction ingestion.

