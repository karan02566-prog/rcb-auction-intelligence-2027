"""Provenance manifest management and integrity verification utilities."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union

from src.utils.config import get_project_root
from src.utils.exceptions import ProvenanceError


def compute_sha256(file_path: Union[str, Path], chunk_size: int = 65536) -> str:
    """
    Calculate the SHA-256 hex digest of a file.

    Args:
        file_path: Path to the target file.
        chunk_size: Read buffer chunk size in bytes.

    Returns:
        Hexadecimal SHA-256 hash string.

    Raises:
        ProvenanceError: If the file does not exist or cannot be read.
    """
    path = Path(file_path)
    if not path.exists():
        raise ProvenanceError(f"File not found for hash calculation: '{path}'")
    if not path.is_file():
        raise ProvenanceError(f"Path is not a file: '{path}'")

    hasher = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
    except Exception as exc:
        raise ProvenanceError(f"Failed to calculate SHA-256 for '{path}': {exc}") from exc

    return hasher.hexdigest()


def compute_bytes_sha256(data: bytes) -> str:
    """
    Calculate the SHA-256 hex digest of a byte sequence.

    Args:
        data: Raw byte payload.

    Returns:
        Hexadecimal SHA-256 hash string.
    """
    return hashlib.sha256(data).hexdigest()


def get_manifest_path(raw_dir: Optional[Path] = None) -> Path:
    """
    Get the standard path to the raw data provenance manifest.

    Args:
        raw_dir: Optional custom raw data directory (defaults to data/raw/).

    Returns:
        Path to data/raw/manifest.json.
    """
    if raw_dir is None:
        raw_dir = get_project_root() / "data" / "raw"
    return Path(raw_dir) / "manifest.json"


def load_manifest(manifest_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load the provenance manifest from JSON.

    Args:
        manifest_path: Optional path to manifest file (defaults to data/raw/manifest.json).

    Returns:
        Dictionary representing manifest content. Returns a new empty manifest structure
        if the file does not exist.

    Raises:
        ProvenanceError: If the manifest file is corrupted or unparseable.
    """
    if manifest_path is None:
        manifest_path = get_manifest_path()

    path = Path(manifest_path)
    if not path.exists():
        return {
            "manifest_version": "1.0",
            "updated_at": None,
            "entries": {},
        }

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ProvenanceError(f"Manifest file '{path}' is invalid JSON: {exc}") from exc
    except Exception as exc:
        raise ProvenanceError(f"Error loading manifest '{path}': {exc}") from exc

    if not isinstance(data, dict) or "entries" not in data:
        raise ProvenanceError(f"Manifest file '{path}' is malformed; missing 'entries' object.")

    return data


def save_manifest(manifest_data: Dict[str, Any], manifest_path: Optional[Path] = None) -> Path:
    """
    Save the provenance manifest dictionary to JSON atomically.

    Args:
        manifest_data: Manifest dictionary to serialize.
        manifest_path: Optional destination path (defaults to data/raw/manifest.json).

    Returns:
        Path where manifest was saved.

    Raises:
        ProvenanceError: If writing to the file fails.
    """
    if manifest_path is None:
        manifest_path = get_manifest_path()

    path = Path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    manifest_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        raise ProvenanceError(f"Failed to write provenance manifest to '{path}': {exc}") from exc

    return path


