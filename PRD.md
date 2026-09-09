# RCB Auction Intelligence Engine — Product Requirements Document

**Document status:** Draft v1.0
**Document owner:** Product/Data Architecture
**Project type:** Independent data-science portfolio project

---

## 0. Disclaimer

This is an **independent, unaffiliated analytical portfolio project**. It is not commissioned by, endorsed by, or connected to Royal Challengers Bengaluru (RCB), the BCCI, the IPL, or any franchise. "RCB" is used purely as a fixed case-study franchise to give the project a concrete decision-making context. No proprietary team data, internal scouting reports, or confidential information is used or implied. All data is sourced from public ball-by-ball and auction records.

---

## 1. Product Vision

### 1.1 Vision statement

The RCB Auction Intelligence Engine is a context-aware player evaluation and auction decision-support system. It exists to answer one question with rigor rather than vibes:

> **Which players should RCB target at auction, why do they fit the squad, how much should RCB reasonably bid, and which players represent potential value or overpayment risk?**

### 1.2 What this product is not

This is explicitly **not** a generic IPL statistics dashboard. A stats dashboard answers "what happened." This product answers "what should we do about it, and how confident should we be." Every feature, metric, and model in this PRD must trace back to a decision RCB's think-tank would actually need to make during auction preparation: squad gaps, shortlists, valuation, and bid strategy.

### 1.3 Core differentiators

The product distinguishes itself through **context-aware evaluation**, meaning no raw number is presented without the context required to interpret it:

- Ball-by-ball granularity instead of scorecard-level aggregates
- Phase-of-innings performance instead of match-level totals
- Pitch/venue environment adjustment instead of venue-agnostic stats
- Matchup-specific performance (vs. pace/spin, vs. batter/bowler types)
- Consistency and distribution analysis instead of averages alone
- Domestic-to-franchise translation modelling for uncapped/emerging players
- League-strength adjustment instead of treating all T20 leagues as equivalent
- Explicit linkage to RCB's squad requirements and role scarcity
- Auction economics: fair value vs. market price vs. maximum rational bid
- ML used selectively, only where it demonstrably improves a decision
- Budget- and roster-constrained optimization for final squad recommendations

### 1.4 Candidate breadth requirement

The system must resist the temptation to jump straight to a "top 5." Auction rooms need option depth, backup plans, and contingencies. The product must therefore support discovery and evaluation of a **candidate universe that narrows into a serious shortlist of roughly 30–40 players**, not merely 5–10 marquee names. This is a first-class product requirement, not an implementation detail — it affects data pipeline scope, dashboard filtering, and ranking design throughout.

---

## 2. Target Users

### 2.1 Primary users

| User | What they need from the product |
|---|---|
| Cricket analytics enthusiasts | A credible, well-reasoned model of how professional auction analysis could work |
| Franchise strategy analysts (persona) | Squad-gap-driven shortlists, matchup and pitch intelligence, bid ceilings |
| Data analysts / data scientists | A worked example of the descriptive → statistical → ML → optimization pipeline on real sports data |
| Portfolio reviewers / interviewers | Evidence of end-to-end thinking: problem framing, data engineering, modelling judgment, and communication |

### 2.2 Secondary users

- Cricket fans who want a deeper, more analytical view of auction decisions than punditry provides
- Students learning sports analytics who want a reference implementation of a real-world evaluation pipeline
- Fantasy-cricket and cricket-strategy researchers looking for matchup and phase-level insights (as a byproduct, not a target use case)

### 2.3 Explicit positioning statement

> This project is an independent analytical and educational exercise. It uses RCB as a fixed case study to demonstrate context-aware player evaluation methodology. It is not an official RCB tool, is not used by RCB, and makes no claim of insider knowledge or franchise endorsement.

This statement must appear on the dashboard's landing page and in any shared write-up.

---

## 3. Core Product Questions

The system's success is measured by whether it can produce a defensible, evidence-backed answer to each of the following. Every downstream module in this PRD exists to answer one or more of these:

1. What are RCB's biggest squad gaps (by role, phase, and skill type)?
2. Which player profiles would solve those gaps?
3. Which players perform consistently, rather than producing only occasional standout performances?
4. How does a player perform under different pitch/venue environments?
5. How does a player perform in different match phases (powerplay, middle, death)?
6. How does a batter perform against pace vs. spin and against different bowling sub-types?
7. How does a bowler perform against different batter types (LHB/RHB, aggressive/anchor)?
8. How well does a player's domestic performance translate to franchise-level competition?
9. What is the player's estimated fair auction value?
10. What is the estimated market/auction price for that player?
11. Is the player potentially undervalued or overvalued relative to fair value?
12. What is RCB's maximum rational bid for that player?
13. What squad combinations can be assembled under purse and roster constraints?
14. How does the recommended auction strategy compare against plausible alternative strategies?

