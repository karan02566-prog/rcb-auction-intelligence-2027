# RCB Auction Intelligence Engine — Visual Design Specification (`design.md`)

This document defines the visual architecture, typography, semantic color system, and layout design rules for the RCB Auction Intelligence Engine. All dashboard pages, visual components, data exports, and presentation decks must strictly adhere to this specification.

---

## 1. Brand Direction & Visual Identity

The project visual identity is an **executive-level sports analytics platform**. It borrows the deep red and dark charcoal tones associated with RCB to establish instant domain context, but maintains strict separation from official franchise assets.

* **Project Name:** RCB Auction Intelligence Engine
* **Visual Identity Feeling:** Executive analytics, sports intelligence, professional data science, clean editorial dashboard.
* **Prohibited Visual Anti-Patterns:**
* Do NOT create a flashy fantasy-cricket or gamified UI.
* Do NOT copy official RCB logos, copyrighted team emblems, or IPL graphics.
* Do NOT use bright neon accents, glossy 3D buttons, or stadium background wallpapers.
* Do NOT use heavy decorative drop shadows or saturated background gradients.



---

## 2. Color System

The palette is restrained, professional, and built on high contrast. Dashboard views must never use more than five distinct colors simultaneously.

| Role | Color Name | Hex Code | RGB | Usage Guidance |
| --- | --- | --- | --- | --- |
| **Canvas Background** | Light Neutral | `#F8F9FA` | `248, 249, 250` | Default background for all Power BI pages and slide decks |
| **Card Container** | Pure White | `#FFFFFF` | `255, 255, 255` | Container fill for charts, KPI cards, and data tables |
| **Primary Text / Dark** | Deep Charcoal | `#1E1E1E` | `30, 30, 30` | Main headings, body text, primary data points, dark card containers |
| **Primary Accent** | Deep RCB Red | `#D11A2A` | `209, 26, 42` | Primary brand accent, focused highlights, active navigation state |
| **Strategic Highlight** | Muted Gold | `#D4AF37` | `212, 175, 55` | Primary recommended target, top-tier gap selection, marquee callout |
| **Secondary Text / Neutral** | Slate Grey | `#6C757D` | `108, 117, 125` | Secondary text, gridlines, axis labels, unselected chart elements |
| **Value / Positive Indicator** | Positive Green | `#16A34A` | `22, 163, 74` | Bargain status, positive value gap ($\text{Fair Value} > \text{Price}$), high floor |
| **Risk / Warning Indicator** | Risk Red-Orange | `#DC2626` | `220, 38, 38` | Overpayment risk ($\text{Price} > \text{Fair Value}$), high variance, vulnerability |

---

## 3. Typography System

The typography scale balances data readability with clear information hierarchy. Decorative, script, or stylized display fonts are strictly prohibited.

```
Font Hierarchy Rules:
├── Primary Sans-Serif : Inter (Fallback: Segoe UI, Arial)
└── Primary Monospace  : JetBrains Mono (Fallback: Consolas, Monospace)

```

| Element Type | Font Family | Size (pt) | Weight | Line Spacing | Usage Context |
| --- | --- | --- | --- | --- | --- |
| **KPI Display Number** | JetBrains Mono | 28 – 36 | Bold (700) | 1.1 | Top-level summary metrics, purse values, bid ceilings |
| **Page / Section Header** | Inter | 18 – 22 | Bold (700) | 1.2 | Page titles, primary quadrant section titles |
| **Card Title** | Inter | 12 – 14 | SemiBold (600) | 1.3 | Individual card container titles, modal headers |
| **Table Header / Label** | Inter | 10 – 11 | Medium (500) | 1.3 | Column headers, filter labels, axis titles |
| **Body / Data Text** | Inter | 10 – 11 | Regular (400) | 1.4 | Paragraph text, narrative descriptions, table cells |
| **Code / Micro Value** | JetBrains Mono | 9 – 10 | Regular (400) | 1.2 | Data IDs, sample indicators, footnotes, confidence tags |

---

## 4. Power BI Dashboard Layout & Structural Grid

### Canvas Specifications

* **Aspect Ratio:** 16:9 widescreen ($1920 \times 1080\text{ px}$ target canvas size).
* **Outer Canvas Margin:** $16\text{ px}$ uniform margin around the entire report page.
* **Card Container Padding:** $12\text{ px}$ internal padding inside every card container.
* **Grid Spacing / Gap:** $12\text{ px}$ fixed gap between adjacent containers.

### Grid & Layout Structure

