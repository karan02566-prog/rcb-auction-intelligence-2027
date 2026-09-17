"""
Phase 3.6: Auction Economics & Historical Price Dynamics.

Inputs: data/raw/auction/ipl_auction_history.csv, configs/purse_caps.yaml
Output: reports/eda_auction_economics.json

Scope: 2018-2026 (per phase.md objective), sold_price rows only, INR only
(2013 rows are USD-denominated and outside this window anyway).

Known source-schema gaps (documented, not fabricated -- see
src/ingestion/auction_consolidate.py docstring for the full per-year
column drift):
  - `role`: present 2013-2024, MISSING for 2025-2026 (source dropped it).
    Role-based spending stats for 2025-2026 are therefore incomplete;
    flagged in the report's `data_gaps` block, not silently dropped or
    back-filled. Also spelled inconsistently within 2013-2024 itself
    (Batsman/Batter, Wicket Keeper/Wicket-Keeper -- confirmed via
    value_counts on the raw CSV); canonicalized via `normalize_role()`.
  - `nationality`: present only 2022-2026, values are "Indian"/"Overseas"
    (not country names). Overseas-vs-Indian spend ratio
    is computed only over 2022-2026 and the report says so explicitly.
  - No pre-auction RETENTION field exists anywhere in this source (only
    in-auction sold_price transactions are recorded -- see
    src/validation/purse_cap_check.py docstring). "Price retention
    premiums" is therefore computed as a data-supported proxy: for
    players sold in more than one auction year, the price change between
    their consecutive sale years (i.e. what it cost to re-secure them via
    auction next time), NOT actual retention-clause cost. Labelled
    `resale_premium` in the output to avoid implying real retention data.

Purse-expansion normalization (common failure mode named in phase.md):
  raw crore totals are not comparable across years because the league-wide
  cap itself grew (60cr in 2014 -> 125cr in 2026). Every year's total spend
  is therefore also reported as a fraction of that year's known cap
  (`spend_as_pct_of_cap`), using only years with a confirmed cap in
  configs/purse_caps.yaml -- unconfirmed years are skipped, not guessed.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.utils.config import get_project_root, load_config

SEASON_MIN = 2018
SEASON_MAX = 2026


def load_auction(root: Path) -> pd.DataFrame:
    df = pd.read_csv(root / "data" / "raw" / "auction" / "ipl_auction_history.csv")
    n_before = len(df)
    df = df.dropna(subset=["sold_price"])
    df = df[df["sold_price"] > 0]
    df = df[df["sold_price_currency"] == "INR"]
    df = df[df["year"].between(SEASON_MIN, SEASON_MAX)]
    print(f"Filtered to {SEASON_MIN}-{SEASON_MAX}, sold INR rows: {len(df):,} / {n_before:,} rows")
    return df


ROLE_CANONICAL_MAP = {
    "batsman": "Batter",
    "batter": "Batter",
    "bowler": "Bowler",
    "all-rounder": "All-Rounder",
    "wicket keeper": "Wicket-Keeper",
    "wicket-keeper": "Wicket-Keeper",
}


def normalize_role(raw: str) -> str:
    """Source spells role inconsistently across years (Batsman/Batter,
    Wicket Keeper/Wicket-Keeper -- confirmed via value_counts on the raw
    CSV). Canonicalize before grouping or role-based stats silently split
    into duplicate buckets."""
    key = str(raw).strip().lower()
    return ROLE_CANONICAL_MAP.get(key, str(raw).strip())


def role_price_summary(df: pd.DataFrame) -> list[dict]:
    rows = []
    role_rows = df.dropna(subset=["role"]).copy()
    role_rows["role"] = role_rows["role"].map(normalize_role)
    missing_role_years = sorted(set(df["year"]) - set(role_rows["year"]))
    for role, grp in role_rows.groupby("role"):
        rows.append({
            "role": role,
            "n_sales": int(len(grp)),
            "median_price_inr": float(grp["sold_price"].median()),
            "peak_price_inr": float(grp["sold_price"].max()),
            "years_covered": sorted(int(y) for y in grp["year"].unique()),
        })
    return rows, missing_role_years


def overseas_vs_indian(df: pd.DataFrame) -> dict:
    nat_rows = df.dropna(subset=["nationality"])
    years_covered = sorted(int(y) for y in nat_rows["year"].unique())
    # Source values are "Indian"/"Overseas" (confirmed via value_counts on
    # the raw CSV), not country names -- "india" never matched here before.
    is_indian = nat_rows["nationality"].str.strip().str.lower().eq("indian")
    indian_total = float(nat_rows.loc[is_indian, "sold_price"].sum())
    overseas_total = float(nat_rows.loc[~is_indian, "sold_price"].sum())
    return {
        "years_covered": years_covered,
        "indian_total_inr": indian_total,
        "overseas_total_inr": overseas_total,
        "overseas_to_indian_spend_ratio": round(overseas_total / indian_total, 3) if indian_total else None,
        "indian_median_price_inr": float(nat_rows.loc[is_indian, "sold_price"].median()) if is_indian.any() else None,
        "overseas_median_price_inr": float(nat_rows.loc[~is_indian, "sold_price"].median()) if (~is_indian).any() else None,
    }


def resale_premiums(df: pd.DataFrame) -> list[dict]:
    """Price change for players sold in >1 auction year (proxy for retention
    premium -- see module docstring for why real retention cost isn't used)."""
    sales = df.sort_values(["player_name", "year"])
    rows = []
    for name, grp in sales.groupby("player_name"):
        grp = grp.drop_duplicates("year")
        if len(grp) < 2:
            continue
        prices = grp["sold_price"].tolist()
        years = grp["year"].tolist()
        for i in range(1, len(prices)):
            if prices[i - 1] <= 0:
                continue
            rows.append({
                "player_name": name,
                "from_year": int(years[i - 1]),
                "to_year": int(years[i]),
                "from_price_inr": float(prices[i - 1]),
                "to_price_inr": float(prices[i]),
                "resale_premium_ratio": round(float(prices[i] / prices[i - 1]), 3),
            })
    return rows


def spend_vs_cap(df: pd.DataFrame, caps: dict) -> list[dict]:
    """League-wide ceiling check: total sold_price for a year should not
    exceed (num_franchises_that_year * confirmed cap) -- retention costs
    are excluded from this data so real spend sits below, never above."""
    rows = []
    for year, grp in df.groupby("year"):
        cap_entry = caps.get(int(year))
        if not cap_entry or cap_entry.get("cap_inr_cr") is None:
            continue
        cap_cr = float(cap_entry["cap_inr_cr"])
        n_teams = grp["team_name"].nunique()
        total_spend_cr = float(grp["sold_price"].sum()) / 1e7
        total_cap_cr = cap_cr * n_teams
        rows.append({
            "year": int(year),
            "n_franchises": int(n_teams),
            "total_spend_cr": round(total_spend_cr, 2),
            "total_available_cap_cr": round(total_cap_cr, 2),
            "spend_as_pct_of_cap": round(total_spend_cr / total_cap_cr * 100, 2),
            "within_ceiling": bool(total_spend_cr <= total_cap_cr),
        })
    return rows


def main() -> Path:
    root = get_project_root()
    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    df = load_auction(root)
    caps = {int(y): entry for y, entry in load_config("configs/purse_caps.yaml")["purse_caps"].items()}

    role_rows, missing_role_years = role_price_summary(df)
    overseas = overseas_vs_indian(df)
    premiums = resale_premiums(df)
    ceiling = spend_vs_cap(df, caps)

    violations = [r for r in ceiling if not r["within_ceiling"]]
    print(f"Ceiling check: {len(ceiling)} years checked (confirmed cap only), {len(violations)} violations")
    if violations:
        print(f"VALIDATION FAILED -- spend exceeds cap in: {violations}")

    if premiums:
        avg_premium = sum(p["resale_premium_ratio"] for p in premiums) / len(premiums)
        print(f"Resale premium: {len(premiums)} repeat-sale pairs, mean ratio {avg_premium:.3f}")

    out = {
        "seasons_filtered": f"{SEASON_MIN}-{SEASON_MAX}",
        "data_gaps": {
            "role_missing_for_years": missing_role_years,
            "nationality_available_years": overseas["years_covered"],
            "retention_cost_field": "not present in source; resale_premium is a proxy, not real retention data",
        },
        "role_price_summary": role_rows,
        "overseas_vs_indian": overseas,
        "resale_premiums": premiums,
        "spend_vs_purse_cap_ceiling": ceiling,
        "ceiling_violations": violations,
        "validation_passed": len(violations) == 0,
    }
    out_path = reports / "eda_auction_economics.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Saved: {out_path}")
    return out_path


if __name__ == "__main__":
    main()