---

## 4. Player Evaluation Dimensions

Feature collection is **conditional on sample size**. A metric is only reported when the underlying sample (balls faced, overs bowled, matches played) clears a minimum-sample threshold defined in the Methodology page (Section 11) and Data Quality framework (Section 13). Below that threshold, the metric is withheld or explicitly flagged as low-confidence rather than silently displayed. The product must never invent a metric for which the underlying data does not exist — if a data source lacks a dimension (e.g., no ball-tracking for wagon-wheel data), that dimension is simply out of scope, not approximated.

### 4.1 Batting dimensions

**Volume and rate**
- Runs, balls faced
- Batting average, strike rate
- Dot-ball percentage
- Boundary percentage, boundary dependency (share of runs from boundaries vs. rotation)
- Singles/doubles/rotation rate

**Phase performance**
- Powerplay performance (overs 1–6)
- Middle-overs performance (overs 7–15)
- Death-overs performance (overs 16–20)
- Scoring acceleration (rate of strike-rate change as an innings progresses)

**Innings-shape / milestone rates**
- 20+, 30+, 40+, 50+, 75+ scoring rate (share of innings reaching each threshold)
- Median innings score
- Percentile scoring distribution (e.g., P10/P25/P50/P75/P90)
- Low-score frequency (e.g., share of innings under a defined threshold)
- High-score / ceiling frequency

**Situational**
- Dismissal patterns (bowling type, phase, shot-adjacent context where derivable from ball-by-ball data)
- Performance while chasing vs. setting a target
- Performance under high required run rate
- Performance in close games (defined by margin/context)

**Matchup and context**
- Performance against pace vs. spin
- Performance against bowling sub-types where sample size permits (e.g., left-arm pace, wrist-spin)
- Venue-adjusted performance
- Pitch-environment-adjusted performance

### 4.2 Bowling dimensions

**Volume and rate**
- Wickets, balls bowled, runs conceded
- Economy rate, bowling strike rate
- Dot-ball percentage, boundary-concession rate
- Wicket rate (wickets per over/per balls)

**Phase performance**
- Powerplay, middle-overs, death-overs performance

**Spell-shape / milestone rates**
- 1+, 2+, 3+ wicket rate (share of spells reaching each threshold)
- Economy consistency (distribution of economy across spells)
- Best/worst spell distribution

