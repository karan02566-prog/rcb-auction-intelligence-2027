import json
import pandas as pd
from pathlib import Path

def generate_rcb_target_shortlist():
    input_path = Path("data/processed/player_valuations_predicted.csv")
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        raise FileNotFoundError(f"Missing predictions file at {input_path}")

    df = pd.read_csv(input_path)

    # Filter for underpriced players (target opportunities)
    underpriced_df = df[df["market_status"] == "Underpriced (Target)"].copy()

    # Calculate Value Margin Ratio (Predicted / Latest Price)
    underpriced_df["value_margin_ratio"] = (
        underpriced_df["predicted_valuation"] / underpriced_df["latest_sold_price"].replace(0, 1)
    ).round(2)

    # Sort targets by valuation differential
    underpriced_df = underpriced_df.sort_values(by="valuation_diff", ascending=False)

    # Select key analytical fields
    output_cols = [
        "canonical_name",
        "primary_role",
        "nationality",
        "total_matches_played",
        "latest_sold_price",
        "predicted_valuation",
        "valuation_diff",
        "value_margin_ratio"
    ]
    
    targets_export = underpriced_df[output_cols]

    out_csv = reports_dir / "rcb_auction_target_shortlist.csv"
    targets_export.to_csv(out_csv, index=False)

    # Build executive strategy summary by role
    role_summary = {}
    for role, group in targets_export.groupby("primary_role"):
        top_3 = group.head(3)[["canonical_name", "valuation_diff", "value_margin_ratio"]].to_dict("records")
        role_summary[role] = {
            "total_underpriced_targets": len(group),
            "top_value_picks": top_3
        }

    summary = {
        "total_players_evaluated": len(df),
        "total_underpriced_targets_found": len(targets_export),
        "role_breakdown": role_summary
    }

    out_json = reports_dir / "rcb_strategy_summary.json"
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"RCB Auction Target Analysis Complete:")
    print(f" - Identified Targets: {len(targets_export)} underpriced players")
    print(f" - Exported Shortlist CSV: {out_csv}")
    print(f" - Saved Strategy Summary: {out_json}")

if __name__ == "__main__":
    generate_rcb_target_shortlist()
