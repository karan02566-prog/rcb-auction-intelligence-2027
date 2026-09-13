import json
import re
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

# Seed list of CONFIRMED ground renames only (physical venue unchanged, name changed).
# This is not exhaustive -- it covers only renames I'm confident are correct.
# Anything else in your actual data will show up in reports/venue_normalization_review.csv
# for you to check and add here.
KNOWN_LINEAGE = {
    "feroz shah kotla": "arun jaitley stadium",
    "feroz shah kotla ground": "arun jaitley stadium",
    "sardar patel stadium": "narendra modi stadium",
    "sardar patel stadium motera": "narendra modi stadium",
    "motera stadium": "narendra modi stadium",
    "punjab cricket association stadium": "punjab cricket association is bindra stadium",
    "punjab cricket association stadium mohali": "punjab cricket association is bindra stadium",
    "is bindra stadium": "punjab cricket association is bindra stadium",
}

KNOWN_LINEAGE.update({
    "rajiv gandhi international stadium uppal": "rajiv gandhi international stadium",
    "daren sammy national cricket stadium gros islet st lucia": "daren sammy national cricket stadium gros islet",
    "sir vivian richards stadium north sound antigua": "sir vivian richards stadium north sound",
    "dr dy patil sports academy mumbai": "dr dy patil sports academy",
    "maharaja yadavindra singh international cricket stadium mullanpur": "maharaja yadavindra singh international cricket stadium new chandigarh",
    "queen's park oval port of spain trinidad": "queen's park oval port of spain",
    "gmhba stadium south geelong victoria": "simonds stadium south geelong victoria",
    "brian lara stadium tarouba trinidad": "brian lara stadium tarouba",
    "kensington oval bridgetown barbados": "kensington oval bridgetown",
    "ma chidambaram stadium chepauk": "ma chidambaram stadium",
    "providence stadium guyana": "providence stadium",
    "sabina park kingston jamaica": "sabina park kingston",
    "warner park basseterre st kitts": "warner park basseterre",
})


def normalize_key(raw) -> str:
    """Collapse punctuation/whitespace/case so spelling variants of the same
    ground converge. Does NOT resolve genuine renames -- see KNOWN_LINEAGE."""
    if pd.isna(raw):
        return ""
    s = str(raw).lower().replace("&", "and").replace("-", " ")
    s = re.sub(r"[.,]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def strip_city_suffix(key: str, city) -> str:
    """'Eden Gardens, Kolkata' and 'Eden Gardens' should converge."""
    if pd.isna(city):
        return key
    city_key = normalize_key(city)
    if city_key and key.endswith(city_key):
        key = key[: -len(city_key)].strip()
    return key


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def main():
    interim_dir = Path("data/interim")
    processed_dir = Path("data/processed")
    configs_dir = Path("configs")
    reports_dir = Path("reports")
    processed_dir.mkdir(parents=True, exist_ok=True)
    configs_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    matches_parquet = interim_dir / "matches.parquet"
    if not matches_parquet.exists():
        raise FileNotFoundError(f"Expected interim matches table at {matches_parquet}")

    df = pd.read_parquet(matches_parquet)
    if "venue" not in df.columns:
        raise KeyError("'venue' column not found in data/interim/matches.parquet")
    city_col = "city" if "city" in df.columns else None

    group_cols = ["venue", city_col] if city_col else ["venue"]
    raw_counts = df.groupby(group_cols, dropna=False).size().reset_index(name="total_records")

    def build_key(row):
        base = normalize_key(row["venue"])
        if city_col:
            base = strip_city_suffix(base, row[city_col])
        return KNOWN_LINEAGE.get(base, base)

    raw_counts["norm_key"] = raw_counts.apply(build_key, axis=1)

    records = []
    mapping = {}
    for i, (key, group) in enumerate(sorted(raw_counts.groupby("norm_key"), key=lambda kv: kv[0]), start=1):
        venue_id = "VEN_UNKNOWN" if key == "" else f"VEN_{i:04d}"
        canonical_row = group.loc[group["total_records"].idxmax()]
        canonical_name = str(canonical_row["venue"])
        canonical_city = str(canonical_row[city_col]) if city_col and pd.notna(canonical_row[city_col]) else None
        variants = sorted(group["venue"].astype(str).unique().tolist())

        records.append({
            "venue_id": venue_id,
            "venue_canonical": canonical_name,
            "city": canonical_city,
            "raw_variant_count": len(variants),
            "raw_variants": variants,
            "total_records": int(group["total_records"].sum()),
        })
        for v in variants:
            mapping[v] = venue_id

    dim_venues = pd.DataFrame(records)

    # Flag close-but-unmerged names for manual review. Never auto-merge on fuzzy
    # similarity alone -- same flag-don't-force pattern as player_identity_audit.py.
    review_rows = []
    canon_list = dim_venues["venue_canonical"].tolist()
    for i in range(len(canon_list)):
        for j in range(i + 1, len(canon_list)):
            score = similarity(normalize_key(canon_list[i]), normalize_key(canon_list[j]))
            if 0.80 <= score < 1.0:
                review_rows.append({"venue_a": canon_list[i], "venue_b": canon_list[j], "similarity": round(score, 3)})

    out_parquet = processed_dir / "dim_venues.parquet"
    out_csv = processed_dir / "dim_venues.csv"
    try:
        dim_venues.to_parquet(out_parquet, index=False)
        print(f"Saved Parquet: {out_parquet}")
    except Exception as e:
        print(f"Parquet save skipped ({e}), exporting CSV fallback.")
    dim_venues.to_csv(out_csv, index=False)
    print(f"Saved CSV: {out_csv}")

    with open(configs_dir / "venue_mapping.json", "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)
    print(f"Saved venue mapping: {configs_dir / 'venue_mapping.json'}")

    if review_rows:
        review_path = reports_dir / "venue_normalization_review.csv"
        pd.DataFrame(review_rows).sort_values("similarity", ascending=False).to_csv(review_path, index=False)
        print(f"\n{len(review_rows)} close-but-unmerged venue pairs flagged for manual review: {review_path}")
    else:
        print("\nNo ambiguous near-duplicate venue names flagged.")

    unmapped = df["venue"].isna().sum()
    print(f"\nTotal canonical venues: {len(dim_venues)}")
    print(f"Total raw venue strings mapped: {len(mapping)}")
    print(f"Null/unmapped venue rows in source: {unmapped}")
    if unmapped > 0:
        print("WARNING: exit criteria needs 100% mapped -- null venues need a source-data fix.")


if __name__ == "__main__":
    main()