"""Build a read-only inventory and ambiguity report for player identities."""

from __future__ import annotations

import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DELIVERIES_PATH = PROJECT_ROOT / "data" / "interim" / "deliveries.parquet"
IDENTITY_PATH = PROJECT_ROOT / "data" / "raw" / "metadata" / "player_identity.csv"
PARTICIPATION_PATH = PROJECT_ROOT / "data" / "raw" / "metadata" / "player_participation.csv"
AUCTION_PATH = PROJECT_ROOT / "data" / "raw" / "auction" / "ipl_auction_history.csv"
REPORT_DIR = PROJECT_ROOT / "reports"
MARKDOWN_PATH = REPORT_DIR / "player_identity_audit.md"
JSON_PATH = REPORT_DIR / "player_identity_ambiguity.json"

NAME_FIELDS = ("batter", "bowler", "non_striker")
SOURCE_LABELS = {
    "deliveries": "deliveries.parquet",
    "auction": "ipl_auction_history.csv",
    "participation": "player_participation.csv",
    "identity": "player_identity.csv",
}


def _clean_name(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    name = str(value).strip()
    return name or None


def _compact_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.casefold())


def _tokens(name: str) -> list[str]:
    return re.findall(r"[a-z]+", name.casefold())


def _initial_signature(name: str) -> str:
    return "".join(token[0] for token in _tokens(name))


def _surname_and_initial(name: str) -> tuple[str, str] | None:
    tokens = _tokens(name)
    if len(tokens) < 2:
        return None
    return tokens[-1], tokens[0][0]


def _extract_fielder_names(value: Any) -> Iterable[str]:
    if value is None or pd.isna(value):
        return
    try:
        wickets = json.loads(str(value))
    except (TypeError, json.JSONDecodeError):
        return
    if not isinstance(wickets, list):
        return
    for wicket in wickets:
        if not isinstance(wicket, dict):
            continue
        fielders = wicket.get("fielders") or []
        if isinstance(fielders, dict):
            fielders = [fielders]
        for fielder in fielders:
            if isinstance(fielder, dict):
                name = _clean_name(fielder.get("name"))
                if name:
                    yield name


def _add_observation(observations: dict[str, dict[str, Any]], name: str, source: str, count: int = 1) -> None:
    record = observations.setdefault(name, {"sources": set(), "occurrences": {}})
    record["sources"].add(source)
    record["occurrences"][source] = record["occurrences"].get(source, 0) + count


