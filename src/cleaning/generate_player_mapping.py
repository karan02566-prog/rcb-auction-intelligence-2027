import json
import hashlib
import subprocess
from pathlib import Path

def run_audit_and_verify():
    audit_script = Path("src/cleaning/player_identity_audit.py")
    ambiguity_json = Path("reports/player_identity_ambiguity.json")
    
    subprocess.run(["python", str(audit_script)], check=True)
    hash1 = hashlib.sha256(ambiguity_json.read_bytes()).hexdigest()
    
    subprocess.run(["python", str(audit_script)], check=True)
    hash2 = hashlib.sha256(ambiguity_json.read_bytes()).hexdigest()
    
    assert hash1 == hash2, "Audit output is non-deterministic!"
    print(f"Audit determinism verified. SHA-256: {hash1}")
    return json.loads(ambiguity_json.read_text(encoding="utf-8"))

def parse_entry(item, default_method, default_confidence):
    source_name = item.get("name") or item.get("source_name")
    register_rows = item.get("register_rows", [])
    if register_rows and isinstance(register_rows, list) and len(register_rows) > 0:
        reg = register_rows[0]
        canonical_id = reg.get("identifier") or reg.get("key_cricinfo") or reg.get("unique_name")
        canonical_name = reg.get("unique_name") or reg.get("name")
    else:
        canonical_id = item.get("canonical_id") or "UNRESOLVED"
        canonical_name = item.get("canonical_name") or source_name

    return {
        "source_name": source_name,
        "canonical_id": canonical_id,
        "canonical_name": canonical_name,
        "method": default_method,
        "confidence": default_confidence,
        "evidence": item.get("evidence", f"{default_method} match against register")
    }

def build_player_mapping():
    data = run_audit_and_verify()
    
    mapped_entries = []
    unresolved_entries = []
    
    for item in data.get("exact_matches", []):
        parsed = parse_entry(item, "exact_match", "exact")
        if parsed["source_name"]:
            mapped_entries.append(parsed)
            
    for item in data.get("initials_pattern_candidates", []):
        parsed = parse_entry(item, "initials_pattern_match", "medium")
        if parsed["source_name"]:
            mapped_entries.append(parsed)

    unresolved_keys = [
        "ambiguous_exact", 
        "ambiguous_normalized", 
        "ambiguous_initials", 
        "no_register_entry",
        "genuinely_unmatched_after_initials",
        "unmatched"
    ]
    
    seen_unresolved = set()
    for key in unresolved_keys:
        items = data.get(key, [])
        for item in items:
            name = item if isinstance(item, str) else (item.get("name") or item.get("source_name"))
            if name and name not in seen_unresolved:
                seen_unresolved.add(name)
                unresolved_entries.append({
                    "source_name": name,
                    "category": key,
                    "evidence": "Unresolved ambiguity; retained without auto-merging."
                })

    output_data = {
        "mapped": mapped_entries,
        "unresolved": unresolved_entries
    }
    
    output_path = Path("configs/player_mapping.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output_data, indent=2), encoding="utf-8")
    
    print(f"\nMapping Results Saved to {output_path}:")
    print(f" - Mapped Entries: {len(mapped_entries)}")
    print(f" - Unresolved Entries: {len(unresolved_entries)}")

if __name__ == "__main__":
    build_player_mapping()
