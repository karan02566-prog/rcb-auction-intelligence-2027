# RCB Auction Intelligence Engine — Architecture

**Document status:** Draft v1.0
**Document owner:** Product/Data Architecture
**Authoritative reference:** `PRD.md`. Where this document is silent or ambiguous, the PRD governs. This document does not introduce product requirements — it only specifies how the PRD's requirements are implemented at a system level.

**Scope note:** This document is architecture, not implementation. It does not contain code. It defines pipelines, layers, storage, data model, and decision boundaries so that any contributor (human or AI coding assistant) can implement the system consistently.

---

## 1. Architecture Goal

The system is a **local-first, reproducible analytics pipeline** that turns public ball-by-ball and auction data into an auction decision-support product, ending in a Power BI presentation layer.

```
Raw Data
  ↓
Ingestion
  ↓
Validation
  ↓
Normalized Data
  ↓
Feature Engineering
  ↓
Statistical Analysis
  ↓
ML Models
  ↓
Auction Optimization
  ↓
Analytical Outputs
  ↓
Power BI
```

Each stage:

- Consumes only the artifacts produced by the stage before it (no stage reaches "backward" or "sideways" into raw sources it doesn't own).
- Writes its output to a well-defined location in `data/` (Section 3) so the pipeline can be re-run deterministically from any stage forward, given its declared inputs.
- Is independently testable (Section 10).

This pipeline structure is also how the PRD's four analytical layers (Section 9.2 of the PRD — descriptive, statistical, ML, optimization) map onto physical code and data:

| PRD analytical layer | Pipeline stage(s) |
|---|---|
| Descriptive analytics | Normalized Data, Feature Engineering |
| Statistical modelling | Statistical Analysis |
| Machine learning | ML Models |
| Optimization | Auction Optimization |

No component may skip a layer (e.g., no dashboard measure may quietly reimplement a statistical adjustment that belongs upstream — see Section 7).

---

## 2. Technology Stack

The stack is deliberately minimal. Nothing below requires a server process, a container runtime, or a cloud account. Everything runs on a single developer machine.

| Concern | Choice | Rationale |
|---|---|---|
| Language | Python | Single language across ingestion, features, ML, and optimization; large ecosystem for all required tasks |
| Data manipulation | pandas, NumPy | Standard, well-understood, sufficient at this data scale |
| Analytical storage/querying | DuckDB, Parquet | Columnar, embedded, no server; DuckDB queries Parquet directly and cheaply; ideal for local-first analytics |
| Data validation | pytest, pandera (where useful) | pytest for pipeline/unit tests; pandera for schema/contract validation of DataFrames at layer boundaries |
| Visualization (analysis-time only) | matplotlib, plotly (where genuinely useful) | Exploratory and validation plots during development; not the delivery mechanism for end users |
| Machine learning | scikit-learn, XGBoost (if justified) | Explainable, well-validated defaults; XGBoost only where a use case demonstrates the need (PRD §9.4) |
| Optimization | OR-Tools (where appropriate) | Constraint/linear/integer programming for squad-construction under purse and roster constraints |
| Dashboard | Power BI, Power Query, DAX | Presentation and interaction layer only (Section 7) |
| Development | VS Code, Git, GitHub | Standard local-first developer tooling |
| AI coding assistance | Gemini 3.7 Flash; Cline or another open-source coding agent; OpenHands (optional) | Assistive only — see constraint below |

**Constraint carried over from the brief:** the architecture must remain fully functional without any proprietary AI service. AI coding assistants are a development-time convenience for writing and reviewing code; they are not a runtime dependency of the pipeline, the models, or the dashboard. If every AI assistant were removed tomorrow, the system must still ingest data, compute features, train models, optimize squads, and refresh the dashboard.

**Explicitly excluded** unless a concrete, documented requirement later justifies them: PostgreSQL, MongoDB, Spark, Kafka, Docker, any cloud infrastructure, microservices. At the current data volume (ball-by-ball data for a bounded set of competitions and seasons), DuckDB + Parquet + pandas is sufficient; adding any of the excluded technologies would add operational surface area without a decision-relevant benefit.

---

## 3. Storage Architecture

```
data/
├── raw/         # exact, untouched copies of source data
├── interim/     # cleaned/normalized, still close to source granularity
├── processed/   # analytics-ready tables (descriptive layer)
├── features/    # feature-engineered tables (feature + statistical layers)
└── exports/     # Power BI-ready, denormalized outputs
```

Rules:

- Parquet is the default file format for anything tabular and larger than a few hundred rows. DuckDB is the query engine used to join, aggregate, and transform Parquet files across the `interim/` → `processed/` → `features/` → `exports/` stages.
- Nothing in `raw/` is ever edited in place. Corrections happen downstream, in `interim/` transformations, so the original source is always re-derivable.
- Every file under `processed/`, `features/`, and `exports/` is produced by a script in `src/`, never by hand. There are no hidden manual edits to any analytical dataset (PRD-aligned principle, Section 10).
- Small reference/config data (e.g., minimum-sample thresholds, pitch-archetype rule definitions, role taxonomies) lives in `configs/` as versioned YAML/JSON, not hardcoded inside scripts, so it can be reviewed and changed without touching pipeline code.

---

## 4. Data Layers

### Raw
Exactly what was downloaded or received: Cricsheet match files in their original format, auction-price source files, biographical/role reference data, exactly as retrieved, with retrieval date recorded. Immutable.

### Staging/Interim
Cleaned and normalized representations of raw data: parsed ball-by-ball events, standardized player/team/venue identifiers, resolved name variants, de-duplicated match records. This layer resolves *data quality* problems, not *analytical* ones — it does not yet compute performance metrics.

### Processed
Analytics-ready tables at the descriptive layer: per-match, per-innings, per-delivery structured tables; resolved entities (Section 6) with stable keys; the tables that the Feature layer reads from. This is where "what happened" data lives.

### Feature Layer
Player-season / phase / matchup / venue feature tables, produced by the Feature Engineering and Statistical Analysis pipeline stages: volume/rate metrics, phase splits, milestone and percentile distributions, consistency scores, pitch-archetype assignments and their confidence levels, league-strength adjustment factors. This is the layer that answers the PRD's Core Product Questions in descriptive/statistical form, before any ML is applied.

### Model Layer
Training datasets (point-in-time correct — see Section 8), trained model artifacts, predictions, and validation/evaluation outputs (metrics, error analysis, SHAP explainability outputs) for Models A, B, and C (Section 8). Stored under `models/` (artifacts) and `data/features/` or a dedicated model-output area (predictions), never mixed with the deterministic statistical feature tables above.

### Dashboard Layer
Power BI-ready exports under `data/exports/`: denormalized, pre-joined, pre-aggregated tables that map closely to the dashboard pages defined in the PRD (Executive Overview, Squad Gap Analysis, Player Discovery, etc.). These exports already contain the results of statistical adjustment and ML inference — Power BI consumes them, it does not recompute them (Section 7).

---

## 5. Folder Architecture

```
rcb-auction-intelligence/
│
├── README.md
├── PRD.md
├── architecture.md
├── rules.md
├── phases.md
├── design.md
├── memory.md
│
├── data/
│   ├── raw/
│   ├── interim/
│   ├── processed/
│   ├── features/
│   └── exports/
│
├── notebooks/            # exploratory analysis and validation only — never a dependency of the pipeline
│
├── src/
│   ├── ingestion/        # raw → interim
│   ├── cleaning/         # interim normalization, entity resolution
│   ├── validation/       # pandera schemas, data-quality checks
│   ├── features/         # interim/processed → feature tables (descriptive + statistical)
│   ├── models/           # Model A / B / C training and inference code
│   ├── optimization/     # squad-construction optimization (OR-Tools)
│   ├── analytics/        # cross-cutting statistical logic (pitch clustering, league adjustment, consistency scoring)
│   └── utils/            # shared helpers (I/O, config loading, logging)
│
├── tests/                # pytest suite, mirrors src/ structure
│
├── models/               # serialized model artifacts + versioned metadata
│
├── reports/              # generated methodology notes, validation reports, portfolio write-ups
│
├── powerbi/              # .pbix file(s), Power Query (M) scripts, DAX measure documentation
│
├── configs/              # thresholds, taxonomies, pitch-archetype rules, model configs (YAML/JSON)
│
├── scripts/              # thin CLI entry points that call src/ modules to run pipeline stages end-to-end
│
└── requirements.txt
```

No changes from the suggested structure in the brief are made. This structure is adopted as-is because it already cleanly separates each pipeline stage (Section 1) into its own `src/` subpackage, keeps generated artifacts (`data/`, `models/`, `reports/`) out of source directories, and keeps the dashboard's presentation logic (`powerbi/`) physically separate from the analytical code that feeds it.

---

## 6. Data Model

The data model is intentionally a **star-like schema centered on players and matches**, not a fully normalized relational system. Complexity is added only where the PRD requires a distinct evaluation dimension.

### Core entities

| Entity | Primary key | Notes |
|---|---|---|
| `competitions` | `competition_id` | IPL, BBL, CPL, SA20, ILT20, MLC, The Hundred, domestic T20s, international T20 — one row per named competition (PRD §7.1) |
| `venues` | `venue_id` | Physical ground only (PRD §6.1 conceptual separation) — never conflated with pitch behavior |
| `teams` | `team_id` | Franchise/national/domestic teams across competitions |
| `players` | `player_id` | One row per unique person, resolved across name variants and competitions |
| `player_roles` | `player_id` (+ `role`) | Many-to-many: a player can have multiple roles/skills (e.g., batting all-rounder, keeper-batter); supports the role-flexibility dimension (PRD §4.3) |
| `matches` | `match_id` | One row per match; foreign keys to `competition_id`, `venue_id`, and both `team_id`s; carries match-environment fields (toss, day/night, etc. — PRD §6.1) |
| `deliveries` | `match_id` + `innings` + `over` + `ball` (composite key) | Ball-by-ball granularity (PRD §1.3); foreign keys to `match_id`, batter/bowler `player_id`, phase (derived) |

### Feature and analytical entities

| Entity | Primary key | Notes |
|---|---|---|
| `player_seasons` | `player_id` + `competition_id` + `season` | Aggregation grain for most reporting; foreign key to `players`, `competitions` |
| `batting_features` | `player_id` + `competition_id` + `season` (+ `phase` where phase-specific) | Volume/rate, phase, milestone, percentile-distribution, and matchup summary fields (PRD §4.1, §5.2) |
| `bowling_features` | `player_id` + `competition_id` + `season` (+ `phase` where phase-specific) | Analogous to `batting_features` (PRD §4.2, §5.2) |
| `matchup_features` | `player_id` + `opponent_type` (e.g., pace/spin, LHB/RHB, style sub-type) | Grain is deliberately coarser than raw deliveries; existence of a row requires clearing the minimum-sample threshold (PRD §4, §13) |
| `venue_features` | `venue_id` (+ `season` where conditions vary by season) | Descriptive venue statistics, distinct from pitch archetype |
| `pitch_archetypes` | `match_id` (+ `innings` where archetype can differ by innings) | Data-derived cluster/label plus a `confidence` field; foreign key to `match_id`, `venue_id`; never assigned from commentary or unverified third-party reports (PRD §6.2–6.3) |
| `player_consistency_profiles` | `player_id` + `competition_id` + `season` | The consistency score/badge (PRD §5.3) and the distribution statistics it is derived from; the derivation must be traceable, not a black box |
| `league_strength_adjustments` | `competition_id` + `season` | Statistical-layer adjustment factors used before any cross-league comparison (PRD §7.3) |

### Auction and squad entities

| Entity | Primary key | Notes |
|---|---|---|
| `auction_history` | `player_id` + `auction_year` | Historical auction/retention prices; foreign key to `players` |
| `squad_state` | `team_id` + `season` + `player_id` | Current roster composition, purse remaining, slot counts; foreign keys to `teams`, `players` |
| `model_predictions` | `player_id` + `model_name` + `as_of_date` | Output of Models A/B/C (Section 8); `as_of_date` enforces the point-in-time discipline described in Section 8's leakage controls |
| `optimization_scenarios` | `scenario_id` | One row per optimizer run; references a set of `model_predictions` and `squad_state` as inputs, and stores the resulting recommended squad(s) as output (Section 9) |

### Relationship principles

- `deliveries` is the single source of truth for on-field events; every batting, bowling, and matchup feature is derivable from it plus `matches`, `players`, and `venues`.
- `pitch_archetypes` references `matches`/`venues` but is never merged into `venues` directly — this preserves the PRD's required conceptual separation between venue, match environment, and pitch archetype (PRD §6.1).
- `model_predictions` and `optimization_scenarios` never write back into `player_seasons`, `batting_features`, `bowling_features`, or `matchup_features`. Descriptive/statistical feature tables remain untouched by ML or optimization outputs, so the provenance of every number stays traceable to its originating layer (PRD §9.2).
- The model deliberately avoids further normalization (e.g., separate tables per phase, per matchup sub-type) beyond what's listed above. Additional granularity is expressed through columns/keys (e.g., a `phase` column) rather than additional tables, to avoid an unnecessarily complex relational system.

---

## 7. Dashboard Flow

```
Cricsheet / official sources
  ↓
Python ingestion            (src/ingestion)
  ↓
Parquet                     (data/raw, data/interim)
  ↓
DuckDB transformations      (src/cleaning, src/validation → data/processed)
  ↓
Feature tables              (src/features, src/analytics → data/features)
  ↓
ML outputs                  (src/models → model_predictions)
  ↓
Optimization outputs        (src/optimization → optimization_scenarios)
  ↓
Final analytical datasets   (data/exports)
  ↓
Power BI
```

**Division of responsibility:**

- Everything upstream of `data/exports/` — ingestion, validation, feature engineering, statistical adjustment (league strength, pitch archetypes, consistency scoring), ML inference, and optimization — happens in Python/DuckDB, where it is version-controlled, testable, and reproducible from source data.
- `data/exports/` contains fully computed, denormalized tables shaped to match the PRD's dashboard pages (Executive Overview, Squad Gap Analysis, Player Discovery, Player Profile, Batting/Bowling/Pitch/Matchup Intelligence, Auction Value, Auction Simulator, Final Recommendations, Methodology/Data Quality).
- Power BI's role is **presentation, filtering, and interaction**: Power Query handles light shaping of already-computed exports for the report model; DAX is used for dashboard measures, slicer-driven aggregation, and interaction logic (e.g., recomputing a visible total when a user changes a filter) — not for computing fair value, consistency scores, pitch archetypes, or any statistically or ML-derived quantity.
- The Auction Simulator / Scenario Analysis page is the one interactive exception worth calling out: purse-allocation sliders and "what-if" comparisons in Power BI operate over a **pre-computed set of `optimization_scenarios`** (Section 9) rather than running the optimizer live inside Power BI. If the required set of interactive scenarios grows beyond what can be pre-computed, that is a signal to revisit this boundary explicitly — not a license to silently move optimization logic into DAX.

This flow keeps a single, auditable path from raw data to what a user sees, so the Methodology / Data Quality dashboard page can honestly state, for any number on screen, which pipeline stage and which analytical layer produced it (PRD §9.2, §13).

---

## 8. ML Architecture

All three models are optional-if-unjustified for Model C, but architected identically in shape: a features contract in, a target and validation strategy that respects time, and an explainability requirement out. None of the three trains on information that would not have been available as of the prediction date (no leakage from future seasons, future auctions, or future performance).

### Model A — Auction price / fair-value model

- **Features:** player-season batting/bowling features, phase and matchup splits, consistency profile, role, age, league-strength-adjusted performance, availability/experience, prior auction history (where it exists).
- **Target:** two related but distinct targets, kept separate per PRD §8.2 — (a) fair value (performance/role/scarcity-grounded) and (b) expected/observed market price (price-history-grounded). These are not collapsed into one model output.
- **Training dataset:** historical auctions with known outcomes, features computed strictly from data available before that auction date.
- **Validation strategy:** temporal validation — train on earlier auction cycles, validate/test on later ones. No random k-fold shuffling across auction years, since that would let future pricing patterns leak into training.
- **Leakage risks:** using post-auction-season performance to explain a pre-auction price; using a player's actual sale price as a feature when predicting fair value; using retrospectively-revised role labels.
- **Baseline:** a simple statistical baseline (e.g., league-adjusted performance percentile, or a regularized linear/regression model) that any ML model must beat to justify its use, per PRD §9.1.
- **Evaluation metrics:** price-prediction error (e.g., MAE/RMSE on price bands), calibration of fair-value estimates against realized outcomes where available, and — since this feeds bargain/overpayment flags — precision of the value-gap direction (bargain vs. overpay), not just point-estimate accuracy.
- **Output:** `model_predictions` rows for fair value and for expected price, kept as separate `model_name` values.
- **Explainability requirement:** SHAP-based (or equivalent) feature attribution per prediction, surfaced on the Player Profile and Auction Value dashboard pages so every valuation traces back to evidence (PRD §9.2, §12).

### Model B — Domestic-to-franchise translation model

- **Features:** domestic-competition performance profile (phase, consistency, matchup features), league-strength adjustment factor for the domestic competition, age, role.
- **Target:** franchise-level (IPL) performance profile, or a translated performance percentile, learned from players who have historically made that transition.
- **Training dataset:** the cohort of players with both domestic and subsequent franchise-level track records; features taken only from the domestic-era window, target from the subsequent franchise-era window.
- **Validation strategy:** temporal/cohort holdout — hold out a set of transition players (or a later time window of transitions) rather than random splits, to simulate predicting a genuinely new domestic entrant.
- **Leakage risks:** including any franchise-era statistic in the feature set; survivorship bias (only players who succeeded in franchise cricket are observed transitioning) must be documented as a known limitation rather than corrected for silently.
- **Baseline:** naive carry-over (assume domestic performance percentile equals franchise performance percentile) as the baseline to beat.
- **Evaluation metrics:** translated-performance prediction error against realized franchise-era outcomes for the holdout cohort.
- **Output:** `model_predictions` rows used specifically for uncapped/domestic auction entrants without an IPL track record (PRD §7.3, §9.3).
- **Explainability requirement:** attribution back to which domestic features drove the translated estimate, plus explicit disclosure of the survivorship-bias limitation on the Methodology page.

### Model C — Player similarity / clustering (optional)

- **Features:** role/style-relevant feature subset (phase splits, matchup profile, consistency profile) — deliberately excluding price/value fields, since this model answers "who plays like whom," not "who is worth what."
- **Target:** unsupervised — no single label; output is a clustering/embedding used for nearest-neighbor retrieval.
- **Training dataset:** the full evaluated player pool (or a role-specific subset) at the season/phase grain.
- **Validation strategy:** cluster stability/quality checks (e.g., silhouette score, stability under bootstrap resampling) rather than a train/test split, since there is no ground-truth label.
- **Leakage risks:** limited, since there is no forward-looking target, but season-boundary leakage (mixing pre- and post-auction-date performance for the same evaluation window) must still be avoided for consistency with the rest of the pipeline.
- **Baseline:** rule-based role bucketing (the existing `player_roles` taxonomy) as the baseline "similarity" a clustering model must add value beyond.
- **Evaluation metrics:** cluster quality metrics plus qualitative review (do same-cluster players plausibly serve the same squad need?).
- **Output:** cluster/archetype labels and nearest-neighbor lists, used to populate "strategic alternatives" (PRD §8.1) on Player Profile and Auction Simulator pages.
- **Explainability requirement:** the features that placed a player in a given cluster, and its nearest neighbors with distance/similarity scores, must be shown — not just a cluster ID.

---

## 9. Auction Optimization Architecture

**Prediction and optimization are architecturally distinct components and are never merged into one step.**

- A **model** (Section 8) produces an estimate about one player in isolation: fair value, expected price, translated performance, or similarity.
- The **optimizer** consumes many players' estimates plus RCB's current constraints and chooses among constrained alternatives to produce a recommended action (a squad, a bid ceiling, a priority order).

This separation exists so that a change in modeling methodology never silently changes optimization logic, and so that the optimizer's constraint-handling can be validated independently of any single model's accuracy.

### Optimizer inputs

- Remaining purse
- Current squad state and identified squad gaps (by role, phase, and skill type)
- Role requirements and minimum/maximum slot counts
- Overseas-player slot constraints
- Player availability (auction pool membership, injury/availability flags)
- Candidate player combinations (drawn from the 30–40-player shortlist, PRD §1.4, §10.2)
- Fair value and expected price (from Model A)
- Risk indicators (consistency profile, translation-model uncertainty for uncapped players, similarity-based fallback options)

### Optimizer outputs

- `optimization_scenarios` rows: one or more recommended squad combinations under the given constraints, each with its own purse allocation and role coverage
- Per-player maximum recommended bid (fair value plus squad-fit/scarcity adjustment, purse-constrained — kept distinct from fair value itself, per PRD §8.2)
- Alternative scenarios (e.g., prioritize an overseas death bowler vs. a domestic all-rounder) for the "what-if" comparison required by the PRD (§10.10, §11 Auction Simulator page)

### Implementation approach

OR-Tools (constraint programming or mixed-integer programming, whichever fits the specific squad-construction formulation) is used to search the constrained combination space, since exhaustively enumerating player combinations against purse/role/overseas constraints is a textbook constrained-optimization problem, not something that should be approximated by ad hoc heuristics or done manually inside Power BI.

---

## 10. Architecture Principles

- **Reproducibility:** given the same raw inputs and the same configs, every pipeline stage produces byte-identical (or numerically identical within documented tolerance) outputs. No stage depends on manual intervention.
- **Modularity:** each `src/` subpackage (ingestion, cleaning, validation, features, models, optimization, analytics) has a single responsibility and a defined input/output contract with the `data/` layer it reads from and writes to.
- **Local-first development:** the full pipeline runs on a single machine with no external service dependency at runtime (Section 2's AI-independence constraint applies at the development-tooling level only).
- **Clear data lineage:** every table in `data/features/`, `models/`, and `data/exports/` can be traced back through the pipeline stages in Section 1 to the raw source file(s) that produced it.
- **Testability:** pytest tests exist per `src/` subpackage; pandera schemas enforce contracts at every layer boundary (raw→interim, interim→processed, processed→features) so malformed data fails loudly and early rather than propagating silently.
- **Explainability:** every model output (Section 8) and every optimizer recommendation (Section 9) is accompanied by the evidence that produced it, surfaced through the Methodology / Data Quality dashboard page.
- **Minimal unnecessary infrastructure:** no component from the excluded list in Section 2 is introduced without a concrete, documented requirement that the current stack cannot satisfy.
- **Version-controlled code:** all of `src/`, `scripts/`, `configs/`, `tests/`, and documentation live in Git/GitHub.
- **Versioned datasets/metadata where practical:** processed/feature/export tables carry a generation timestamp and the config/version that produced them, so a given dashboard export can be tied back to a specific pipeline run.
- **No hidden manual transformations:** if a number needs correcting, the correction is made in a script under `src/` and re-run, never edited directly in a Parquet file, a DuckDB table, or inside Power Query/DAX.

---

## Architecture decisions that must not be changed casually

1. **The four-layer separation (descriptive → statistical → ML → optimization) is fixed.** No dashboard measure, no ad hoc script, and no future feature may blur these boundaries — for example, computing a statistical adjustment inside DAX, or letting an optimizer output silently overwrite a descriptive feature table.
2. **Power BI is a presentation layer, not a computation layer.** Fair value, consistency scores, pitch archetypes, league-strength adjustments, and any ML output are always computed upstream in Python/DuckDB and delivered to Power BI as finished exports.
3. **Fair value, expected/observed price, and maximum recommended bid remain three distinct, separately stored figures** (PRD §8.2). They must never be collapsed into a single "recommended price" field anywhere in the data model or the dashboard.
4. **Prediction and optimization remain separate components with separate inputs/outputs** (`model_predictions` vs. `optimization_scenarios`). A model never directly emits a squad recommendation; an optimizer never directly emits a player valuation.
5. **Venue, match environment, and pitch archetype remain conceptually and structurally separate entities** (`venues` vs. match-level environment fields vs. `pitch_archetypes`), per PRD §6.1. They are never merged into a single "venue behavior" table.
6. **No model trains on information unavailable as of its prediction date.** Temporal validation is mandatory for Models A and B; any future change to validation strategy that would allow lookahead is out of bounds without an explicit, documented exception.
7. **`data/raw/` is immutable.** All corrections happen downstream in versioned code, never by editing raw source files.
8. **The excluded technology list (PostgreSQL, MongoDB, Spark, Kafka, Docker, cloud infrastructure, microservices) stays excluded** unless a specific, documented requirement demonstrates that the current DuckDB/Parquet/pandas stack cannot meet it. Scaling anxiety or general "best practice" is not sufficient justification on its own.
9. **The system has no proprietary-AI-service runtime dependency.** AI coding assistants remain development-time tools only; removing them must never break ingestion, features, models, optimization, or the dashboard.
10. **The candidate shortlist width (30–40 players, PRD §1.4) is a data-pipeline and dashboard-filtering requirement, not just a display choice**, and any architectural change (e.g., feature-table grain, export sizing) must continue to support that breadth rather than silently optimizing only for a top-5 view.