Every dashboard page follows a strict 12-column grid layout with three vertical zones:

1. **Control & Header Strip (Top 0–12% Height):** Page title, subtitle, global slicers (Role, Overseas Status, Price Band), and high-level summary KPI cards.
2. **Main Analytical Quadrant (Middle 12–85% Height):** Primary data visuals, ranking tables, distribution plots, and scenario comparisons.
3. **Context & Methodology Footer (Bottom 85–100% Height):** Dynamic narrative summary, sample size warnings, model attribution, and disclaimer tags.

### Navigation & Tooltips

* **Navigation:** Left-aligned collapsed sidebar ($60\text{ px}$ width) or top horizontal tab strip with muted grey inactive icons and a Deep Red (`#D11A2A`) active underline.
* **Tooltips:** Custom dark-themed hover cards (`#1E1E1E` background, `#FFFFFF` text) presenting a maximum of 4 key context metrics (e.g., Deliveries Sample, Consistency Score, Model Confidence, SHAP Key Driver).

---

## 5. Player Profile Layout Architecture

A player profile must communicate the player's core value proposition within **3 seconds**, followed by detailed evidence for deeper inspection.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ PLAYER HEADER: Name, Role, Age, Country, Overseas Status | RCB Fit Score: 88/100 (Gold) │
├───────────────────────────────┬───────────────────────────────┬────────────────────────┤
│ VALUATION STRIP               │ FAIR VALUE: ₹8.5 Cr           │ MAXIMUM BID: ₹9.5 Cr   │
│ Expected Price: ₹6.0 Cr       │ Value Gap: +₹2.5 Cr (Green)   │ Recommendation: TARGET │
├───────────────────────────────┴───────────────────────────────┴────────────────────────┤
│ QUADRANT 1: Performance & Consistency  │ QUADRANT 2: Tactical & Pitch Fit               │
│ • Distribution Ridge Plot (P10–P90)   │ • Phase Split Bar Chart (PP / Middle / Death)  │
│ • Median Score vs Average             │ • Pitch Archetype Performance Matrix           │
│ • Consistency Badge: High Floor       │ • Pace vs Spin Matchup Breakdown               │
├───────────────────────────────────────┼────────────────────────────────────────────────┤
│ QUADRANT 3: Risk & Model Drivers      │ QUADRANT 4: Strategic Backup Mapping           │
│ • SHAP Valuation Drivers (Top + / -)  │ • Model C Nearest Neighbors (Top 3 Alternatives)│
│ • Injury / Availability Risk Tag      │ • Price / Skill Trade-off Comparison           │
└───────────────────────────────────────┴────────────────────────────────────────────────┘

