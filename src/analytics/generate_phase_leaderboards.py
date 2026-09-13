import re
import pandas as pd
import numpy as np
from pathlib import Path

def extract_start_year(val):
    if pd.isna(val):
        return None
    match = re.search(r'\b(20\d{2})\b', str(val))
    return int(match.group(1)) if match else None

def compute_phase_metrics(df, min_balls=30):
    df_valid = df[df["batter_canonical_id"] != "UNRESOLVED"].copy()
    
    # Core aggregations
    grouped = df_valid.groupby(["batter_canonical_id", "batter_canonical_name", "phase"]).agg(
        runs_scored=("batter_runs", "sum"),
        balls_faced=("is_legal_delivery", "sum"),
        fours=("is_boundary_four", "sum"),
        sixes=("is_boundary_six", "sum"),
        dot_balls=("is_dot_ball", "sum")
    ).reset_index()

    # Apply minimum sample size filter
    filtered = grouped[grouped["balls_faced"] >= min_balls].copy()

    # Derived KPIs
    filtered["strike_rate"] = np.round((filtered["runs_scored"] / filtered["balls_faced"].replace(0, 1)) * 100, 2)
    filtered["boundary_pct"] = np.round(((filtered["fours"] + filtered["sixes"]) / filtered["balls_faced"].replace(0, 1)) * 100, 2)
    filtered["dot_pct"] = np.round((filtered["dot_balls"] / filtered["balls_faced"].replace(0, 1)) * 100, 2)
    filtered["boundary_runs_pct"] = np.round((((filtered["fours"] * 4) + (filtered["sixes"] * 6)) / filtered["runs_scored"].replace(0, 1)) * 100, 2)

    return filtered

def generate_leaderboards():
    processed_dir = Path("data/processed")
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    deliv_file = processed_dir / "fact_deliveries.parquet"
    if not deliv_file.exists():
        deliv_file = processed_dir / "fact_deliveries.csv"

    if not deliv_file.exists():
        raise FileNotFoundError("fact_deliveries not found. Run Phase 2.5 build script first.")

    df = pd.read_parquet(deliv_file) if str(deliv_file).endswith(".parquet") else pd.read_csv(deliv_file)

    # Attach numeric year for temporal windowing
    season_col = next((c for c in ["season", "year"] if c in df.columns), None)
    if season_col:
        df["year_clean"] = df[season_col].apply(extract_start_year)
    else:
        df["year_clean"] = 2026

    # 1. Overall Career Aggregations (2013-2026)
    career_metrics = compute_phase_metrics(df, min_balls=40)
    career_metrics["window"] = "Career (2013-2026)"

    # 2. Recent 3-Year Aggregations (2024-2026)
    recent_df = df[df["year_clean"] >= 2024]
    recent_metrics = compute_phase_metrics(recent_df, min_balls=25)
    recent_metrics["window"] = "Recent Form (2024-2026)"

    # Export Unified Phase Performance Databases
    career_out = reports_dir / "player_phase_career_stats.csv"
    recent_out = reports_dir / "player_phase_recent_stats.csv"
    career_metrics.to_csv(career_out, index=False)
    recent_metrics.to_csv(recent_out, index=False)

    # 3. Generate Top 30 Phase Leaderboards
    combined = pd.concat([career_metrics, recent_metrics], ignore_index=True)

    top_leaderboards = []
    phases = ["Powerplay", "Middle", "Death"]
    windows = ["Career (2013-2026)", "Recent Form (2024-2026)"]

    for window in windows:
        for phase in phases:
            sub = combined[(combined["window"] == window) & (combined["phase"] == phase)]

            # Top 30 by Strike Rate
            top_sr = sub.sort_values(by="strike_rate", ascending=False).head(30).copy()
            top_sr["metric_rank_type"] = "Top Strike Rate"
            top_leaderboards.append(top_sr)

            # Top 30 by Boundary %
            top_bound = sub.sort_values(by="boundary_pct", ascending=False).head(30).copy()
            top_bound["metric_rank_type"] = "Top Boundary %"
            top_leaderboards.append(top_bound)

            # Top 30 Lowest Dot % (Best Strike Rotators)
            top_dot = sub.sort_values(by="dot_pct", ascending=True).head(30).copy()
            top_dot["metric_rank_type"] = "Lowest Dot %"
            top_leaderboards.append(top_dot)

    final_leaderboards = pd.concat(top_leaderboards, ignore_index=True)
    leaderboard_out = reports_dir / "phase_batsmen_top30_leaderboards.csv"
    final_leaderboards.to_csv(leaderboard_out, index=False)

    print("Successfully Generated Dual-Window Phase Analytics:")
    print(f" - Career Stats Exported: {career_out} ({len(career_metrics):,} rows)")
    print(f" - Recent 3-Yr Stats Exported: {recent_out} ({len(recent_metrics):,} rows)")
    print(f" - Top 30 Leaderboards Master File: {leaderboard_out} ({len(final_leaderboards):,} rows)")

if __name__ == "__main__":
    generate_leaderboards()
