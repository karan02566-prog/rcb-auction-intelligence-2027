from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_AUCTION_DIR = PROJECT_ROOT / "data" / "raw" / "auction"

REQUIRED_COLUMNS = [
    "year",
    "player_name",
    "nationality",
    "role",
    "capped_status",
    "base_price",
    "base_price_currency",
    "sold_price",
    "sold_price_currency",
    "team_name",
    "source_file",
]

VALID_NATIONALITY = {"", "Indian", "Overseas"}

VALID_CAPPED_STATUS = {"", "Capped", "Uncapped"}

VALID_CURRENCIES = {"", "INR", "USD"}

VALID_ROLES = {
    "",
    "All-Rounder",
    "Bowler",
    "Batsman",
    "Batter",
    "Wicket Keeper",
    "Wicket-Keeper",
}


def load_auction_records(path: Path) -> pd.DataFrame:
    """Load the consolidated auction dataset as source-preserving strings."""
    if not path.exists():
        raise FileNotFoundError(f"Auction input not found: {path}")

    df = pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
    )

    missing = set(REQUIRED_COLUMNS) - set(df.columns)

    if missing:
        raise ValueError(
            f"Auction input is missing required columns: {sorted(missing)}"
        )

    return df


def _validate_allowed_values(
    df: pd.DataFrame,
    column: str,
    allowed: set[str],
) -> None:
    values = set(df[column].astype(str))
    invalid = values - allowed

    if invalid:
        raise ValueError(
            f"Invalid values in {column}: {sorted(invalid)}"
        )


def _validate_numeric_column(
    df: pd.DataFrame,
    column: str,
) -> None:
    values = df[column].replace("", pd.NA)

    numeric = pd.to_numeric(
        values,
        errors="coerce",
    )

    invalid = values.notna() & numeric.isna()

    if invalid.any():
        raise ValueError(
            f"Non-numeric values found in {column}: "
            f"{sorted(values[invalid].astype(str).unique())}"
        )

    negative = numeric.notna() & (numeric < 0)

    if negative.any():
        raise ValueError(
            f"Negative values are not allowed in {column}"
        )


def validate_auction_records(df: pd.DataFrame) -> pd.DataFrame:
    """Validate the source-supported 11-column auction schema."""
    missing = set(REQUIRED_COLUMNS) - set(df.columns)

    if missing:
        raise ValueError(
            f"Auction dataframe is missing required columns: {sorted(missing)}"
        )

    result = df[REQUIRED_COLUMNS].copy()

    # Required identity fields.
    for column in ["year", "player_name", "team_name", "source_file"]:
        empty = result[column].astype(str).eq("")

        if empty.any():
            raise ValueError(
                f"{column} cannot be empty"
            )

    # Year validation.
    years = pd.to_numeric(
        result["year"],
        errors="coerce",
    )

    if years.isna().any():
        raise ValueError("year contains non-numeric values")

    if ((years < 2013) | (years > 2100)).any():
        raise ValueError("year contains values outside the supported range")

    # Controlled categorical fields.
    _validate_allowed_values(
        result,
        "nationality",
        VALID_NATIONALITY,
    )

    _validate_allowed_values(
        result,
        "capped_status",
        VALID_CAPPED_STATUS,
    )

    _validate_allowed_values(
        result,
        "role",
        VALID_ROLES,
    )

    _validate_allowed_values(
        result,
        "base_price_currency",
        VALID_CURRENCIES,
    )

    _validate_allowed_values(
        result,
        "sold_price_currency",
        VALID_CURRENCIES,
    )

    # Numeric price validation.
    _validate_numeric_column(
        result,
        "base_price",
    )

    _validate_numeric_column(
        result,
        "sold_price",
    )

    # Sold prices are present in the consolidated source for every row.
    sold_price_missing = result["sold_price"].eq("")

    if sold_price_missing.any():
        raise ValueError(
            "sold_price cannot be empty in the consolidated auction dataset"
        )

    # A price should not have a currency missing.
    for price_column, currency_column in [
        ("base_price", "base_price_currency"),
        ("sold_price", "sold_price_currency"),
    ]:
        price_present = result[price_column].ne("")
        currency_missing = result[currency_column].eq("")

        invalid = price_present & currency_missing

        if invalid.any():
            raise ValueError(
                f"{currency_column} cannot be empty when "
                f"{price_column} is present"
            )

    # Detect duplicate logical records.
    duplicate_columns = [
        "year",
        "player_name",
        "team_name",
        "source_file",
    ]

    duplicates = result.duplicated(
        subset=duplicate_columns,
        keep=False,
    )

    if duplicates.any():
        duplicate_rows = result.loc[
            duplicates,
            duplicate_columns,
        ].to_dict("records")

        raise ValueError(
            f"Duplicate logical auction records found: {duplicate_rows}"
        )

    return result


def auction_quality_report(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Return basic column-level completeness diagnostics."""
    validated = validate_auction_records(df)

    report = pd.DataFrame(
        {
            "column": REQUIRED_COLUMNS,
            "row_count": len(validated),
            "missing_count": [
                validated[column].eq("").sum()
                for column in REQUIRED_COLUMNS
            ],
        }
    )

    report["missing_pct"] = (
        report["missing_count"]
        / report["row_count"]
        * 100
    )

    return report


def write_auction_history(
    df: pd.DataFrame,
    output_path: Path | None = None,
) -> Path:
    """Validate and write the historical auction table."""
    output_path = (
        output_path
        or RAW_AUCTION_DIR / "ipl_auction_history.csv"
    )

    validated = validate_auction_records(df)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    validated.to_csv(
        output_path,
        index=False,
    )

    return output_path


def ingest_auction_history(
    input_path: Path,
    output_path: Path | None = None,
) -> Path:
    """Load, validate, and write a controlled auction history dataset."""
    records = load_auction_records(input_path)

    return write_auction_history(
        records,
        output_path,
    )