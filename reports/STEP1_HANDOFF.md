# Phase 2.3 Step 1 Handoff

This handoff covers identity inventory and candidate evidence only. It assigns no canonical IDs and does not create the Step 2 mapping file.

## Report Files

- `player_identity_ambiguity.json`: structured audit output.
- `player_identity_audit.md`: human-readable count and candidate summary.
- `player_identity_collision_review.txt`: full exact-collision and no-register review lines.
- `player_identity_reconciliation.txt`: direct proof that observed names are partitioned into exactly one bucket.

## JSON Schema

- `inputs`: repository-relative source paths.
- `counts`: row/name totals and tier counts. `unmatched_before_initials_pass` is the pre-partition total; `genuinely_unmatched_after_initials` is the final list count.
- `exact_matches`: confident exact names, each with `name`, source list, reference sources, and one `register_rows` entry.
- `candidate_variants`: confident punctuation/spacing/case-normalized and initials candidates. Each has `names`, `confidence`, `reasoning`, and register evidence.
- `initials_pattern_candidates`: the confident initials subset, with one register row in `evidence.register_rows`.
- `ambiguous_initials`: surname/initial candidates with multiple register rows.
- `ambiguous_exact`: exact source names with multiple register identifiers.
- `ambiguous_normalized`: normalized candidates with multiple register identifiers.
- `ambiguous_initials_collision`: initials candidates with multiple register identifiers.
- `no_register_entry`: names with no register row or alternate identifier join; includes detection rule where applicable.
- `genuinely_unmatched_after_initials`: names remaining after candidate detection.
- `reconciliation`: mutually exclusive name buckets, assigned/observed totals, and zero/multiple-bucket lists.

## Current Tier Counts

{
  "ambiguous_exact": 80,
  "ambiguous_initials": 132,
  "ambiguous_initials_collision": 0,
  "ambiguous_normalized": 0,
  "auction_rows": 1381,
  "candidate_variant_pairs": 397,
  "confident_exact_matches": 2923,
  "confident_initials_matches": 357,
  "confident_normalized_matches": 40,
  "delivery_rows": 871141,
  "exact_matches": 2923,
  "genuinely_unmatched_after_initials": 84,
  "identity_rows": 18507,
  "initials_pattern_candidates": 357,
  "no_register_entry": 5,
  "participation_rows": 84502,
  "unique_auction_names": 734,
  "unique_delivery_names": 3003,
  "unique_observed_names": 3601,
  "unmatched_before_initials_pass": 594
}

## Caveats

- `player_participation.csv` has no identifier column or alternate join key.
- Initials matching uses exact surname plus first given-name initial; it is candidate evidence only.
- Hyphenated and multi-token surname conventions are not fully normalized.
- Ambiguous register identifiers are never auto-selected.
- No roles, nationality, age, or other biographical fields are inferred.

## Step 2 Consumption

Step 2 must consume only confident tiers with exactly one `register_rows` identifier: `exact_matches`, confident entries in `candidate_variants`, and `initials_pattern_candidates`. It must keep all ambiguous buckets and `no_register_entry` visible and unresolved, then write explicit mapping evidence without inventing IDs.