def record_manifest_entry(manifest_data: Dict[str, Any], entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add or update a data source record in the manifest dictionary.

    Args:
        manifest_data: Existing manifest structure.
        entry: Data source provenance dict. Must contain 'source_name'.

    Returns:
        Updated manifest dictionary.

    Raises:
        ProvenanceError: If 'source_name' is missing from entry.
    """
    source_name = entry.get("source_name")
    if not source_name:
        raise ProvenanceError("Manifest entry must contain a non-empty 'source_name'.")

    if "entries" not in manifest_data:
        manifest_data["entries"] = {}

    manifest_data["entries"][source_name] = entry
    manifest_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    return manifest_data


def verify_file_provenance(
    source_name: str,
    manifest_path: Optional[Path] = None,
    project_root: Optional[Path] = None,
) -> bool:
    """
    Verify that a recorded file exists and matches its recorded SHA-256 checksum.

    Args:
        source_name: Target source name in manifest.
        manifest_path: Optional path to manifest file.
        project_root: Optional project root directory for path resolution.

    Returns:
        True if file exists and SHA-256 matches manifest.

    Raises:
        ProvenanceError: If source is unrecorded, file is missing, or SHA-256 mismatches.
    """
    if project_root is None:
        project_root = get_project_root()

    manifest = load_manifest(manifest_path)
    entries = manifest.get("entries", {})

    if source_name not in entries:
        raise ProvenanceError(f"Source '{source_name}' is not recorded in provenance manifest.")

    entry = entries[source_name]
    relative_local_path = entry.get("local_path")
    expected_sha256 = entry.get("sha256")

    if not relative_local_path or not expected_sha256:
        raise ProvenanceError(f"Manifest entry for '{source_name}' is missing local_path or sha256.")

    full_path = project_root / relative_local_path
    if not full_path.exists():
        raise ProvenanceError(f"Raw file for '{source_name}' missing on disk at '{full_path}'.")

    actual_sha256 = compute_sha256(full_path)
    if actual_sha256.lower() != expected_sha256.lower():
        raise ProvenanceError(
            f"Integrity check failed for '{source_name}': expected SHA-256 {expected_sha256}, "
            f"got {actual_sha256}."
        )

    return True


# ---------------------------------------------------------------------------
# Source catalog (configs/source_manifest.json) — Phase 1.1
#
# Distinct from the provenance functions above: those track per-file fetch
# hashes/timestamps at data/raw/manifest.json; this section validates the
# formal, project-level catalog of *where sources come from* (competitions,
# URLs, license, scope, known limitations).
# ---------------------------------------------------------------------------

REQUIRED_SOURCE_FIELDS = (
    "source_name",
    "competition",
    "provider",
    "url",
    "format",
    "scope",
    "license",
    "authority_level",
    "status",
    "known_limitations",
)

VALID_SOURCE_STATUSES = ("active", "planned", "deprecated")


def get_source_catalog_path(config_dir: Optional[Path] = None) -> Path:
    """
    Get the standard path to the source catalog file.

    Args:
        config_dir: Optional custom configs directory (defaults to configs/).

    Returns:
        Path to configs/source_manifest.json.
    """
    if config_dir is None:
        config_dir = get_project_root() / "configs"
    return Path(config_dir) / "source_manifest.json"


def load_source_catalog(catalog_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load the source catalog from JSON.

    Args:
        catalog_path: Optional path to catalog file (defaults to configs/source_manifest.json).

    Returns:
        Dictionary representing the source catalog.

    Raises:
        ProvenanceError: If the file is missing or invalid JSON.
    """
    if catalog_path is None:
        catalog_path = get_source_catalog_path()

    path = Path(catalog_path)
    if not path.exists():
        raise ProvenanceError(f"Source catalog not found: '{path}'.")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ProvenanceError(f"Source catalog '{path}' is invalid JSON: {exc}") from exc

    if not isinstance(data, dict) or "sources" not in data:
        raise ProvenanceError(f"Source catalog '{path}' is malformed; missing 'sources' list.")

    return data


def validate_source_catalog(catalog: Dict[str, Any]) -> bool:
    """
    Validate a source catalog dictionary against the Phase 1.1 schema.

    Checks: required fields present on every source, non-empty unique
    source_name values, valid status values, URLs present for non-planned
    sources, and full coverage of the catalog's declared required_competitions.

    Args:
        catalog: Loaded source catalog dictionary (see load_source_catalog).

    Returns:
        True if the catalog passes all checks.

    Raises:
        ProvenanceError: On the first validation failure, describing the issue.
    """
    sources = catalog.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ProvenanceError("Source catalog must contain a non-empty 'sources' list.")

    seen_names = set()
    covered_competitions = set()

    for entry in sources:
        missing = [f for f in REQUIRED_SOURCE_FIELDS if f not in entry]
        if missing:
            raise ProvenanceError(
                f"Source entry '{entry.get('source_name', '<unnamed>')}' missing required "
                f"field(s): {missing}."
            )

        name = entry["source_name"]
        if not name or not isinstance(name, str):
            raise ProvenanceError("Source entry has empty or invalid 'source_name'.")
        if name in seen_names:
            raise ProvenanceError(f"Duplicate source_name in catalog: '{name}'.")
        seen_names.add(name)

        status = entry["status"]
        if status not in VALID_SOURCE_STATUSES:
            raise ProvenanceError(
                f"Source '{name}' has invalid status '{status}'; expected one of {VALID_SOURCE_STATUSES}."
            )

        if status == "active" and not entry.get("url"):
            raise ProvenanceError(f"Active source '{name}' is missing a 'url'.")

        covered_competitions.add(entry["competition"])

    required_competitions = catalog.get("required_competitions", [])
    for competition in required_competitions:
        if not any(competition in c for c in covered_competitions):
            raise ProvenanceError(
                f"Required competition '{competition}' is not covered by any catalog source."
            )

    return True