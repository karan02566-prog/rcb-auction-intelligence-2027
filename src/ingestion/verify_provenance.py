"""Phase 1.5 - Provenance & Source Manifest Verification.

Cross-checks data/raw/manifest.json (per-file fetch provenance, written by
src.ingestion.manifest at fetch time) against configs/source_manifest.json
(the formal source catalog) and the actual files on disk under data/raw/.

Produces reports/data_provenance_manifest.json: an auditable snapshot of
what is verified, what is missing, and what raw files exist on disk that
are not tracked in the provenance manifest ("untracked raw files").
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.ingestion.manifest import (
    load_manifest,
    load_source_catalog,
    record_manifest_entry,
    verify_file_provenance,
)
from src.utils.config import get_project_root
from src.utils.exceptions import ProvenanceError


def find_untracked_raw_files(
    raw_dir: Optional[Path] = None,
    manifest_entries: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """
    List files under data/raw/ that are not referenced by any manifest
    entry's local_path.

    Args:
        raw_dir: Optional raw data directory (defaults to data/raw/).
        manifest_entries: Optional pre-loaded manifest 'entries' dict.

    Returns:
        Sorted list of project-root-relative paths for untracked files.
        manifest.json itself is excluded (it is the ledger, not tracked data).
    """
    if raw_dir is None:
        project_root = get_project_root()
        raw_dir = project_root / "data" / "raw"
    else:
        raw_dir = Path(raw_dir)
        project_root = raw_dir.parent.parent

    if manifest_entries is None:
        manifest_entries = load_manifest().get("entries", {})

    tracked_paths = set()
    for entry in manifest_entries.values():
        local_path = entry.get("local_path")
        if local_path:
            tracked_paths.add(str(Path(local_path)))

    untracked = []
    if raw_dir.exists():
        for path in raw_dir.rglob("*"):
            if path.is_file() and path.name != "manifest.json":
                rel = str(path.relative_to(project_root))
                if rel not in tracked_paths:
                    untracked.append(rel)

    return sorted(untracked)


def verify_all_sources() -> Dict[str, Any]:
    """
    Verify SHA-256 provenance for every entry recorded in data/raw/manifest.json,
    and cross-reference each against configs/source_manifest.json.

    Returns:
        Dict with keys: verified (list), failed (list of {source, error}),
        catalog_cross_reference (list of {source, in_catalog: bool}).
    """
    manifest = load_manifest()
    entries = manifest.get("entries", {})

    try:
        catalog = load_source_catalog()
        catalog_names = {s["source_name"] for s in catalog["sources"]}
    except ProvenanceError:
        catalog_names = set()

    verified: List[str] = []
    failed: List[Dict[str, str]] = []
    cross_reference: List[Dict[str, Any]] = []

    for source_name in entries:
        try:
            verify_file_provenance(source_name)
            verified.append(source_name)
        except ProvenanceError as exc:
            failed.append({"source": source_name, "error": str(exc)})

        cross_reference.append(
            {"source": source_name, "in_source_catalog": source_name in catalog_names}
        )

    return {
        "verified": verified,
        "failed": failed,
        "catalog_cross_reference": cross_reference,
    }


def generate_provenance_report(output_path: Optional[Path] = None) -> Path:
    """
    Run full provenance verification and write reports/data_provenance_manifest.json.

    Args:
        output_path: Optional destination (defaults to reports/data_provenance_manifest.json).

    Returns:
        Path the report was written to.
    """
    if output_path is None:
        output_path = get_project_root() / "reports" / "data_provenance_manifest.json"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    verification = verify_all_sources()
    untracked = find_untracked_raw_files()

    report = {
        "report_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sha256_verification": {
            "verified_count": len(verification["verified"]),
            "failed_count": len(verification["failed"]),
            "verified_sources": verification["verified"],
            "failed_sources": verification["failed"],
        },
        "source_catalog_cross_reference": verification["catalog_cross_reference"],
        "untracked_raw_files": {
            "count": len(untracked),
            "files": untracked,
        },
        "status": "PASS" if not verification["failed"] and not untracked else "ATTENTION_REQUIRED",
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return output_path


def register_untracked_raw_files(raw_dir: Optional[Path] = None) -> int:
    """
    Backfill manifest entries for files under data/raw/ that predate per-file
    provenance tracking (e.g. individual match JSONs extracted from a Cricsheet
    zip, where only the parent archive download was originally recorded).

    Computes a real SHA-256 for each untracked file and records it under a
    source_name derived from its path. Idempotent: already-tracked files are
    left untouched and not re-hashed.

    Args:
        raw_dir: Optional raw data directory (defaults to data/raw/).

    Returns:
        Number of newly registered files.
    """
    from src.ingestion.manifest import compute_sha256, save_manifest

    project_root = get_project_root()
    manifest = load_manifest()
    untracked = find_untracked_raw_files(raw_dir=raw_dir, manifest_entries=manifest.get("entries", {}))

    for rel_path in untracked:
        full_path = project_root / rel_path
        entry = {
            "source_name": rel_path,
            "local_path": rel_path,
            "sha256": compute_sha256(full_path),
        }
        manifest = record_manifest_entry(manifest, entry)

    if untracked:
        save_manifest(manifest)

    return len(untracked)


def prune_missing_manifest_entries() -> List[str]:
    """
    Remove manifest entries whose local_path no longer exists on disk
    (e.g. after deleting a stray/duplicate raw data folder).

    Returns:
        List of source_name keys that were removed.
    """
    from src.ingestion.manifest import save_manifest

    project_root = get_project_root()
    manifest = load_manifest()
    entries = manifest.get("entries", {})

    removed = []
    for source_name, entry in list(entries.items()):
        local_path = entry.get("local_path")
        if local_path and not (project_root / local_path).exists():
            del entries[source_name]
            removed.append(source_name)

    if removed:
        manifest["entries"] = entries
        save_manifest(manifest)

    return removed


if __name__ == "__main__":
    import sys

    if "--prune-missing" in sys.argv:
        removed = prune_missing_manifest_entries()
        print(f"Pruned {len(removed)} manifest entr(y/ies) for files no longer on disk")

    if "--register-untracked" in sys.argv:
        n = register_untracked_raw_files()
        print(f"Registered {n} previously untracked file(s) into data/raw/manifest.json")

    path = generate_provenance_report()
    with open(path, "r", encoding="utf-8") as f:
        report = json.load(f)
    print(f"Provenance report written to {path}")
    print(f"Status: {report['status']}")
    print(
        f"Verified: {report['sha256_verification']['verified_count']}, "
        f"Failed: {report['sha256_verification']['failed_count']}, "
        f"Untracked raw files: {report['untracked_raw_files']['count']}"
    )