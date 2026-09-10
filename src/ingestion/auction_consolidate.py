"""
Consolidate per-year IPL auction CSVs (Kaggle: sunnyyadav754/ipl-auction-dataset-20132026)
into one canonical table: data/raw/auction/ipl_auction_history.csv

Source schema drift observed across years:
  2013:        Name, Price in $,  Role, TeamName                (USD, no nationality, no base price)
  2014-2021:   Name, Price in rs, Role, TeamName                 (INR, no nationality, no base price)
  2022-2024:   Name, Nationality, Price in rs, Role, TeamName     (INR, adds nationality)
  2025-2026:   Name, Nationality, BasePrices in Rs, Winning Bid in Rs, TeamName, Capped/UnCapped
                                                                   (INR, adds base price + capped status, drops Role)

Policy: never fabricate a field a given year doesn't provide. Missing fields are
left as NaN/empty, not guessed or defaulted. Currency is preserved per-row rather
than silently converted, since no documented FX rate for the 2013 USD figures exists
in this source.
"""

import re
from pathlib import Path

import pandas as pd

SOURCE_DIR = Path("sources/IPL_Auction")
OUTPUT_PATH = Path("ipl_auction_history.csv")

CANONICAL_COLUMNS = [
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


def parse_money(raw, currency):
    """Extract a numeric value from a raw price string. Currency is passed in
    explicitly (derived from the SOURCE COLUMN NAME, e.g. 'Price in $' vs
    'Price in rs') since the cell values themselves carry no currency symbol.
    Returns None for blank/unparseable input rather than fabricating a value.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None

    digits = re.sub(r"[^0-9.]", "", s)
    if not digits:
        return None

    return float(digits)


def clean_str(val):
    if pd.isna(val):
        return None
    s = str(val).strip()
    return s if s else None


def extract_year(filename: str) -> int:
    match = re.search(r"(\d{4})", filename)
    if not match:
        raise ValueError(f"Could not extract year from filename: {filename}")
    return int(match.group(1))


def load_one_file(path: Path) -> pd.DataFrame:
    year = extract_year(path.name)
    df = pd.read_csv(path, index_col=0)
    df.columns = [c.strip() for c in df.columns]
    # Source files keep their original (non-sequential) row numbers as the
    # index column. Reset it so downstream assignment aligns positionally
    # instead of silently producing NaNs via pandas index-based alignment.
    df = df.reset_index(drop=True)

    row_count = len(df)
    out = pd.DataFrame(index=range(row_count))

    out["year"] = year
    out["player_name"] = df["Name"].map(clean_str) if "Name" in df.columns else None
    out["nationality"] = df["Nationality"].map(clean_str) if "Nationality" in df.columns else None
    out["role"] = df["Role"].map(clean_str) if "Role" in df.columns else None
    out["capped_status"] = (
        df["Capped/UnCapped"].map(clean_str) if "Capped/UnCapped" in df.columns else None
    )
    out["team_name"] = df["TeamName"].map(clean_str) if "TeamName" in df.columns else None

    # Base price: only present 2025-2026 in this source (always Rs in that era)
    if "BasePrices in Rs" in df.columns:
        out["base_price"] = df["BasePrices in Rs"].map(lambda v: parse_money(v, "INR"))
        out["base_price_currency"] = out["base_price"].map(lambda v: "INR" if v is not None else None)
    else:
        out["base_price"] = None
        out["base_price_currency"] = None

    # Sold price: column name AND currency vary by era
    sold_col_currency = [
        ("Winning Bid in Rs", "INR"),
        ("Price in rs", "INR"),
        ("Price in $", "USD"),
    ]
    sold_col, sold_currency = None, None
    for candidate, currency in sold_col_currency:
        if candidate in df.columns:
            sold_col, sold_currency = candidate, currency
            break

    if sold_col is not None:
        out["sold_price"] = df[sold_col].map(lambda v: parse_money(v, sold_currency))
        out["sold_price_currency"] = out["sold_price"].map(lambda v: sold_currency if v is not None else None)
    else:
        out["sold_price"] = None
        out["sold_price_currency"] = None

    out["source_file"] = path.name
    return out[CANONICAL_COLUMNS]


def main():
    files = sorted(SOURCE_DIR.glob("*.csv"))
    if not files:
        raise SystemExit(f"No CSV files found in {SOURCE_DIR}")

    frames = []
    for f in files:
        frame = load_one_file(f)
        frames.append(frame)
        print(f"  {f.name}: {len(frame)} rows parsed")

    combined = pd.concat(frames, ignore_index=True)
    combined.to_csv(OUTPUT_PATH, index=False)

    print(f"\nWrote {len(combined)} total rows to {OUTPUT_PATH}")
    print(f"Years covered: {sorted(combined['year'].unique().tolist())}")
    print(f"Rows missing sold_price: {combined['sold_price'].isna().sum()}")
    print(f"Rows missing base_price: {combined['base_price'].isna().sum()} (expected: all pre-2025 rows)")


if __name__ == "__main__":
    main()