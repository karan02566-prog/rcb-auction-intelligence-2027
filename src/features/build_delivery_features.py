import json
import re
import pandas as pd
import numpy as np
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
        return {}, {}
    
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

def resolve_name(name_val, exact_lookup, norm_lookup):
    if pd.isna(name_val) or not str(name_val).strip():
        return "NA", "NA"
    name_str = str(name_val).strip()
    if name_str in exact_lookup:
        return exact_lookup[name_str]["canonical_id"], exact_lookup[name_str]["canonical_name"]
    norm_key = normalize_string(name_str)
    if norm_key in norm_lookup:
        return norm_lookup[norm_key]["canonical_id"], norm_lookup[norm_key]["canonical_name"]
    return "UNRESOLVED", name_str

def main():
    interim_dir = Path("data/interim")
    raw_dir = Path("data/raw")
    processed_dir = Path("data/processed")
    processed_dir.mkdir(parents=True, exist_ok=True)

    deliv_parquet = interim_dir / "deliveries.parquet"
    deliv_csv = raw_dir / "deliveries.csv"

    if deliv_parquet.exists():
        df = pd.read_parquet(deliv_parquet)
        print(f"Loaded deliveries parquet with {len(df):,} rows.")
    elif deliv_csv.exists():
        df = pd.read_csv(deliv_csv)
        print(f"Loaded deliveries CSV with {len(df):,} rows.")
    else:
        raise FileNotFoundError("Delivery dataset not found.")

    # Explicit schema column mapping based on data inspection
    batter_col = "batter"
    bowler_col = "bowler"
    over_col = "over_number"
    runs_col = "batter_runs"
    total_runs_col = "total_runs"
    wides_col = "wides_runs" if "wides_runs" in df.columns else None
    noballs_col = "noballs_runs" if "noballs_runs" in df.columns else None
    dismissal_col = "dismissal_count" if "dismissal_count" in df.columns else "dismissal_type"

    exact_lookup, norm_lookup = get_mapping_lookups()

    print("Mapping canonical identities for batters and bowlers...")
    b_res = df[batter_col].apply(lambda x: resolve_name(x, exact_lookup, norm_lookup))
    df["batter_canonical_id"] = [r[0] for r in b_res]
    df["batter_canonical_name"] = [r[1] for r in b_res]

    bw_res = df[bowler_col].apply(lambda x: resolve_name(x, exact_lookup, norm_lookup))
    df["bowler_canonical_id"] = [r[0] for r in bw_res]
    df["bowler_canonical_name"] = [r[1] for r in bw_res]

    # Handle 0-indexed vs 1-indexed over numbers cleanly
    min_over = df[over_col].min()
    print(f"Detected minimum over_number: {min_over}")

    def assign_phase(o):
        try:
            val = float(o)
            if min_over == 0:
                # 0..5 -> Powerplay (overs 1-6), 6..14 -> Middle (overs 7-15), 15+ -> Death (overs 16-20)
                if val <= 5: return "Powerplay"
                elif val <= 14: return "Middle"
                else: return "Death"
            else:
                # 1..6 -> Powerplay, 7..15 -> Middle, 16+ -> Death
                if val <= 6: return "Powerplay"
                elif val <= 15: return "Middle"
                else: return "Death"
        except:
            return "Unknown"

    df["phase"] = df[over_col].apply(assign_phase)

    # Resolution Verification Metrics
    resolved_batters = (df["batter_canonical_id"] != "UNRESOLVED").mean() * 100
    resolved_bowlers = (df["bowler_canonical_id"] != "UNRESOLVED").mean() * 100
    print("\n--- Canonical Identity Resolution Accuracy ---")
    print(f" - Batter Mapping Rate: {resolved_batters:.2f}%")
    print(f" - Bowler Mapping Rate: {resolved_bowlers:.2f}%")

    # Batting Phase Aggregations
    df["is_legal_delivery"] = 1
    if wides_col:
        df["is_legal_delivery"] = (df[wides_col].fillna(0) == 0).astype(int)

    df["is_boundary_four"] = (df[runs_col] == 4).astype(int)
    df["is_boundary_six"] = (df[runs_col] == 6).astype(int)
    df["is_dot_ball"] = ((df[runs_col] == 0) & (df["is_legal_delivery"] == 1)).astype(int)

    bat_df = df[df["batter_canonical_id"] != "UNRESOLVED"].groupby(
        ["batter_canonical_id", "batter_canonical_name", "phase"]
    ).agg(
        runs_scored=(runs_col, "sum"),
        balls_faced=("is_legal_delivery", "sum"),
        fours=("is_boundary_four", "sum"),
        sixes=("is_boundary_six", "sum"),
        dot_balls=("is_dot_ball", "sum")
    ).reset_index()

    bat_df["strike_rate"] = np.round((bat_df["runs_scored"] / bat_df["balls_faced"].replace(0, 1)) * 100, 2)
    bat_df["boundary_pct"] = np.round(((bat_df["fours"] + bat_df["sixes"]) / bat_df["balls_faced"].replace(0, 1)) * 100, 2)
    bat_df["dot_pct"] = np.round((bat_df["dot_balls"] / bat_df["balls_faced"].replace(0, 1)) * 100, 2)

    # Bowling Phase Aggregations
    # NOTE: dismissal_count is pandas nullable Int64, which `dtype in [int, float]`
    # does not match (that checks against Python's built-in types, not pandas
    # ExtensionDtypes). That previously fell through to `.notna()`, which is True
    # for every row -- including dismissal_count == 0 rows -- flagging 100% of
    # deliveries as wickets. Use pd.api.types.is_numeric_dtype and compare > 0
    # regardless of dtype family.
    df["is_wicket"] = 0
    if dismissal_col in df.columns:
        if pd.api.types.is_numeric_dtype(df[dismissal_col]):
            df["is_wicket"] = (df[dismissal_col].fillna(0) > 0).astype(int)
        else:
            df["is_wicket"] = df[dismissal_col].notna().astype(int)

    bowl_df = df[df["bowler_canonical_id"] != "UNRESOLVED"].groupby(
        ["bowler_canonical_id", "bowler_canonical_name", "phase"]
    ).agg(
        runs_conceded=(total_runs_col, "sum"),
        balls_bowled=("is_legal_delivery", "sum"),
        wickets=("is_wicket", "sum"),
        dots_bowled=("is_dot_ball", "sum")
    ).reset_index()

    bowl_df["economy_rate"] = np.round((bowl_df["runs_conceded"] / (bowl_df["balls_bowled"].replace(0, 1) / 6.0)), 2)
    bowl_df["bowling_strike_rate"] = np.where(
        bowl_df["wickets"] > 0,
        np.round(bowl_df["balls_bowled"] / bowl_df["wickets"], 2),
        np.nan
    )

    # Save Cleaned Fact Deliveries and Phase Features
    out_fact_csv = processed_dir / "fact_deliveries.csv"
    out_fact_parquet = processed_dir / "fact_deliveries.parquet"
    out_bat_csv = processed_dir / "player_phase_features.csv"
    out_bat_parquet = processed_dir / "player_phase_features.parquet"
    out_bowl_csv = processed_dir / "bowler_phase_features.csv"

    df.to_csv(out_fact_csv, index=False)
    df.to_parquet(out_fact_parquet, index=False)
    bat_df.to_csv(out_bat_csv, index=False)
    bat_df.to_parquet(out_bat_parquet, index=False)
    bowl_df.to_csv(out_bowl_csv, index=False)

    print("\nPhase-wise Feature Stores Generated:")
    print(f" - Fact Deliveries: {out_fact_csv} ({len(df):,} rows)")
    print(f" - Batting Phase Metrics: {out_bat_csv} ({len(bat_df):,} rows)")
    print(f" - Bowling Phase Metrics: {out_bowl_csv} ({len(bowl_df):,} rows)")

if __name__ == "__main__":
    main()
