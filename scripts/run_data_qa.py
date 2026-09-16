"""
Phase 2.7 executable QA pipeline.
Run after scripts/build_processed_layer.py (fact_deliveries must already be
joined to dim_competitions/dim_venues, or the FK checks validate nothing).

Usage: python3 scripts/run_data_qa.py
Exit code: 0 if all checks pass, 1 if any check fails.
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.validation.quality_checks import run_all_checks


def main():
    processed_dir = Path("data/processed")
    interim_dir = Path("data/interim")
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    fact_path = processed_dir / "fact_deliveries.parquet"
    matches_path = interim_dir / "matches.parquet"

    fact = pd.read_parquet(fact_path)
    matches = pd.read_parquet(matches_path)

    if "competition_id" not in fact.columns or "venue_id" not in fact.columns:
        raise RuntimeError(
            "fact_deliveries.parquet has no competition_id/venue_id columns -- "
            "run scripts/build_processed_layer.py first, or these FK checks "
            "validate nothing."
        )

    results = run_all_checks(fact, matches)

    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_fail = len(results) - n_pass

    report = {
        "row_count": int(len(fact)),
        "checks_run": len(results),
        "checks_passed": n_pass,
        "checks_failed": n_fail,
        "overall_status": "PASS" if n_fail == 0 else "FAIL",
        "results": results,
    }

    out_path = reports_dir / "data_quality_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Data quality report: {n_pass}/{len(results)} checks passed")
    for r in results:
        marker = "OK " if r["status"] == "PASS" else "FAIL"
        print(f"  [{marker}] {r['check']}: {r['detail']}")
    print(f"\nSaved: {out_path}")

    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