def _load_observations() -> tuple[dict[str, dict[str, Any]], pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    deliveries = pd.read_parquet(DELIVERIES_PATH)
    identity = pd.read_csv(IDENTITY_PATH, dtype=str, keep_default_na=False)
    participation = pd.read_csv(PARTICIPATION_PATH, dtype=str, keep_default_na=False)
    auction = pd.read_csv(AUCTION_PATH, dtype=str, keep_default_na=False)
    observations: dict[str, dict[str, Any]] = {}

    for field in NAME_FIELDS:
        for name, count in deliveries[field].dropna().astype(str).value_counts().items():
            cleaned = _clean_name(name)
            if cleaned:
                _add_observation(observations, cleaned, "deliveries", int(count))
    for value in deliveries["wickets_json"].dropna():
        for name in _extract_fielder_names(value):
            _add_observation(observations, name, "deliveries", 1)
    for name, count in auction["player_name"].map(_clean_name).dropna().value_counts().items():
        _add_observation(observations, name, "auction", int(count))
    return observations, deliveries, identity, participation, auction


def _reference_names(identity: pd.DataFrame, participation: pd.DataFrame) -> set[str]:
    names: set[str] = set()
    for column in ("name", "unique_name"):
        names.update(str(name) for name in identity[column].dropna().astype(str).unique())
    names.update(str(name) for name in participation["player_name"].dropna().astype(str).unique())
    return names


def _participation_evidence(participation: pd.DataFrame) -> dict[str, set[tuple[str, str]]]:
    evidence: dict[str, set[tuple[str, str]]] = {}
    relevant = participation[["player_name", "team", "season"]].dropna(subset=["player_name"])
    for name, team, season in relevant.itertuples(index=False, name=None):
        evidence.setdefault(str(name), set()).add((str(team), str(season)))
    return evidence


def _candidate_pairs(names: list[str], participation: pd.DataFrame) -> list[dict[str, Any]]:
    evidence = _participation_evidence(participation)
    blocks: dict[tuple[str, int], set[str]] = {}
    for name in names:
        compact = _compact_name(name)
        if compact:
            blocks.setdefault((compact[0], len(compact)), set()).add(name)
    comparison_pairs: set[tuple[str, str]] = set()
    for block_names in blocks.values():
        ordered = sorted(block_names)
        for index, left in enumerate(ordered):
            for right in ordered[index + 1:]:
                if _initial_signature(left) == _initial_signature(right):
                    comparison_pairs.add((left, right))
                else:
                    left_context = evidence.get(left, set())
                    right_context = evidence.get(right, set())
                    if left_context & right_context:
                        comparison_pairs.add((left, right))
    compact_groups: dict[str, list[str]] = {}
    for name in names:
        compact_groups.setdefault(_compact_name(name), []).append(name)
    for group_names in compact_groups.values():
        for index, left in enumerate(sorted(group_names)):
            for right in sorted(group_names)[index + 1:]:
                comparison_pairs.add((left, right))
    pairs: list[dict[str, Any]] = []
    for left, right in sorted(comparison_pairs):
        left_compact = _compact_name(left)
        left_tokens = _tokens(left)
        right_compact = _compact_name(right)
        same_compact = left_compact == right_compact
        ratio = SequenceMatcher(None, left_compact, right_compact).ratio()
        shared_context = evidence.get(left, set()) & evidence.get(right, set())
        same_initials = _initial_signature(left) == _initial_signature(right)
        if not same_compact and not (ratio >= 0.94 and (same_initials or shared_context)):
            continue
        if same_compact:
            reason = "same alphanumeric spelling after removing punctuation and spacing"
            confidence = "high_candidate"
        elif shared_context:
            reason = f"edit similarity {ratio:.3f}; shared team-season context: {sorted(shared_context)[:5]}"
            confidence = "medium_candidate"
        else:
            reason = f"edit similarity {ratio:.3f}; matching token initials"
            confidence = "low_candidate"
        pairs.append({
            "names": [left, right],
            "reasoning": reason,
            "confidence": confidence,
            "evidence": {
                "compact_names": [left_compact, right_compact],
                "initial_signatures": [_initial_signature(left), _initial_signature(right)],
                "shared_team_seasons": [list(item) for item in sorted(shared_context)],
            },
        })
    return pairs


def _register_records(identity: pd.DataFrame) -> list[dict[str, str]]:
    records: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in identity.itertuples(index=False):
        identifier = _clean_name(getattr(row, "identifier", "")) or ""
        name = _clean_name(getattr(row, "name", "")) or ""
        unique_name = _clean_name(getattr(row, "unique_name", "")) or ""
        key = (identifier, name, unique_name)
        if not any(key):
            continue
        record = records.setdefault(key, {
            "identifier": identifier,
            "name": name,
            "unique_name": unique_name,
        })
        record["source"] = "player_identity.csv / people.csv"
    return list(records.values())


def _register_lookup(identity: pd.DataFrame) -> dict[str, list[dict[str, str]]]:
    lookup: dict[str, list[dict[str, str]]] = {}
    for record in _register_records(identity):
        for value in (record["name"], record["unique_name"]):
            if value:
                lookup.setdefault(value, []).append(record)
    return lookup


def _unique_register_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    unique: dict[str, dict[str, str]] = {}
    for row in rows:
        unique[row["identifier"]] = row
    return list(unique.values())


def _resolved_rows_for_candidate(
    candidate: dict[str, Any],
    register_lookup: dict[str, list[dict[str, str]]],
) -> list[dict[str, str]]:
    rows = candidate.get("evidence", {}).get("register_rows")
    if rows:
        return _unique_register_rows(rows)
    names = candidate.get("names", [])
    rows = []
    for name in names[1:]:
        rows.extend(register_lookup.get(name, []))
    if not rows:
        compact = {
            _compact_name(value): record
            for value, records in register_lookup.items()
            for record in records
        }
        for name in names:
            record = compact.get(_compact_name(name))
            if record:
                rows.append(record)
    return _unique_register_rows(rows)


def _normalized_register_candidates(
    unmatched_names: list[str],
    identity: pd.DataFrame,
) -> tuple[list[dict[str, Any]], list[str]]:
    register = _register_records(identity)
    index: dict[str, list[dict[str, str]]] = {}
    for record in register:
        for display_name in (record["name"], record["unique_name"]):
            compact = _compact_name(display_name)
            if compact:
                index.setdefault(compact, []).append(record)
    candidates: list[dict[str, Any]] = []
    remaining: list[str] = []
    for name in unmatched_names:
        matches = index.get(_compact_name(name), [])
        if not matches:
            remaining.append(name)
            continue
        seen: set[tuple[str, str, str]] = set()
        for record in matches:
            key = (record["identifier"], record["name"], record["unique_name"])
            if key in seen:
                continue
            seen.add(key)
            candidates.append({
                "names": [name, record["name"] or record["unique_name"]],
                "reasoning": "same alphanumeric spelling after removing punctuation, spacing, and case",
                "confidence": "high_candidate",
                "evidence": {"register_rows": [record]},
            })
    return candidates, remaining


def _initials_candidates(
    unmatched_names: list[str],
    identity: pd.DataFrame,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    register = _register_records(identity)
    index: dict[tuple[str, str], list[dict[str, str]]] = {}
    for record in register:
        parsed = _surname_and_initial(record["name"] or record["unique_name"])
        if parsed:
            index.setdefault(parsed, []).append(record)
    candidates: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    resolved_names: set[str] = set()
    for name in unmatched_names:
        parsed = _surname_and_initial(name)
        if not parsed:
            continue
        surname, initial = parsed
        matches = index.get((surname, initial), [])
        if len(matches) == 1:
            candidates.append({
                "names": [name, matches[0]["name"] or matches[0]["unique_name"]],
                "reasoning": (
                    f"exact surname {surname!r}; unmatched given name starts with {initial.upper()!r}; "
                    "register record uses an initial-based given name"
                ),
                "confidence": "initials_pattern",
                "evidence": {"register_rows": matches},
            })
            resolved_names.add(name)
        elif len(matches) > 1:
            ambiguous.append({
                "name": name,
                "surname": surname,
                "initial": initial.upper(),
                "reasoning": (
                    f"exact surname {surname!r} and given-name initial {initial.upper()!r} "
                    f"match {len(matches)} register rows; no automatic candidate emitted"
                ),
                "matches": matches,
            })
            resolved_names.add(name)
    remaining = [name for name in unmatched_names if name not in resolved_names]
    return candidates, ambiguous, remaining


def build_audit() -> dict[str, Any]:
    observations, deliveries, identity, participation, auction = _load_observations()
    observed_names = sorted(observations)
    reference_names = _reference_names(identity, participation)
    identity_names = set(identity["name"].dropna().astype(str).unique()) | set(identity["unique_name"].dropna().astype(str).unique())
    participation_names = set(participation["player_name"].dropna().astype(str).unique())
    unmatched_names = sorted(set(observed_names) - reference_names)
    punctuation_candidates = _candidate_pairs(observed_names, participation)
    normalized_candidates, unmatched_for_initials = _normalized_register_candidates(unmatched_names, identity)
    existing_candidate_pairs = {tuple(candidate["names"]) for candidate in punctuation_candidates}
    punctuation_candidates.extend(
        candidate for candidate in normalized_candidates
        if tuple(candidate["names"]) not in existing_candidate_pairs
    )
    candidate_names = {name for candidate in punctuation_candidates for name in candidate["names"]}
    initials_candidates, ambiguous_initials, remaining_unmatched = _initials_candidates(unmatched_for_initials, identity)
    candidates = punctuation_candidates + initials_candidates
    genuinely_unmatched = remaining_unmatched
    register_lookup = _register_lookup(identity)
    exact_matches_raw = [
        {
            "name": name,
            "sources": sorted(observations[name]["sources"]),
            "reference_sources": sorted(
                source for source, values in (
                    ("identity", identity_names),
                    ("participation", participation_names),
                ) if name in values
            ),
        }
        for name in observed_names if name in reference_names
    ]
    exact_matches: list[dict[str, Any]] = []
    ambiguous_exact: list[dict[str, Any]] = []
    no_register_entry: list[dict[str, Any]] = []
    for item in exact_matches_raw:
        rows = _unique_register_rows(register_lookup.get(item["name"], []))
        if len(rows) == 1:
            item["register_rows"] = rows
            exact_matches.append(item)
        elif len(rows) > 1:
            ambiguous_exact.append({
                "detection_rule": "exact_string_match",
                "name": item["name"],
                "reasoning": "exact source spelling resolves to multiple register identifiers",
                "matches": rows,
            })
        else:
            no_register_entry.append({
                "name": item["name"],
                "sources": item["sources"],
                "reasoning": "name exists in participation metadata but has no register row or identifier join key",
            })
    confident_candidates: list[dict[str, Any]] = []
    ambiguous_normalized: list[dict[str, Any]] = []
    ambiguous_initials_collision: list[dict[str, Any]] = []
    for candidate in candidates:
        rows = _resolved_rows_for_candidate(candidate, register_lookup)
        if len(rows) == 1:
            candidate["evidence"]["register_rows"] = rows
            confident_candidates.append(candidate)
            continue
        if not rows:
            no_register_entry.append({
                "name": candidate["names"][0],
                "source_names": candidate["names"],
                "detection_rule": "normalized_match" if candidate["confidence"] == "high_candidate" else "initials_pattern_match",
                "reasoning": "candidate has no matching register row or identifier join key",
                "sources": sorted(observations.get(candidate["names"][0], {}).get("sources", [])),
            })
            continue
        detection_rule = "initials_pattern_match" if candidate["confidence"] == "initials_pattern" else "normalized_match"
        target = ambiguous_initials_collision if detection_rule == "initials_pattern_match" else ambiguous_normalized
        target.append({
            "detection_rule": detection_rule,
            "name": candidate["names"][0],
            "names": candidate["names"],
            "reasoning": "candidate match resolves to multiple register identifiers",
            "matches": rows,
        })
    initials_candidates = [candidate for candidate in confident_candidates if candidate["confidence"] == "initials_pattern"]
    punctuation_candidates = [candidate for candidate in confident_candidates if candidate["confidence"] == "high_candidate"]
    no_register_names = {item["name"] for item in no_register_entry}
    initials_from_no_register, ambiguous_from_no_register, remaining_no_register = _initials_candidates(
        sorted(no_register_names), identity
    )
    for candidate in initials_from_no_register:
        rows = _resolved_rows_for_candidate(candidate, register_lookup)
        if len(rows) == 1:
            candidate["evidence"]["register_rows"] = rows
            initials_candidates.append(candidate)
        elif len(rows) > 1:
            ambiguous_initials_collision.append({
                "detection_rule": "initials_pattern_match",
                "name": candidate["names"][0],
                "names": candidate["names"],
                "reasoning": "no-register candidate resolves to multiple register identifiers",
                "matches": rows,
            })
    no_register_entry = [
        item for item in no_register_entry if item["name"] in set(remaining_no_register)
    ]
    candidates = punctuation_candidates + initials_candidates
    exact_name_bucket = {item["name"] for item in exact_matches}
    ambiguous_exact_bucket = {item["name"] for item in ambiguous_exact}
    normalized_bucket = {
        item["names"][0] for item in punctuation_candidates
        if item["names"][0] not in exact_name_bucket
    }
    ambiguous_normalized_bucket = {item["name"] for item in ambiguous_normalized}
    initials_bucket = {
        item["names"][0] for item in initials_candidates
        if item["names"][0] not in exact_name_bucket
    }
    ambiguous_initials_bucket = {
        item["name"] for item in ambiguous_initials
    } | {
        item["name"] for item in ambiguous_initials_collision
    }
    no_register_bucket = {item["name"] for item in no_register_entry}
    genuinely_unmatched_bucket = set(genuinely_unmatched)
    reconciliation_buckets = {
        "confident_exact": sorted(exact_name_bucket),
        "ambiguous_exact": sorted(ambiguous_exact_bucket),
        "confident_normalized": sorted(normalized_bucket),
        "ambiguous_normalized": sorted(ambiguous_normalized_bucket),
        "confident_initials": sorted(initials_bucket),
        "ambiguous_initials": sorted(ambiguous_initials_bucket),
        "no_register_entry": sorted(no_register_bucket),
        "genuinely_unmatched_after_initials": sorted(genuinely_unmatched_bucket),
    }
    name_membership: dict[str, list[str]] = {}
    for bucket, names in reconciliation_buckets.items():
        for name in names:
            name_membership.setdefault(name, []).append(bucket)
    observed_name_set = set(observed_names)
    reconciliation = {
        "observed_name_count": len(observed_name_set),
        "assigned_name_count": sum(len(names) for names in reconciliation_buckets.values()),
        "bucket_counts": {bucket: len(names) for bucket, names in reconciliation_buckets.items()},
        "names_in_zero_buckets": sorted(observed_name_set - set(name_membership)),
        "names_in_multiple_buckets": sorted(
            {name: buckets for name, buckets in name_membership.items() if len(buckets) > 1}.items()
        ),
        "buckets": reconciliation_buckets,
    }
    unmatched = [
        {
            "name": name,
            "sources": sorted(observations[name]["sources"]),
            "reason": "not present exactly in player_identity.csv name/unique_name or player_participation.csv player_name",
            "candidate_variant": name in candidate_names,
        }
        for name in unmatched_names
    ]
    source_counts = {
        source: sum(1 for record in observations.values() if source in record["sources"])
        for source in ("deliveries", "auction")
    }
    return {
        "inputs": {
            "deliveries": str(DELIVERIES_PATH.relative_to(PROJECT_ROOT)),
            "identity": str(IDENTITY_PATH.relative_to(PROJECT_ROOT)),
            "participation": str(PARTICIPATION_PATH.relative_to(PROJECT_ROOT)),
            "auction": str(AUCTION_PATH.relative_to(PROJECT_ROOT)),
            "register": str((PROJECT_ROOT / "data/raw/people.csv").relative_to(PROJECT_ROOT)),
        },
        "counts": {
            "unique_delivery_names": source_counts["deliveries"],
            "unique_auction_names": source_counts["auction"],
            "unique_observed_names": len(observed_names),
            "exact_matches": len(exact_matches),
            "unmatched_before_initials_pass": len(unmatched),
            "candidate_variant_pairs": len(candidates),
            "initials_pattern_candidates": len(initials_candidates),
            "ambiguous_initials": len(ambiguous_initials),
            "ambiguous_exact": len(ambiguous_exact),
            "ambiguous_normalized": len(ambiguous_normalized),
            "ambiguous_initials_collision": len(ambiguous_initials_collision),
            "no_register_entry": len(no_register_entry),
            "confident_exact_matches": len(exact_matches),
            "confident_normalized_matches": len(punctuation_candidates),
            "confident_initials_matches": len(initials_candidates),
            "genuinely_unmatched_after_initials": len(genuinely_unmatched),
            "delivery_rows": len(deliveries),
            "auction_rows": len(auction),
            "identity_rows": len(identity),
            "participation_rows": len(participation),
        },
        "exact_matches": exact_matches,
        "candidate_variants": candidates,
        "initials_pattern_candidates": initials_candidates,
        "ambiguous_initials": ambiguous_initials,
        "ambiguous_exact": ambiguous_exact,
        "ambiguous_normalized": ambiguous_normalized,
        "ambiguous_initials_collision": ambiguous_initials_collision,
        "no_register_entry": no_register_entry,
        "reconciliation": reconciliation,
        "unmatched": unmatched,
        "genuinely_unmatched_after_initials": genuinely_unmatched,
        "method": {
            "candidate_only": True,
            "canonical_ids_assigned": False,
            "biographical_fields_inferred": False,
            "fielder_source": "nested wickets_json fielders",
            "matching_rules": [
                "exact membership in identity name/unique_name or participation player_name",
                "same compact alphanumeric spelling after punctuation/spacing removal",
                "conservative edit similarity with matching initials or shared participation team-season context",
            ],
        },
    }


def _markdown(report: dict[str, Any]) -> str:
    counts = report["counts"]
    lines = [
        "# Player Identity Audit",
        "",
        "Phase 2.3 Step 1 only: inventory and ambiguity surfacing. No canonical IDs are assigned and no names are auto-merged.",
        "",
        "## Counts",
        "",
        f"- Unique delivery player names, including nested wicket fielders: **{counts['unique_delivery_names']}**",
        f"- Unique auction player names: **{counts['unique_auction_names']}**",
        f"- Unique observed names across delivery and auction sources: **{counts['unique_observed_names']}**",
        f"- Exact reference matches: **{counts['exact_matches']}**",
        f"- Names unmatched before initials pass: **{counts['unmatched_before_initials_pass']}**",
        f"- Candidate variant pairs: **{counts['candidate_variant_pairs']}**",
        f"- Confident normalized matches: **{counts['confident_normalized_matches']}**",
        f"- Initials-pattern candidates: **{counts['initials_pattern_candidates']}**",
        f"- Ambiguous initials matches: **{counts['ambiguous_initials']}**",
        f"- Genuinely unmatched after all candidate passes: **{counts['genuinely_unmatched_after_initials']}**",
        "",
        "## Candidate Variant Pairs",
        "",
        "These are review candidates only. They do not establish that two names refer to the same person.",
        "",
        "| Names | Confidence label | Reasoning |",
        "| --- | --- | --- |",
    ]
    for candidate in report["candidate_variants"]:
        names = " / ".join(candidate["names"])
        reasoning = candidate["reasoning"].replace("|", "\\|")
        lines.append(f"| {names} | {candidate['confidence']} | {reasoning} |")
    lines.extend(["", "## Ambiguous Initials", ""])
    lines.append("These names have multiple register rows with the same surname and given-name initial. No candidate identity is emitted.")
    lines.extend(
        f"- `{item['name']}`: " + ", ".join(
            f"{row['name'] or row['unique_name']} ({row['identifier']})" for row in item["matches"]
        )
        for item in report["ambiguous_initials"]
    )
    lines.extend(["", "## Fully Unmatched Names", ""])
    lines.extend(f"- `{name}`" for name in report["genuinely_unmatched_after_initials"])
    lines.extend([
        "",
        "## Interpretation",
        "",
        "- Exact matches mean only that the spelling exists in the current identity or participation references.",
        "- Candidate variants use punctuation/spacing normalization or conservative edit similarity plus available participation context.",
        "- Unmatched names require human review or a separately evidenced mapping in Step 2.",
        "- No role, nationality, age, or other biographical field was inferred.",
    ])
    return "\n".join(lines) + "\n"


def write_reports(report_dir: str | Path = REPORT_DIR) -> dict[str, Path]:
    report = build_audit()
    destination = Path(report_dir)
    destination.mkdir(parents=True, exist_ok=True)
    markdown_path = destination / "player_identity_audit.md"
    json_path = destination / "player_identity_ambiguity.json"
    collision_path = destination / "player_identity_collision_review.txt"
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    collision_lines = [
        "AMBIGUOUS_EXACT",
        *[
            f"{item['name']} | detection_rule={item['detection_rule']} | reasoning={item['reasoning']} | matches={json.dumps(item['matches'], ensure_ascii=False, sort_keys=True)}"
            for item in report["ambiguous_exact"]
        ],
        "AMBIGUOUS_NORMALIZED",
        *[
            f"{item['name']} | detection_rule={item['detection_rule']} | reasoning={item['reasoning']} | matches={json.dumps(item['matches'], ensure_ascii=False, sort_keys=True)}"
            for item in report["ambiguous_normalized"]
        ],
        "AMBIGUOUS_INITIALS_COLLISION",
        *[
            f"{item['name']} | detection_rule={item['detection_rule']} | reasoning={item['reasoning']} | matches={json.dumps(item['matches'], ensure_ascii=False, sort_keys=True)}"
            for item in report["ambiguous_initials_collision"]
        ],
        "NO_REGISTER_ENTRY",
        *[
            f"{item['name']} | reasoning={item['reasoning']} | sources={item['sources']}"
            for item in report["no_register_entry"]
        ],
    ]
    collision_path.write_text("\n".join(collision_lines) + "\n", encoding="utf-8")
    reconciliation_lines = [
        f"observed_name_count={report['reconciliation']['observed_name_count']}",
        f"assigned_name_count={report['reconciliation']['assigned_name_count']}",
        f"names_in_zero_buckets={json.dumps(report['reconciliation']['names_in_zero_buckets'], ensure_ascii=False)}",
        f"names_in_multiple_buckets={json.dumps(report['reconciliation']['names_in_multiple_buckets'], ensure_ascii=False)}",
        "bucket_counts=" + json.dumps(report["reconciliation"]["bucket_counts"], sort_keys=True),
    ]
    reconciliation_path = destination / "player_identity_reconciliation.txt"
    reconciliation_path.write_text("\n".join(reconciliation_lines) + "\n", encoding="utf-8")
    handoff_path = destination / "STEP1_HANDOFF.md"
    handoff_path.write_text(
        "\n".join([
            "# Phase 2.3 Step 1 Handoff",
            "",
            "This handoff covers identity inventory and candidate evidence only. It assigns no canonical IDs and does not create the Step 2 mapping file.",
            "",
            "## Report Files",
            "",
            "- `player_identity_ambiguity.json`: structured audit output.",
            "- `player_identity_audit.md`: human-readable count and candidate summary.",
            "- `player_identity_collision_review.txt`: full exact-collision and no-register review lines.",
            "- `player_identity_reconciliation.txt`: direct proof that observed names are partitioned into exactly one bucket.",
            "",
            "## JSON Schema",
            "",
            "- `inputs`: repository-relative source paths.",
            "- `counts`: row/name totals and tier counts. `unmatched_before_initials_pass` is the pre-partition total; `genuinely_unmatched_after_initials` is the final list count.",
            "- `exact_matches`: confident exact names, each with `name`, source list, reference sources, and one `register_rows` entry.",
            "- `candidate_variants`: confident punctuation/spacing/case-normalized and initials candidates. Each has `names`, `confidence`, `reasoning`, and register evidence.",
            "- `initials_pattern_candidates`: the confident initials subset, with one register row in `evidence.register_rows`.",
            "- `ambiguous_initials`: surname/initial candidates with multiple register rows.",
            "- `ambiguous_exact`: exact source names with multiple register identifiers.",
            "- `ambiguous_normalized`: normalized candidates with multiple register identifiers.",
            "- `ambiguous_initials_collision`: initials candidates with multiple register identifiers.",
            "- `no_register_entry`: names with no register row or alternate identifier join; includes detection rule where applicable.",
            "- `genuinely_unmatched_after_initials`: names remaining after candidate detection.",
            "- `reconciliation`: mutually exclusive name buckets, assigned/observed totals, and zero/multiple-bucket lists.",
            "",
            "## Current Tier Counts",
            "",
            json.dumps(report["counts"], indent=2, sort_keys=True),
            "",
            "## Caveats",
            "",
            "- `player_participation.csv` has no identifier column or alternate join key.",
            "- Initials matching uses exact surname plus first given-name initial; it is candidate evidence only.",
            "- Hyphenated and multi-token surname conventions are not fully normalized.",
            "- Ambiguous register identifiers are never auto-selected.",
            "- No roles, nationality, age, or other biographical fields are inferred.",
            "",
            "## Step 2 Consumption",
            "",
            "Step 2 must consume only confident tiers with exactly one `register_rows` identifier: `exact_matches`, confident entries in `candidate_variants`, and `initials_pattern_candidates`. It must keep all ambiguous buckets and `no_register_entry` visible and unresolved, then write explicit mapping evidence without inventing IDs.",
            "",
        ]) + "\n",
        encoding="utf-8",
    )
    return {
        "markdown": markdown_path,
        "json": json_path,
        "collision": collision_path,
        "reconciliation": reconciliation_path,
        "handoff": handoff_path,
        "report": report,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", default=str(REPORT_DIR))
    args = parser.parse_args()
    result = write_reports(args.report_dir)
    print(json.dumps(result["report"]["counts"], sort_keys=True))


if __name__ == "__main__":
    main()