"""
Franchise-total-vs-purse-cap ceiling validation for consolidated auction data.

This is deliberately an UPPER-BOUND check, not an exact-match check.
ipl_auction_history.csv records only in-auction sold_price transactions; it
has no column for pre-auction retention costs, which in mega-auction years
consume part of the same season's cap before bidding starts. A franchise's
summed sold_price for a year will almost always be below the cap - that is
expected. The only signal worth failing loudly on is a total that EXCEEDS
the cap, which points to a currency/scale/dedup bug upstream, not a real
overspend by a franchise.

See configs/purse_caps.yaml for the reference cap figures and their
per-year confidence/sourcing.
"""

from pathlib import Path
from typing import Any, Dict, List, Union

import pandas as pd

from src.utils.config import get_project_root, load_config
from src.utils.exceptions import DataQualityError, ValidationError
from src.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_CSV_PATH = "data/raw/auction/ipl_auction_history.csv"
DEFAULT_CAPS_PATH = "configs/purse_caps.yaml"

REQUIRED_COLUMNS = {"year", "team_name", "sold_price", "sold_price_currency"}


def _load_auction_data(csv_path: Union[str, Path]) -> pd.DataFrame:
    """Load and minimally validate the consolidated auction CSV."""
    path = Path(csv_path)
    if not path.is_absolute():
        path = get_project_root() / path

    if not path.exists():
        raise ValidationError(f"Consolidated auction file not found: '{path}'")

    df = pd.read_csv(path)

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValidationError(
            f"Auction file '{path}' is missing required column(s): {sorted(missing)}"
        )

    return df


def _load_purse_caps(caps_path: Union[str, Path]) -> Dict[int, Dict[str, Any]]:
    """Load the purse cap reference table, keyed by int year."""
    config = load_config(caps_path)
    raw_caps = config.get("purse_caps")
    if not isinstance(raw_caps, dict):
        raise ValidationError(
            f"'{caps_path}' is missing a top-level 'purse_caps' mapping."
        )
    return {int(year): entry for year, entry in raw_caps.items()}


def compute_franchise_totals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-year, per-franchise summed sold_price, restricted to rows
    that are safe to compare against an INR-crore cap.

    Excludes:
      - rows with null or non-positive sold_price (unsold / bad rows)
      - rows not denominated in INR (currently: all of 2013, per
        configs/data_sources.yaml known_limitations)
    """
    clean = df.dropna(subset=["sold_price"])
    clean = clean[clean["sold_price"] > 0]
    clean = clean[clean["sold_price_currency"] == "INR"]

    totals = (
        clean.groupby(["year", "team_name"])["sold_price"]
        .sum()
        .reset_index()
        .rename(columns={"sold_price": "total_sold_price_inr"})
    )
    totals["total_sold_price_cr"] = totals["total_sold_price_inr"] / 1e7
    return totals


def validate_purse_caps(
    csv_path: Union[str, Path] = DEFAULT_CSV_PATH,
    caps_path: Union[str, Path] = DEFAULT_CAPS_PATH,
) -> Dict[str, Any]:
    """
    Run the ceiling check across all franchise-year totals.

    Returns:
        A report dict with keys:
          - "checked": list of rows actually compared against a known cap
          - "skipped_no_cap": years present in data but with no confirmed
            cap on record (informational, not a failure)
          - "violations": rows where total_sold_price_cr > cap_inr_cr
            (the only condition that should be treated as a real bug)

    Raises:
        ValidationError: if input files are missing or malformed.
    """
    df = _load_auction_data(csv_path)
    caps = _load_purse_caps(caps_path)
    totals = compute_franchise_totals(df)

    checked: List[Dict[str, Any]] = []
    skipped_years: set = set()
    violations: List[Dict[str, Any]] = []

    for _, row in totals.iterrows():
        year = int(row["year"])
        cap_entry = caps.get(year)

        if not cap_entry or cap_entry.get("cap_inr_cr") is None:
            skipped_years.add(year)
            continue

        cap_cr = float(cap_entry["cap_inr_cr"])
        spent_cr = float(row["total_sold_price_cr"])
        record = {
            "year": year,
            "team_name": row["team_name"],
            "total_sold_price_cr": round(spent_cr, 2),
            "cap_inr_cr": cap_cr,
        }
        checked.append(record)

        if spent_cr > cap_cr:
            violations.append(record)
            logger.warning(
                "Purse cap ceiling exceeded: %s %s spent Rs %.2f Cr against a "
                "Rs %.2f Cr cap",
                year,
                row["team_name"],
                spent_cr,
                cap_cr,
            )

    if skipped_years:
        logger.info(
            "No confirmed purse cap on record for year(s) %s - skipped, not failed. "
            "Add a sourced figure to configs/purse_caps.yaml to include them.",
            sorted(skipped_years),
        )

    report = {
        "checked": checked,
        "skipped_no_cap": sorted(skipped_years),
        "violations": violations,
    }

    if violations:
        raise DataQualityError(
            f"{len(violations)} franchise-year total(s) exceed the known purse "
            f"cap ceiling: {violations}"
        )

    logger.info(
        "Purse cap ceiling check passed: %d franchise-year totals checked, "
        "0 violations, %d years skipped for lack of a confirmed cap.",
        len(checked),
        len(skipped_years),
    )
    return report


if __name__ == "__main__":
    try:
        result = validate_purse_caps()
    except DataQualityError as exc:
        logger.error(str(exc))
        raise SystemExit(1)
    except ValidationError as exc:
        logger.error(str(exc))
        raise SystemExit(2)

    print(f"Checked:  {len(result['checked'])} franchise-year totals")
    print(f"Violations: {len(result['violations'])}")
    print(f"Skipped (no confirmed cap): {result['skipped_no_cap']}")