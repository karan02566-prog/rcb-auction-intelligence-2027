import json
import re
import pandas as pd
from difflib import SequenceMatcher
from pathlib import Path
from collections import defaultdict

def similarity_score(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def get_tokens(text: str):
    return set(re.findall(r'[a-zA-Z]+', str(text).lower()))

def generate_auction_candidates():
    mapping_path = Path("configs/player_mapping.json")
    people_path = Path("data/raw/people.csv")
    
    if not mapping_path.exists() or not people_path.exists():
        raise FileNotFoundError("Missing mapping JSON or people.csv raw file.")

    mapping_data = json.loads(mapping_path.read_text(encoding="utf-8"))
    unresolved_list = mapping_data.get("unresolved", [])

    people_df = pd.read_csv(people_path)
    
    # Pre-index registry by word-initial tokens to eliminate 95%+ redundant comparisons
    token_index = defaultdict(list)
    records = people_df[["identifier", "name", "unique_name"]].dropna(subset=["identifier"]).to_dict("records")
    
    for reg in records:
        target_name = str(reg["unique_name"] if pd.notna(reg["unique_name"]) else reg["name"])
        tokens = get_tokens(target_name)
        record = (reg["identifier"], target_name)
        for t in tokens:
            if len(t) > 1:
                token_index[t[0]].append(record)

    candidates = []
    
    for item in unresolved_list:
        src_name = item["source_name"]
        src_tokens = get_tokens(src_name)
        
        # Build restricted candidate pool matching first letters of tokens
        candidate_pool = []
        for t in src_tokens:
            if t[0] in token_index:
                candidate_pool.extend(token_index[t[0]])
                
        if not candidate_pool:
            continue

        seen_cids = set()
        best_matches = []

        for cid, target_name in candidate_pool:
            if cid in seen_cids:
                continue
            seen_cids.add(cid)
            
            score = similarity_score(src_name, target_name)
            if score >= 0.70:
                best_matches.append({
                    "canonical_id": cid,
                    "canonical_name": target_name,
                    "score": round(score, 3)
                })

        best_matches = sorted(best_matches, key=lambda x: x["score"], reverse=True)[:3]

        if best_matches:
            candidates.append({
                "source_name": src_name,
                "top_candidates": best_matches
            })

    output_path = Path("reports/fuzzy_auction_candidates.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(candidates, indent=2), encoding="utf-8")
    
    print(f"Generated {len(candidates)} fuzzy candidate suggestions in {output_path}")

if __name__ == "__main__":
    generate_auction_candidates()
