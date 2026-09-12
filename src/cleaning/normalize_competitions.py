import re
import pandas as pd
from pathlib import Path

def parse_season(season_str):
    """Normalize season formats like '2023/24', '2023', '2023-2024', 'Season 10' into canonical keys."""
    if pd.isna(season_str):
        return "UNKNOWN", None, None

    s = str(season_str).strip()
    
    # Handle YYYY/YY or YYYY-YY (e.g., 2023/24 -> 2023-2024)
    m_slash = re.match(r'^(\d{4})[/-](\d{2})$', s)
    if m_slash:
        start = int(m_slash.group(1))
        end = int(str(start)[:2] + m_slash.group(2))
        return f"{start}-{end}", start, end

    # Handle YYYY/YYYY or YYYY-YYYY
    m_full = re.match(r'^(\d{4})[/-](\d{4})$', s)
    if m_full:
        start = int(m_full.group(1))
        end = int(m_full.group(2))
        return f"{start}-{end}", start, end

    # Handle single YYYY
    m_year = re.search(r'\b(19\d{2}|20\d{2})\b', s)
    if m_year:
        yr = int(m_year.group(1))
        return str(yr), yr, yr

    return s, None, None

def classify_competition(comp_name):
    """Categorize competition into tiers: IPL, Overseas Franchise, Domestic, International, Other."""
    if pd.isna(comp_name):
        return "Other"

    name = str(comp_name).lower().strip()

    if "indian premier league" in name or "ipl" in name:
        return "IPL"
    elif any(k in name for k in [
        "big bash", "bbl", "caribbean premier league", "cpl", "pakistan super league", "psl",
        "sa20", "ilt20", "major league cricket", "mlc", "the hundred", "bpl", "bangladesh premier league",
        "lanka premier league", "lpl", "super smash", "t20 blast"
    ]):
        return "Overseas Franchise"
    elif any(k in name for k in [
        "syed mushtaq ali", "ranji", "vijay hazare", "deodhar", "duleep",
        "sheffield shield", "marsh cup", "csa t20", "plunket shield"
    ]):
        return "Domestic"
    elif any(k in name for k in ["t20i", "odi", "test", "world cup", "asia cup", "champions trophy", "international"]):
        return "International"
    else:
        return "Domestic"

def main():
    raw_dir = Path("data/raw")
    interim_dir = Path("data/interim")
    processed_dir = Path("data/processed")
    processed_dir.mkdir(parents=True, exist_ok=True)

    matches_parquet = interim_dir / "matches.parquet"
    participation_csv = raw_dir / "metadata" / "player_participation.csv"
    summary_csv = raw_dir / "metadata" / "player_competition_summary.csv"

    # Load source matches dataset
    if matches_parquet.exists():
        df = pd.read_parquet(matches_parquet)
        print(f"Loaded source dataset from: {matches_parquet}")
    elif participation_csv.exists():
        df = pd.read_csv(participation_csv)
        print(f"Loaded source dataset from: {participation_csv}")
    elif summary_csv.exists():
        df = pd.read_csv(summary_csv)
        print(f"Loaded source dataset from: {summary_csv}")
    else:
        raise FileNotFoundError("No valid match or participation dataset found in data/interim/ or data/raw/metadata/")

    # Normalize dates to ISO-8601 (YYYY-MM-DD)
    date_col = next((c for c in ["match_date", "first_match_date", "date"] if c in df.columns), None)
    if date_col:
        df["match_date_iso"] = pd.to_datetime(df[date_col], errors="coerce").dt.strftime("%Y-%m-%d")
    else:
        df["match_date_iso"] = None

    # Group competition and season metadata
    comp_col = next((c for c in ["competition", "league", "competition_name"] if c in df.columns), "competition")
    season_col = next((c for c in ["season", "year"] if c in df.columns), "season")

    grouped = df.groupby([comp_col, season_col], dropna=False).agg(
        total_records=(comp_col, "count"),
        min_date=("match_date_iso", "min"),
        max_date=("match_date_iso", "max")
    ).reset_index()

    records = []
    for _, row in grouped.iterrows():
        comp_raw = row[comp_col]
        season_raw = row[season_col]
        canonical_season, start_yr, end_yr = parse_season(season_raw)
        tier = classify_competition(comp_raw)

        comp_id = f"{re.sub(r'[^a-zA-Z0-9]', '_', str(comp_raw).lower()).strip('_')}_{canonical_season}"

        records.append({
            "competition_id": comp_id,
            "competition_raw": comp_raw,
            "competition_canonical": str(comp_raw).strip(),
            "competition_category": tier,
            "season_raw": season_raw,
            "season_canonical": canonical_season,
            "start_year": start_yr,
            "end_year": end_yr,
            "date_min_iso": row["min_date"],
            "date_max_iso": row["max_date"],
            "total_records": int(row["total_records"])
        })

    dim_comp = pd.DataFrame(records)

    # Save outputs (parquet + csv fallback)
    out_parquet = processed_dir / "dim_competitions.parquet"
    out_csv = processed_dir / "dim_competitions.csv"

    try:
        dim_comp.to_parquet(out_parquet, index=False)
        print(f"Saved Parquet: {out_parquet}")
    except Exception as e:
        print(f"Parquet save skipped ({e}), exporting CSV fallback.")

    dim_comp.to_csv(out_csv, index=False)
    print(f"Saved CSV: {out_csv}")

    # Validation breakdown
    print("\n--- Competition Category Breakdown ---")
    print(dim_comp["competition_category"].value_counts().to_string())
    print(f"\nTotal Standardized Competitions/Seasons: {len(dim_comp)}")

if __name__ == "__main__":
    main()
