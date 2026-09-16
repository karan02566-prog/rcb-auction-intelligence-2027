"""
Phase 2.7: Automated Data-Quality Checks & Contract Validation.

Scope status (v1.1): SCOPED DOWN -- targeted checks on the fields the models
actually use, not a full contract-validation suite. Runs against
data/processed/fact_deliveries.parquet (joined to dim_competitions/dim_venues
by scripts/build_processed_layer.py) plus the dimension tables themselves.

Each check function returns a dict: {"check": ..., "status": "PASS"/"FAIL",
"detail": ...}. Nothing here suppresses a failure -- run_data_qa.py surfaces
every result and exits non-zero if any check fails.
"""
import pandas as pd


def check_no_duplicate_deliveries(fact: pd.DataFrame) -> dict:
    dup_count = int(fact["delivery_key"].duplicated().sum())
    return {
        "check": "no_duplicate_deliveries",
        "status": "PASS" if dup_count == 0 else "FAIL",
        "detail": f"{dup_count} duplicate delivery_key values",
    }


def check_required_fields_not_null(fact: pd.DataFrame) -> dict:
    required = [
        "delivery_key", "match_id", "competition", "season",
        "batter_canonical_id", "bowler_canonical_id", "phase",
        "batter_runs", "total_runs",
    ]
    null_counts = {c: int(fact[c].isna().sum()) for c in required if c in fact.columns}
    missing_cols = [c for c in required if c not in fact.columns]
    bad = {c: n for c, n in null_counts.items() if n > 0}
    ok = not bad and not missing_cols
    detail = {}
    if bad:
        detail["null_counts"] = bad
    if missing_cols:
        detail["missing_columns"] = missing_cols
    return {
        "check": "required_fields_not_null",
        "status": "PASS" if ok else "FAIL",
        "detail": detail if detail else "all required fields fully populated",
    }


def check_competition_fk_integrity(fact: pd.DataFrame) -> dict:
    orphan = int(fact["competition_id"].isna().sum())
    return {
        "check": "competition_fk_integrity",
        "status": "PASS" if orphan == 0 else "FAIL",
        "detail": f"{orphan} rows with no matching competition_id (dim_competitions FK)",
    }


def check_venue_fk_integrity(fact: pd.DataFrame) -> dict:
    orphan = int(fact["venue_id"].isna().sum())
    return {
        "check": "venue_fk_integrity",
        "status": "PASS" if orphan == 0 else "FAIL",
        "detail": f"{orphan} rows with no matching venue_id (dim_venues FK)",
    }


def check_orphan_matches(fact: pd.DataFrame, matches: pd.DataFrame) -> dict:
    fact_match_ids = set(fact["match_id"].unique())
    known_match_ids = set(matches["match_id"].unique())
    orphans = fact_match_ids - known_match_ids
    return {
        "check": "no_orphan_matches",
        "status": "PASS" if not orphans else "FAIL",
        "detail": f"{len(orphans)} match_id(s) in fact_deliveries absent from matches.parquet",
    }


def check_run_sanity(fact: pd.DataFrame) -> dict:
    # batter_runs off the bat is 0-6 in cricket; total_runs (incl. extras) must be >= batter_runs.
    bad_batter_runs = int(((fact["batter_runs"] < 0) | (fact["batter_runs"] > 6)).sum())
    bad_total_runs = int((fact["total_runs"] < fact["batter_runs"]).sum())
    ok = bad_batter_runs == 0 and bad_total_runs == 0
    return {
        "check": "run_sanity",
        "status": "PASS" if ok else "FAIL",
        "detail": {
            "batter_runs_out_of_0_6_range": bad_batter_runs,
            "total_runs_less_than_batter_runs": bad_total_runs,
        },
    }


def check_wicket_sanity(fact: pd.DataFrame) -> dict:
    bad_domain = int(((fact["is_wicket"] != 0) & (fact["is_wicket"] != 1)).sum())
    # A wicket falls roughly every ~20-25 legal balls in T20 cricket (~4-5%).
    # Bound generously (1%-15%) to catch gross derivation bugs (e.g. every ball
    # flagged as a wicket) without false-failing on small/unusual samples.
    legal = fact["is_legal_delivery"] == 1
    wicket_rate = fact.loc[legal, "is_wicket"].mean() if legal.any() else 0.0
    plausible = 0.01 <= wicket_rate <= 0.15
    ok = bad_domain == 0 and plausible
    return {
        "check": "wicket_sanity",
        "status": "PASS" if ok else "FAIL",
        "detail": {
            "rows_outside_0_1_domain": bad_domain,
            "wicket_rate_on_legal_balls": round(float(wicket_rate), 4),
            "plausible_range": "0.01-0.15",
        },
    }


def check_phase_over_boundary(fact: pd.DataFrame) -> dict:
    """Sanity check the phase assignment at the 5.6 -> 6.0 boundary (Phase 4.4
    validation the coding agent's memory.md log did not confirm was ever run --
    see Known Open Gap #2)."""
    zero_indexed = fact["over_number"].min() == 0
    boundary_over = 5 if zero_indexed else 6
    boundary_rows = fact[fact["over_number"] == boundary_over]
    wrong_phase = int((boundary_rows["phase"] != "Powerplay").sum())
    return {
        "check": "phase_over_boundary_5_6_to_6_0",
        "status": "PASS" if wrong_phase == 0 else "FAIL",
        "detail": f"{wrong_phase} rows at over_number={boundary_over} "
                  f"(last powerplay over) not labeled Powerplay",
    }


def run_all_checks(fact: pd.DataFrame, matches: pd.DataFrame) -> list:
    return [
        check_no_duplicate_deliveries(fact),
        check_required_fields_not_null(fact),
        check_competition_fk_integrity(fact),
        check_venue_fk_integrity(fact),
        check_orphan_matches(fact, matches),
        check_run_sanity(fact),
        check_wicket_sanity(fact),
        check_phase_over_boundary(fact),
    ]