```

---

## 6. Data Visualization Principles

### Required Visual Types

* **Ranking & Comparisons:** Tables with embedded micro-bars, dumbbell plots for value gaps.
* **Distributions & Variance:** Ridge plots, box plots, percentile range charts (P10–P90).
* **Valuation & Correlations:** Scatter plots with 4-quadrant reference overlays (Bargain vs Overpay).
* **Phase & Skill Splits:** Horizontal bar charts, small multiples.
* **Progress & Targets:** Bullet visuals, progress bars against squad gap benchmarks.

### Formatting Rules

* **Axes & Units:** Currency always formatted in Indian Rupees ($\text{₹ Cr}$ or $\text{₹ Lakh}$). Percentages formatted to 1 decimal place ($64.2\%$).
* **Direct Labeling:** Place data labels directly on bars/points where space permits; avoid redundant legend boxes.
* **Prohibited Visual Elements:**
* 3D charts of any kind.
* Pie charts or donut charts with more than 3 slices.
* Non-zero baseline truncations on bar charts (misleading scales).
* Decorative background images or chart watermarks.
* Fake precision (e.g., listing bid ceilings as $\text{₹ 8.43219 Cr}$).



---

## 7. Semantic Color Encodings

Color choices must maintain identical meanings across all dashboard pages:

```
Semantic Color Mapping:
├── Green  (#16A34A) ──> Positive Value Gap / Bargain Target / High Floor / Strong Advantage
├── Red    (#DC2626) ──> Overpayment Risk / High Failure Rate / Critical Matchup Weakness
├── Gold   (#D4AF37) ──> Primary Strategic Recommendation / Selected Gap Target / Marquee Choice
├── Grey   (#6C757D) ──> Neutral Baseline / Benchmark Average / Unselected Candidates
└── Charcoal (#1E1E1E) ──> Primary Data Points / Active Selection Focus

```

---

## 8. Candidate Ranking & Comparison Visuals

Candidate comparison views must align all evaluation dimensions side-by-side in a single structured matrix view:

| Candidate | Role | RCB Fit | Fair Value | Expected Price | Value Gap (Dumbbell) | Consistency | Max Bid | Action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Player A** | Death Bowler | $92/100$ | $\text{₹ }8.5\text{ Cr}$ | $\text{₹ }6.0\text{ Cr}$ | `[---●=====>]` ($+\text{₹ }2.5\text{Cr}$) | High Floor | $\text{₹ }9.5\text{ Cr}$ | **TARGET** |
| **Player B** | Spin All-Rounder | $78/100$ | $\text{₹ }4.0\text{ Cr}$ | $\text{₹ }5.5\text{ Cr}$ | `[<====●---]` ($-\text{₹ }1.5\text{Cr}$) | Boom-or-Bust | $\text{₹ }4.2\text{ Cr}$ | **PASS** |

---

## 9. Pitch Environment & Matchup Visualizations

### Pitch Archetype Badges

Match pitches are classified into four distinct archetypes, rendered as simple icon badges:

* **High-Scoring / Flat:** Red accent (`#D11A2A`), run rate $> 9.2$.
* **Spin-Friendly:** Muted Gold (`#D4AF37`), spin economy $< 7.2$.
* **Pace / Movement:** Slate Grey (`#4A5568`), pace wicket share $> 68\%$.
* **Two-Paced / Tricky:** Dark Charcoal (`#1E1E1E`), boundary rate $< 12\%$.

### Matchup Grid & Sample Protection

Matchup matrices (e.g., Batter vs Left-Arm Pace) use a 2-color divergent fill (Green for batter advantage, Red for bowler advantage).

* **Sample Protection Rule:** If deliveries faced $< 30$, the matchup cell must be rendered in hatched grey with a visible `Low Sample (<30b)` tag, preventing premature conclusions.

---

## 10. Accessibility Standards

* **Contrast Compliance:** All text against card backgrounds must clear a minimum contrast ratio of **4.5:1** (WCAG AA standard).
* **Color-Blind Safety:** Color encodings must always be accompanied by secondary non-color indicators (e.g., green value gaps feature an upward arrow `▲`, red risks feature a warning triangle `⚠`).
* **Minimum Font Sizes:** No text element on screen may be smaller than $9\text{ pt}$.

---

## 11. Presentation Deck Visual Language

Slide decks produced from this project (e.g., C-suite portfolio reviews) must adopt a consulting-style presentation aesthetic:

* **Slide Canvas:** Minimalist off-white background (`#F8F9FA`), 16:9 layout.
* **One Insight Per Slide:** Every slide must feature a single takeaway header sentence (e.g., *"Targeting Player A addresses RCB's death-over economy gap while preserving ₹3.5 Cr in purse flexibility"*).
* **Layout Structure:**
* **Left Column (30% width):** Executive conclusion, key decision numbers (36 pt JetBrains Mono), short bulleted rationale.
* **Right Column (70% width):** Large high-contrast visual (e.g., Valuation Scatter Plot, Scenario Matrix) supporting the left-column conclusion.



---

## 12. Reusable Design Checklist

Before publishing any dashboard page, report, or slide deck, verify compliance against this checklist:

* [ ] **Brand Identity:** No copyrighted RCB/IPL logos used; tone feels like an executive sports science tool.
* [ ] **Color Palette:** Maximum 5 colors active on screen; palette uses Deep Charcoal, Light Grey, RCB Red, Muted Gold, and semantic Green/Red.
* [ ] **Typography:** Fonts restricted to Inter and JetBrains Mono; strict size hierarchy maintained.
* [ ] **Grid & Spacing:** Visuals conform to 12-column grid with $16\text{ px}$ outer margins and $12\text{ px}$ card padding.
* [ ] **Chart Selection:** Zero 3D charts, zero pie charts with $>3$ slices; charts directly answer a defined product question.
* [ ] **Semantic Color Rules:** Green always means positive/value; Red always means risk/overpayment; Gold always means primary target.
* [ ] **Three-Second Profile Rule:** Player profiles state Name, Role, Fit, Fair Value, Max Bid, and Recommendation within the top header strip.
* [ ] **Accessibility:** Text contrast clears WCAG AA ($4.5:1$); color indicators paired with text labels or icons.
* [ ] **Sample Safeguards:** Matchups or features with insufficient sample sizes are explicitly flagged with low-confidence labels.