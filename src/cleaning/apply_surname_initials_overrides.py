import json
import re
import pandas as pd
from pathlib import Path

def get_tokens(name_str):
    cleaned = re.sub(r'[^\w\s]', '', str(name_str).lower()).strip()
    return [t for t in cleaned.split() if t]

def match_surname_initials(src_name, target_name):
    src_tokens = get_tokens(src_name)
    tgt_tokens = get_tokens(target_name)
    
    if not src_tokens or not tgt_tokens:
        return False
        
    # Check if last names (surnames) match exactly
    if src_tokens[-1] != tgt_tokens[-1]:
        return False
        
    # Check if first initials match
    src_first = src_tokens[0]
    tgt_first = tgt_tokens[0]
    
    if src_first[0] == tgt_first[0]:
        return True
        
    return False

def apply_surname_initials_pass():
    mapping_path = Path("configs/player_mapping.json")
    people_path = Path("data/raw/people.csv")
    overrides_path = Path("configs/player_mapping_overrides.json")

    mapping_data = json.loads(mapping_path.read_text(encoding="utf-8"))
    people_df = pd.read_csv(people_path)

    unresolved = mapping_data.get("unresolved", [])
    records = people_df[["identifier", "name", "unique_name"]].dropna(subset=["identifier"]).to_dict("records")

    accepted = []
    resolved_names = set()

    for item in unresolved:
        src_name = item["source_name"]
        matches = []

        for reg in records:
            tgt_name = str(reg["unique_name"] if pd.notna(reg["unique_name"]) else reg["name"])
            if match_surname_initials(src_name, tgt_name):
                matches.append({
                    "canonical_id": reg["identifier"],
                    "canonical_name": tgt_name
                })

        # Accept only if unambiguous single match
        if len(matches) == 1:
            accepted.append({
                "source_name": src_name,
                "canonical_id": matches[0]["canonical_id"],
                "canonical_name": matches[0]["canonical_name"],
                "method": "surname_initials_matching",
                "confidence": "high",
                "evidence": f"Unambiguous surname + initial match to {matches[0]['canonical_name']}"
            })
            resolved_names.add(src_name)

    # Load existing overrides
    existing_overrides = []
    if overrides_path.exists():
        existing_overrides = json.loads(overrides_path.read_text(encoding="utf-8"))

    all_overrides = existing_overrides + accepted
    overrides_path.write_text(json.dumps(all_overrides, indent=2), encoding="utf-8")

    # Update mapping
    updated_mapped = mapping_data.get("mapped", []) + accepted
    updated_unresolved = [u for u in unresolved if u["source_name"] not in resolved_names]

    new_mapping_data = {
        "mapped": updated_mapped,
        "unresolved": updated_unresolved
    }
    mapping_path.write_text(json.dumps(new_mapping_data, indent=2), encoding="utf-8")

    print(f"Accepted {len(accepted)} unambiguous surname+initial matches.")
    print(f"Remaining unresolved: {len(updated_unresolved)}")

if __name__ == "__main__":
    apply_surname_initials_pass()
