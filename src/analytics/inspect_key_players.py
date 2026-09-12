import pandas as pd
from pathlib import Path

target_tokens = ["Salt", "Buttler", "Abhishek", "Abhisek", "Bhuvneshwar", "Bumrah", "Tim David"]
pattern = "|".join(target_tokens)

bat_file = Path("data/processed/player_phase_features.csv")
bowl_file = Path("data/processed/bowler_phase_features.csv")

if bat_file.exists():
    bat_df = pd.read_csv(bat_file)
    filtered_bat = bat_df[bat_df["batter_canonical_name"].str.contains(pattern, case=False, na=False)].sort_values(by=["batter_canonical_name", "phase"])
    print("=" * 95)
    print("BATTING PHASE PERFORMANCE METRICS")
    print("=" * 95)
    bat_cols = ["batter_canonical_name", "phase", "runs_scored", "balls_faced", "fours", "sixes", "strike_rate", "boundary_pct", "dot_pct"]
    print(filtered_bat[bat_cols].to_string(index=False))

if bowl_file.exists():
    bowl_df = pd.read_csv(bowl_file)
    filtered_bowl = bowl_df[bowl_df["bowler_canonical_name"].str.contains(pattern, case=False, na=False)].sort_values(by=["bowler_canonical_name", "phase"])
    print("\n" + "=" * 95)
    print("BOWLING PHASE PERFORMANCE METRICS")
    print("=" * 95)
    bowl_cols = ["bowler_canonical_name", "phase", "runs_conceded", "balls_bowled", "wickets", "dots_bowled", "economy_rate", "bowling_strike_rate"]
    print(filtered_bowl[bowl_cols].to_string(index=False))
