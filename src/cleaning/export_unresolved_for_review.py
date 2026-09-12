import json
import pandas as pd
from pathlib import Path

def export_unresolved_review():
    mapping_path = Path("configs/player_mapping.json")
    fuzzy_path = Path("reports/fuzzy_auction_candidates.json")

    mapping_data = json.loads(mapping_path.read_text(encoding="utf-8"))
    unresolved_items = mapping_data.get("unresolved", [])

    fuzzy_candidates = {}
    if fuzzy_path.exists():
        fuzzy_data = json.loads(fuzzy_path.read_text(encoding="utf-8"))
        for item in fuzzy_data:
            fuzzy_candidates[item["source_name"]] = item.get("top_candidates", [])

    review_rows = []
    for item in unresolved_items:
        src_name = item["source_name"]
        candidates = fuzzy_candidates.get(src_name, [])

        top_1 = candidates[0] if len(candidates) > 0 else {}
        top_2 = candidates[1] if len(candidates) > 1 else {}

        review_rows.append({
            "source_name": src_name,
            "category": item.get("category", "unresolved"),
            "suggested_id_1": top_1.get("canonical_id", ""),
            "suggested_name_1": top_1.get("canonical_name", ""),
            "score_1": top_1.get("score", ""),
            "suggested_id_2": top_2.get("canonical_id", ""),
            "suggested_name_2": top_2.get("canonical_name", ""),
            "score_2": top_2.get("score", "")
        })

    df = pd.DataFrame(review_rows)
    output_path = Path("reports/unresolved_players_manual_review.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    summary = {
        "total_mapped_entities": len(mapping_data.get("mapped", [])),
        "total_unresolved_entities": len(unresolved_items),
        "manual_review_csv": str(output_path)
    }

    summary_path = Path("reports/entity_resolution_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Exported {len(df)} unresolved player records to: {output_path}")
    print(f"Saved resolution summary to: {summary_path}")

if __name__ == "__main__":
    export_unresolved_review()
