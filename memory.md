# Project Memory & Progress Log

## Phase 2.3: Player Identity Resolution & Baseline Valuation (Completed)
- **Identity Resolution Strategy**: Built a multi-pass pipeline (Exact matching, Normalized strings, Fuzzy similarity >= 0.82, Surname + Initial patterns).
- **Match Rates Achieved**:
  - Metadata & Participation: **99.88%** resolved.
  - Historical Auction Records: **83.13%** resolved.
  - Unresolved Edge Cases: 141 records exported to `reports/unresolved_players_manual_review.csv`.
- **Master Feature Store**: Generated `data/processed/master_player_features.csv` covering 551 player profiles.
- **Valuation Model**: Pure NumPy/Pandas OLS linear regression model ($R^2 = 0.2645$, MAE = 13.47M, RMSE = 20.97M).
- **Key Deliverables**: `reports/RCB_Auction_Strategy_Report.md`, `reports/rcb_auction_target_shortlist.csv`.

## Phase 2.4: Competition & Season Normalization (Completed)
- **Script**: `src/cleaning/normalize_competitions.py`
- **Output Artifacts**: `data/processed/dim_competitions.parquet` & `data/processed/dim_competitions.csv`
- **Standardization Results**: 75 total series mapped (33 Overseas Franchise, 23 Domestic, 19 IPL).

## Phase 2.5: Delivery-Level Cleaning & Feature Prep (Completed)
- **Script**: `src/features/build_delivery_features.py`
- **Output Artifacts**:
  - `data/processed/fact_deliveries.parquet` (and CSV fallback)
  - `data/processed/player_phase_features.parquet` (and CSV fallback)
- **Feature Engineering & Phase Segmentation**:
  - Overs partitioned into Powerplay (Overs 1–6), Middle Overs (Overs 7–15), and Death Overs (Overs 16–20).
  - Engineered phase-wise Strike Rates, Boundary %, and Dot Ball % metrics mapped to canonical player IDs.
