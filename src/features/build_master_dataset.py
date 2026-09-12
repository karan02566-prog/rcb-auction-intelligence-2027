import pandas as pd
from pathlib import Path

def build_master_dataset():
    cleaned_dir = Path("data/cleaned")
    processed_dir = Path("data/processed")
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    auction_path = cleaned_dir / "auction" / "ipl_auction_history.csv"
    perf_path = cleaned_dir / "metadata" / "player_competition_summary.csv"
    
    if not auction_path.exists() or not perf_path.exists():
        raise FileNotFoundError("Cleaned auction or performance summary datasets are missing.")
        
    auction_df = pd.read_csv(auction_path)
    perf_df = pd.read_csv(perf_path)
    
    # Filter valid canonical identities
    valid_auction = auction_df[auction_df["player_name_canonical_id"] != "UNRESOLVED"].copy()
    valid_perf = perf_df[perf_df["player_name_canonical_id"] != "UNRESOLVED"].copy()
    
    # Aggregate historical auction metrics
    auction_agg = valid_auction.groupby("player_name_canonical_id").agg(
        canonical_name=("player_name_canonical_name", "first"),
        times_in_auction=("year", "count"),
        max_sold_price=("sold_price", "max"),
        avg_sold_price=("sold_price", "mean"),
        latest_sold_price=("sold_price", "last"),
        primary_role=("role", lambda x: x.mode()[0] if not x.mode().empty else "Unknown"),
        nationality=("nationality", "first")
    ).reset_index()
    
    # Aggregate match performance metrics
    perf_agg = valid_perf.groupby("player_name_canonical_id").agg(
        total_matches_played=("matches", "sum"),
        competitions_count=("competition", "nunique")
    ).reset_index()
    
    # Join into unified player master profile
    master_df = pd.merge(auction_agg, perf_agg, on="player_name_canonical_id", how="left")
    master_df["total_matches_played"] = master_df["total_matches_played"].fillna(0).astype(int)
    master_df["competitions_count"] = master_df["competitions_count"].fillna(0).astype(int)
    
    output_path = processed_dir / "master_player_features.csv"
    master_df.to_csv(output_path, index=False)
    
    print(f"Master Player Feature Store successfully generated!")
    print(f" - Unified Player Profiles: {len(master_df)}")
    print(f" - Saved to: {output_path}")

if __name__ == "__main__":
    build_master_dataset()
