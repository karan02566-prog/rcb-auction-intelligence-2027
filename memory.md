# memory.md

## 1. Project Identity

* **Project Name:** RCB Auction Intelligence Engine


* **Purpose:** Context-aware player evaluation and auction decision-support system


* **Current Version/Stage:** v1.0 / Foundation Setup


* **Repository:** `rcb-auction-intelligence`

* **Current Phase:** Phase 0 — Project Foundation


* **Current Subphase:** 0.1 — Repository Setup & Folder Hierarchy



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

* **Phase 0.0 — Specification & Architecture Baseline:** Completed.



## 17. Git History

| Commit | Purpose | Phase/Subphase |
| --- | --- | --- |
| `Initial` | Baseline project specifications created (`PRD.md`, `architecture.md`, `rules.md`, `phases.md`, `design.md`) | Phase 0.0

 |

## 18. Current Next Action

CURRENT PHASE: Phase 0 — Project Foundation
CURRENT SUBPHASE: 0.1 — Repository Setup & Folder Hierarchy
NEXT ACTION: Create directory tree (`data/{raw,interim,processed,features,exports}`, `notebooks/`, `src/{ingestion,cleaning,validation,features,models,optimization,analytics,utils}`, `tests/`, `models/`, `reports/`, `powerbi/`, `configs/`, `scripts/`) and configure `.gitignore`.
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