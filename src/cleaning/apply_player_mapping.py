import json
import re
import pandas as pd
from pathlib import Path

def normalize_string(val: str) -> str:
    if not isinstance(val, str):
        return ""
    val = val.lower().strip()
    val = re.sub(r'[^\w\s]', '', val)
    return re.sub(r'\s+', ' ', val)

def get_mapping_lookups():
    mapping_file = Path("configs/player_mapping.json")
    if not mapping_file.exists():
        raise FileNotFoundError(f"{mapping_file} not found. Run generate_player_mapping.py first.")
    
    mapping_data = json.loads(mapping_file.read_text(encoding="utf-8"))
    mapped_list = mapping_data.get("mapped", [])
    
    exact_lookup = {}
    norm_lookup = {}
    
    for item in mapped_list:
        src = item["source_name"]
        exact_lookup[src] = item
        norm_key = normalize_string(src)
        if norm_key and norm_key not in norm_lookup:
            norm_lookup[norm_key] = item
            
    return exact_lookup, norm_lookup

def resolve_player(name_val, exact_lookup, norm_lookup):
    if pd.isna(name_val) or not str(name_val).strip():
        return "NA", "NA", "none"
    
    name_str = str(name_val).strip()
    
    # 1. Exact Match
    if name_str in exact_lookup:
        match = exact_lookup[name_str]
        return match["canonical_id"], match["canonical_name"], match["method"]
        
    # 2. Normalized Match
    norm_key = normalize_string(name_str)
    if norm_key in norm_lookup:
        match = norm_lookup[norm_key]
        return match["canonical_id"], match["canonical_name"], match["method"] + "_normalized"
        
    return "UNRESOLVED", name_str, "unresolved"

def apply_mapping_to_file(input_path: Path, output_path: Path, exact_lookup: dict, norm_lookup: dict):
    if input_path.name == "sample_sales_data.csv":
        return

    try:
        df = pd.read_csv(input_path)
    except Exception as e:
        print(f"Skipping {input_path.name}: {e}")
        return

    candidate_cols = ["Name", "player_name", "name", "unique_name", "batter", "bowler", "player"]
    target_cols = [c for c in candidate_cols if c in df.columns]

    if not target_cols:
        print(f"Skipping '{input_path.relative_to('data/raw')}': No player columns matching {candidate_cols}")
        return

    for col in target_cols:
        results = df[col].apply(lambda x: resolve_player(x, exact_lookup, norm_lookup))
        df[f"{col}_canonical_id"] = [r[0] for r in results]
        df[f"{col}_canonical_name"] = [r[1] for r in results]
        df[f"{col}_mapping_method"] = [r[2] for r in results]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    
    primary_col = target_cols[0]
    total = df[primary_col].dropna().count()
    resolved = (df[f"{primary_col}_canonical_id"] != "UNRESOLVED").sum()
    pct = (resolved / total * 100) if total > 0 else 0
    print(f"Cleaned '{input_path.relative_to('data/raw')}' (Col: '{primary_col}') -> Mapped: {resolved}/{total} ({pct:.2f}%)")

def main():
    exact_lookup, norm_lookup = get_mapping_lookups()
    raw_dir = Path("data/raw")
    cleaned_dir = Path("data/cleaned")

    csv_files = list(raw_dir.rglob("*.csv"))
    for raw_path in csv_files:
        rel_path = raw_path.relative_to(raw_dir)
        out_path = cleaned_dir / rel_path
        apply_mapping_to_file(raw_path, out_path, exact_lookup, norm_lookup)

if __name__ == "__main__":
    main()
