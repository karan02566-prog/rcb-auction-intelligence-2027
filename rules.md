# Project Rules

This document is the strict engineering and analytical constitution for the entire project.

Any future AI coding agent must read this before changing the project.

## 1. General rule

The project must prioritize:

1. Correctness
2. Data integrity
3. Reproducibility
4. Explainability
5. Maintainability
6. Visual quality

Never prioritize speed of coding above correctness.

## 2. Data rules

Primary raw ball-by-ball data should preferably come from Cricsheet.

Supplement with official competition/board sources where necessary.

Use reputable sources for:

- Auction prices
- Player information
- Squad information
- Availability
- Competition metadata

Never invent statistics.

Never silently fill missing statistics.

Never treat scraped data as reliable merely because it exists online.

Every external dataset must have documented:

- Source
- URL/location
- Retrieval date
- Competition
- Seasons
- Format
- Known limitations

## 3. Data provenance

Every important derived metric must be traceable to source data.

Maintain a data dictionary containing:

- Feature name
- Definition
- Formula
- Input fields
- Unit
- Aggregation level
- Population
- Minimum sample
- Missing-data behavior

## 4. Statistical rules

Never compare players using raw statistics without considering context when context materially changes interpretation.

Consider:

- Season
- League
- Venue
- Phase
- Opposition
- Batting position
- Bowling phase
- Sample size
- Match situation

Do not manufacture statistical significance.

Do not use averages alone when distributions matter.

Use:

- Median
- Percentiles
- Rates
- Distribution
- Confidence/uncertainty where practical

## 5. Pitch rules

Never label pitches arbitrarily.

Prefer empirical venue/match-environment classification.

Any pitch classification must document:

- Inputs
- Method
- Thresholds or clustering approach
- Limitations

A third-party pitch label can be used as supplemental evidence but must not automatically become ground truth.

## 6. Minimum-sample rules

Create explicit sample thresholds.

Examples:

- Minimum batting balls
- Minimum innings
- Minimum bowling balls
- Minimum matchup deliveries
- Minimum venue observations

Small samples must be visibly flagged.

Never rank a player highly based on 8 deliveries against a particular bowling type.

## 7. Feature-engineering rules

Prefer transparent feature formulas.

Examples:

```
20+ rate
30+ rate
50+ rate
Median innings score
Dot-ball %
Boundary %
Rotation %
Phase-adjusted performance
Venue-adjusted performance
Runs above/below expected environment
Wicket rate
Death-over economy
Matchup performance
```

Do not create a metric simply because it sounds sophisticated.

Every custom metric needs:

- Definition
- Formula
- Reason for inclusion
- Interpretation
- Known limitations

## 8. ML rules

ML is allowed only when it solves a real analytical problem.

Allowed:

- Regression
- Gradient boosting
- Random forest
- Classification
- Clustering
- Player similarity
- Optimization

Deep learning is prohibited unless a later phase proves it is genuinely necessary.

Always create a simple baseline before an advanced model.

Always evaluate out-of-sample.

Avoid target leakage.

Use temporal validation for future-oriented auction predictions.

Record:

- Model version
- Features
- Training period
- Validation period
- Hyperparameters
- Metrics
- Baseline
- Limitations

Never claim:

> "The model knows who will succeed."

Instead describe probability, estimated value or expected performance.

## 9. Optimization rules

Do not confuse ML prediction with auction strategy.

ML:

> estimates value/performance.

Optimization:

> selects combinations under constraints.

Auction recommendations must expose the assumptions behind the recommendation.

## 10. Error handling

Python code must:

- Fail loudly on corrupted critical data
- Produce clear error messages
- Validate schemas
- Handle missing optional fields gracefully
- Avoid swallowing exceptions
- Log important failures
- Never silently substitute fabricated values

Use appropriate exceptions.

Validate inputs before expensive processing.

## 11. Coding standards

Use:

- Type hints where useful
- Docstrings for important functions
- Small functions
- Descriptive names
- No duplicated business logic
- Configuration instead of magic numbers
- Unit tests for formulas
- Deterministic random seeds for ML where practical

Keep notebooks for exploration.

Move reusable production logic into `src/`.

## 12. AI-agent boundaries

AI coding agents may:

- Generate boilerplate
- Refactor code
- Explain code
- Write tests
- Suggest models
- Analyze errors
- Improve documentation
- Generate SQL/Python/DAX drafts

AI agents may NOT:

- Invent data
- Invent sources
- Change metric definitions silently
- Delete project requirements
- Remove validation merely to make code pass
- Replace real data with fake demo data without explicit permission
- Change architecture without documenting it
- Add dependencies without justification
- Claim a model is accurate without evaluation
- Make unsupported cricket claims
- Modify `memory.md` history destructively
- Commit code without checking tests/status

Gemini 3.7 Flash may be used as a coding/reasoning assistant. AI-generated code remains untrusted until reviewed and tested.

## 13. Dependencies

Prefer:

- pandas
- numpy
- duckdb
- pyarrow
- scikit-learn
- xgboost when justified
- scipy
- matplotlib
- plotly where useful
- pytest
- pandera where useful
- ortools where optimization requires it

Do not install packages merely because an AI suggested them.

Before adding a dependency, answer:

1. Why is it needed?
2. Can the current stack already solve this?
3. Is it maintained?
4. Does it complicate deployment?
5. Does it materially improve the project?

## 14. Git rules

Commit after every subphase.

Commits must be meaningful.

Prefer:

```
feat(data): add Cricsheet ingestion
feat(features): add batting consistency metrics
feat(model): add auction value baseline
feat(powerbi): add player discovery page
fix(validation): handle duplicate deliveries
docs(memory): update phase status
```

Never make meaningless commits such as:

```
update
changes
final
done
stuff
```

## 15. Definition of done

Nothing is "done" until:

- Code runs
- Tests pass
- Outputs are inspected
- Data quality checks pass
- Documentation is updated
- `memory.md` is updated
- Git status is clean or intentionally documented

End with:

> **When uncertain, preserve data integrity and explainability over convenience.**