**Matchup and context**
- Performance against LHB vs. RHB
- Performance against batter styles/types where data permits (e.g., anchors vs. power-hitters, derived from opponent scoring profile)
- Pace/spin-specific matchup performance where meaningful (e.g., a spinner's effectiveness against players who struggle vs. spin)
- Venue-adjusted and pitch-environment-adjusted performance
- Pressure performance (performance in defined high-leverage situations — close games, death overs defending a small total, etc.)
- Runs prevented relative to environment/expectation (a bowler's economy relative to what an average bowler would concede in the same phase/venue/pitch context)

### 4.3 Fielding and availability dimensions

- Catch involvement (catches taken, chances where derivable)
- Run-outs (direct hits and run-outs involved in, where attributable)
- Wicketkeeping contribution where relevant (dismissals, byes conceded, stumping rate)
- Availability: matches missed, injury history where publicly known
- Role flexibility (can bat in multiple positions, can bowl multiple phases, keeper who can also bat top-order, etc.)
- Age (career-stage context for value and risk assessment)
- Domestic / franchise / international experience (breadth and volume of competitive exposure)

**Explicit constraint:** if a metric listed anywhere in this section cannot be reliably computed from available data sources (e.g., true fielding-chance data is rarely available at ball-by-ball granularity), the PRD requires that this be documented as a known limitation rather than filled with a proxy presented as ground truth.

---

## 5. Consistency Framework

### 5.1 Why averages are insufficient for auction decisions

A batting average or economy rate collapses an entire season into one number, discarding the shape of the underlying distribution. Two players can have identical averages while one delivers dependable 30s every match and the other alternates between ducks and centuries. For a franchise allocating a fixed, scarce auction purse, the **distribution of outcomes matters as much as the central tendency**, because:

- A reliable "floor" performer reduces variance in a chase or defense
- A high-ceiling but inconsistent performer may be a bargain in some phases of a tournament and a liability in others
- Overpaying for a high-average player who is actually "boom-or-bust" is a common and avoidable auction mistake

The consistency framework exists specifically to prevent this mistake and must be treated as a first-class evaluation layer, not a supplementary chart.

### 5.2 Required consistency metrics

**Batting**
- Median innings score (robust to outlier big scores)
- Percentile distribution of innings scores (P10, P25, P50, P75, P90)
- 20+/30+/40+/50+ contribution rate (frequency of clearing each threshold)
- Distribution shape of scores (visualized, not just summarized) — e.g., histogram or ridge plot per player
- Frequency of very low scores (a defined "failure rate," e.g., share of innings under 10 runs off a meaningful number of balls)
- Frequency of high-impact performances (share of innings above a defined match-winning threshold, contextualized by team total/required rate where feasible)

**Bowling (analogous framework)**
- Median wickets per spell and median economy per spell
- Percentile distribution of both wickets and economy across spells
- 1+/2+/3+ wicket contribution rate
- Frequency of "damage" spells (economy above a poor threshold for the phase)
- Frequency of "match-defining" spells (2+ wickets at or below a strong economy threshold for the phase)

### 5.3 Output requirement

Every player profile must present a **consistency score or badge** (e.g., "high floor / moderate ceiling," "boom-or-bust," "elite floor and ceiling") derived transparently from the above distributions — never as an unexplained black-box label. The methodology for deriving the badge must be documented and reproducible.

---

## 6. Pitch and Venue Intelligence

### 6.1 Conceptual separation

The system must not conflate the following, even though they are correlated in practice:

| Concept | Definition |
|---|---|
| **Venue** | The physical ground (e.g., M. Chinnaswamy Stadium) |
| **Match environment** | Conditions specific to that match — weather, dew, day/night, toss outcome |
| **Pitch archetype** | An empirically derived cluster describing how the surface actually played |
| **Phase** | Segment of the innings (powerplay/middle/death) — pitch behavior can differ meaningfully by phase |
| **Opposition/context** | Quality and style of the opposition, which can confound raw venue statistics |

Treating "venue" as a proxy for "pitch behavior" is a common analytical error this product must explicitly avoid — the same venue can play very differently match to match (re-laid pitch, dew-heavy vs. dry, day vs. night).

### 6.2 Data-driven pitch classification

Pitch archetypes must be derived from observed match data (e.g., first-innings scoring rate, boundary frequency, wicket fall rate by phase, spin vs. pace effectiveness in that match) using clustering or rule-based bucketing grounded in that data — **not** assigned from commentary, punditry, or unverified third-party pitch reports. Candidate archetypes include, but are not limited to:

- High-scoring / batting-friendly
- Low-scoring / bowling-friendly
- Pace-friendly
- Spin-friendly
- Two-paced / low-boundary ("tricky" surfaces)
- Additional clusters empirically discovered through the data (the taxonomy above is a starting hypothesis, not a fixed constraint on the clustering output)

### 6.3 Handling uncertainty

Where a match or venue has insufficient data to confidently assign a pitch archetype (e.g., only one or two historical matches, rain-affected data, mixed signals), the system must **preserve and surface that uncertainty** — e.g., an explicit "insufficient data / unclassified" label — rather than force-fitting a confident-looking category. Every pitch classification shown to a user must be accompanied by a confidence indicator or sample-size disclosure.

---

## 7. League and Competition Coverage

### 7.1 Required coverage

- IPL (primary competition of interest, since this is the auction context)
- Major franchise T20 leagues (e.g., BBL, CPL, SA20, ILT20, MLC, The Hundred) where data is available
- Relevant Indian domestic T20 cricket (Syed Mushtaq Ali Trophy and similar) — critical for evaluating uncapped/domestic auction entrants
- Other useful domestic T20 competitions where data quality supports inclusion
- International T20 cricket where useful for contextualizing a player's ceiling and big-match experience

### 7.2 Primary data source

**Cricsheet** is the primary ball-by-ball data source across competitions, supplemented by publicly available auction price history and player biographical/role data where Cricsheet does not cover it.

### 7.3 Cross-league comparability

Different competitions vary substantially in bowling depth, pitch conditions, and overall standard. The product must **not treat raw numbers across leagues as directly comparable**. This requires:

- A league-strength/context adjustment layer applied before cross-league comparison
- Explicit labeling of which league(s) underlie any given statistic shown
- Special handling for domestic-to-franchise translation (see Section 9), since this is the single most auction-relevant cross-context comparison RCB would need (evaluating uncapped Indian players who have no IPL track record)

---

## 8. Auction Intelligence

### 8.1 Required outputs per candidate player

| Output | Description |
|---|---|
| Estimated fair value | Model-based valuation of what the player is objectively worth given performance, role, and scarcity |
| Expected/observed auction price | Historical price for retained/previously-auctioned players, or a predicted price band for new entrants |
| Value gap | Fair value minus expected/observed price |
| Potential bargain flag | Players whose fair value meaningfully exceeds expected price |
| Potential overpayment flag | Players whose expected price meaningfully exceeds fair value |
| Maximum recommended bid | The ceiling RCB should rationally pay, accounting for fair value, squad fit, and remaining purse |
| Squad-fit score | How well the player's profile addresses RCB's identified gaps (Section 3, Q1–Q2) |
| Role scarcity adjustment | Premium/discount applied based on how rare the player's role/profile is in the available pool |
| Budget constraint | Player valuation considered against remaining purse and roster slots |
| Overseas-player constraint | Explicit handling of overseas-slot limits in squad-building logic |
| Strategic alternatives | Comparable players who could fulfill the same role need, for contingency planning |

### 8.2 Guiding principle

Fair value and maximum bid are **not the same number**. Fair value is an estimate of a player's objective worth; maximum bid additionally factors in how badly RCB needs that specific role, how scarce the alternatives are, and how much purse remains. The PRD requires these to be modeled and displayed as distinct figures, never merged into one undifferentiated "recommended price."

---

## 9. ML Requirements

### 9.1 Guiding principle

> ML is used only where it demonstrably improves a decision relative to simpler statistical or descriptive methods. The project must never use ML merely to claim "this project uses AI."

### 9.2 Required separation of analytical layers

The PRD requires the pipeline to be explicitly and visibly separated into four layers, each with a distinct purpose:

| Layer | Purpose | Example in this project |
|---|---|---|
| **Descriptive analytics** | Summarize what happened, without inference or prediction | Phase-wise strike rate, dismissal breakdowns, raw milestone rates |
| **Statistical modelling** | Quantify relationships, adjust for context, test significance/uncertainty | Venue/pitch adjustment via regression, percentile-based consistency scoring, league-strength adjustment factors |
| **Machine learning** | Learn patterns too complex for hand-specified rules, where justified by data volume and decision value | Auction price prediction, domestic-to-franchise translation, player similarity/clustering |
| **Optimization** | Turn valuations and constraints into an actionable decision | Squad-construction optimization under purse and roster constraints |

Every model or metric in the product must be traceable to exactly one of these four layers, and the dashboard's Methodology page (Section 11) must state which layer produced each output shown to the user.

### 9.3 Candidate ML use cases

- **Auction price prediction** — predicting a likely price band from player performance, role, age, and historical auction price patterns
- **Fair-value estimation** — a valuation model distinct from price prediction, grounded in performance and role scarcity rather than market sentiment
- **Domestic-to-franchise translation** — modelling how a domestic-competition performance profile is likely to translate to IPL-level competition, using players who have made that transition as training examples
- **Player clustering** — grouping players into role/style archetypes (e.g., "death-overs finisher," "new-ball swing bowler") to support like-for-like comparison and scarcity analysis
- **Similar-player identification** — nearest-neighbor style retrieval to surface strategic alternatives (Section 8.1)

### 9.4 Non-requirements

The PRD explicitly does **not** require deep learning, black-box ensembles, or any model whose primary justification is technical impressiveness rather than decision value. Simpler, well-validated, explainable models (e.g., regularized regression, gradient-boosted trees with SHAP explainability, k-means/hierarchical clustering) are preferred defaults unless a specific use case demonstrates the need for more complexity.

---

## 10. Final Outputs

The finished system must produce the following deliverables:

1. **Candidate universe** — the full pool of players considered before narrowing
2. **30–40-player shortlist** — the serious candidate list, spanning multiple roles and price tiers
3. **Role-specific rankings** — rankings within each role category (e.g., top-order batter, death bowler, all-rounder, wicketkeeper-batter)
4. **Player profiles** — individual pages combining all evaluation dimensions for a given player
5. **Pitch/environment profiles** — venue and pitch-archetype summaries
6. **Matchup profiles** — pace/spin and batter/bowler-type matchup breakdowns
7. **Fair-value estimates** — per-player valuation output
8. **Auction strategy** — the overall recommended approach to the auction (priority order, purse allocation philosophy)
9. **Maximum bid recommendations** — per-player bid ceilings
10. **Alternative auction scenarios** — "what if" strategies (e.g., prioritize overseas death bowler vs. prioritize domestic all-rounder)
11. **Recommended squad combinations** — final optimized squad(s) under constraints
12. **Power BI dashboard** — the interactive presentation layer (Section 11)
13. **Presentation-ready findings** — a summarized narrative/slide-style output suitable for a portfolio review or interview walkthrough

---

## 11. Dashboard Requirements (Power BI)

The dashboard must **prioritize decision-making over decorative visualization**. Every page must exist to answer one or more of the Core Product Questions (Section 3); pages that merely display statistics without supporting a decision are out of scope.

| Page | Purpose | Key content |
|---|---|---|
| **Executive Overview** | One-screen summary for a decision-maker | Top squad gaps, top shortlisted candidates, headline recommendations |
| **Squad Gap Analysis** | Diagnose RCB's current roster weaknesses | Role/phase coverage map, current squad performance by phase, identified gaps |
| **Player Discovery** | Browse and filter the 30–40 candidate shortlist | Filters by role, league, price band, squad-fit score |
| **Player Profile** | Deep dive on a single player | Full evaluation dimensions, consistency badge, career trajectory |
| **Batting Intelligence** | Batting-specific analytical depth | Phase performance, milestone rates, distribution charts, matchup breakdowns |
| **Bowling Intelligence** | Bowling-specific analytical depth | Phase performance, wicket-rate distributions, matchup breakdowns |
| **Pitch/Venue Intelligence** | Environment context | Pitch archetype clusters, venue behavior, confidence/uncertainty indicators |
| **Matchup Intelligence** | Head-to-head style analysis | Pace vs. spin, batter-type vs. bowler-type performance grids |
| **Auction Value** | Valuation transparency | Fair value, expected price, value gap, bargain/overpayment flags |
| **Auction Simulator / Scenario Analysis** | Interactive "what-if" exploration | Purse allocation sliders, alternative strategy comparison |
| **Final Recommendations** | The answer to the core product questions | Shortlist, bid ceilings, recommended squad combination(s) |
| **Methodology / Data Quality** | Transparency and trust | Data sources, sample-size thresholds, model layer attribution (Section 9.2), known limitations |

---

## 12. Non-Goals

This project explicitly is **not**:

- An official RCB prediction system or endorsed franchise tool
- A betting or gambling-adjacent system
- A fantasy-cricket prediction product
- A live, transactional auction platform
- A guarantee of future player performance
- A black-box AI recommendation engine — every recommendation must be explainable back to its underlying evidence
- A replacement for professional scouting, medical assessment, or on-ground franchise judgment

---

## 13. Success Criteria

Success is defined by the following measurable, evaluable criteria rather than by feature count:

| Dimension | Criterion |
|---|---|
| **Data reliability** | Data sources are documented, sample-size thresholds are enforced, and known gaps/limitations are disclosed rather than hidden |
| **Reproducibility** | Given the same source data, the pipeline (descriptive → statistical → ML → optimization) produces the same outputs; all transformation logic is version-controlled and documented |
| **Statistical validity** | Consistency metrics, adjustments, and model outputs are grounded in defensible methodology (appropriate sample sizes, disclosed confidence, no overfitting presented as certainty) |
| **Explainability** | Every recommendation, valuation, or ranking can be traced back to the specific evidence and model layer that produced it |
| **Useful shortlist generation** | The 30–40-player shortlist spans genuinely distinct roles, price tiers, and risk profiles rather than clustering around a few obvious names |
| **Reasonable model validation** | ML components (price prediction, translation modelling, clustering) are validated with appropriate train/test discipline and error reporting, not just fit-and-display |
| **Dashboard usability** | A first-time reviewer can navigate from squad gaps to a specific bid recommendation without external explanation |
| **Interview-readiness** | The project can be walked through end-to-end in a portfolio review, with clear articulation of design decisions, trade-offs, and limitations |
| **Reproducible results** | Re-running the pipeline on refreshed data produces coherent, comparably structured outputs without manual patching |

---

## Product Principle

> **Optimize for evidence, explainability, reproducibility and decision usefulness — not for the largest number of metrics or the most complicated model.**
