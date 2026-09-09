"""Ingestion subpackage for raw data acquisition and provenance tracking."""

from src.ingestion.manifest import (
    compute_bytes_sha256,
    compute_sha256,
    get_manifest_path,
    load_manifest,
    save_manifest,
    verify_file_provenance,
)
from src.ingestion.fetcher import (
    derive_deterministic_filename,
    download_source,
    get_source_by_name,
    load_source_register,
)

__all__ = [
    "compute_sha256",
    "compute_bytes_sha256",
    "get_manifest_path",
    "load_manifest",
    "save_manifest",
    "verify_file_provenance",
    "derive_deterministic_filename",
    "download_source",
    "get_source_by_name",
    "load_source_register",
]
