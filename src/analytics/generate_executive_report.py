import json
import pandas as pd
from pathlib import Path

def generate_markdown_report():
    summary_path = Path("reports/rcb_strategy_summary.json")
    csv_path = Path("reports/rcb_auction_target_shortlist.csv")
    out_report_path = Path("reports/RCB_Auction_Strategy_Report.md")
    
    if not summary_path.exists() or not csv_path.exists():
        raise FileNotFoundError("Missing target shortlist CSV or strategy summary JSON.")
        
    summary_data = json.loads(summary_path.read_text(encoding="utf-8"))
    df = pd.read_csv(csv_path)
    
    report_lines = [
        "# RCB IPL Auction Analytical Strategy Report",
        "",
        "## Executive Overview",
        f"- **Total Players Evaluated**: {summary_data.get('total_players_evaluated', len(df))}",
        f"- **Total Underpriced Opportunities Identified**: {summary_data.get('total_underpriced_targets_found', len(df))}",
        "",
        "## Top Underpriced Value Targets by Role",
        ""
    ]
    
    for role in df["primary_role"].unique():
        if pd.isna(role):
            continue
        role_df = df[df["primary_role"] == role].head(5)
        report_lines.append(f"### Role: {role}")
        report_lines.append("| Player Name | Nationality | Matches | Latest Price | Model Valuation | Valuation Diff | Value Margin |")
        report_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for _, row in role_df.iterrows():
            report_lines.append(
                f"| {row['canonical_name']} | {row['nationality']} | {int(row['total_matches_played'])} | "
                f"₹{row['latest_sold_price']:,.0f} | ₹{row['predicted_valuation']:,.0f} | "
                f"+₹{row['valuation_diff']:,.0f} | {row['value_margin_ratio']}x |"
            )
        report_lines.append("")
        
    out_report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"Executive Strategy Report successfully generated at: {out_report_path}")

if __name__ == "__main__":
    generate_markdown_report()
