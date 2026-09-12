import json
from pathlib import Path

def apply_overrides():
    candidates_path = Path("reports/fuzzy_auction_candidates.json")
    mapping_path = Path("configs/player_mapping.json")
    overrides_path = Path("configs/player_mapping_overrides.json")

    if not candidates_path.exists() or not mapping_path.exists():
        raise FileNotFoundError("Missing fuzzy candidates report or master mapping JSON.")

    candidates_data = json.loads(candidates_path.read_text(encoding="utf-8"))
    mapping_data = json.loads(mapping_path.read_text(encoding="utf-8"))

    accepted_overrides = []
    auto_accepted_names = set()

    # Rule-based auto-acceptance threshold
    SCORE_THRESHOLD = 0.82

    for item in candidates_data:
        src_name = item["source_name"]
        top_candidates = item.get("top_candidates", [])
        
        if not top_candidates:
            continue
            
        best = top_candidates[0]
        score = best["score"]

        # Accept if score >= threshold or if top match is substantially ahead of second choice
        is_clear_winner = (
            score >= SCORE_THRESHOLD or 
            (len(top_candidates) > 1 and (score - top_candidates[1]["score"]) >= 0.20 and score >= 0.75) or
            (len(top_candidates) == 1 and score >= 0.78)
        )

        if is_clear_winner:
            accepted_overrides.append({
                "source_name": src_name,
                "canonical_id": best["canonical_id"],
                "canonical_name": best["canonical_name"],
                "method": "fuzzy_string_matching",
                "confidence": "high" if score >= 0.88 else "medium",
                "score": score,
                "evidence": f"Auto-accepted fuzzy match with score {score}"
            })
            auto_accepted_names.add(src_name)

    # Save overrides configuration
    overrides_path.parent.mkdir(parents=True, exist_ok=True)
    overrides_path.write_text(json.dumps(accepted_overrides, indent=2), encoding="utf-8")

    # Update master player mapping JSON
    existing_mapped = mapping_data.get("mapped", [])
    existing_unresolved = mapping_data.get("unresolved", [])

    updated_mapped = existing_mapped + accepted_overrides
    updated_unresolved = [u for u in existing_unresolved if u["source_name"] not in auto_accepted_names]

    new_mapping_data = {
        "mapped": updated_mapped,
        "unresolved": updated_unresolved
    }

    mapping_path.write_text(json.dumps(new_mapping_data, indent=2), encoding="utf-8")

    print(f"Auto-accepted {len(accepted_overrides)} high-confidence fuzzy matches.")
    print(f"Saved overrides to: {overrides_path}")
    print(f"Updated master mapping: {len(updated_mapped)} mapped | {len(updated_unresolved)} remaining unresolved.")

if __name__ == "__main__":
    apply_overrides()
