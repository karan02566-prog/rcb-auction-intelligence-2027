"""Data acquisition mechanism for downloading and preserving raw project datasets."""

from datetime import datetime, timezone
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Union
import urllib.parse
import urllib.request

from src.ingestion.manifest import (
    compute_sha256,
    get_manifest_path,
    load_manifest,
    record_manifest_entry,
    save_manifest,
)
from src.utils.config import get_project_root, load_config
from src.utils.exceptions import DuplicateFileError, IngestionError


def load_source_register(
    config_path: Union[str, Path] = "configs/data_sources.yaml"
) -> Dict[str, Any]:
    """
    Load and validate the data source register.

    Args:
        config_path: Path to data_sources.yaml (relative to project root or absolute).

    Returns:
        Dictionary containing configuration including 'sources' list.

    Raises:
        IngestionError: If the source register is missing or malformed.
    """
    try:
        config = load_config(config_path)
    except Exception as exc:
        raise IngestionError(f"Failed to load data source register '{config_path}': {exc}") from exc

    if "sources" not in config or not isinstance(config["sources"], list):
        raise IngestionError(
            f"Source register '{config_path}' is missing a 'sources' list."
        )

    return config


def get_source_by_name(
    source_name: str, config_path: Union[str, Path] = "configs/data_sources.yaml"
) -> Dict[str, Any]:
    """
    Retrieve a specific source definition by name from the source register.

    Args:
        source_name: Name of the data source to find.
        config_path: Path to data_sources.yaml.

    Returns:
        Data source dictionary entry.

    Raises:
        IngestionError: If source_name is not found in the configuration.
    """
    register = load_source_register(config_path)
    for source in register["sources"]:
        if source.get("source_name") == source_name:
            return source

    raise IngestionError(
        f"Data source '{source_name}' is not configured in '{config_path}'. "
        "Only sources explicitly listed in configs/data_sources.yaml can be downloaded."
    )


def derive_deterministic_filename(source_entry: Dict[str, Any]) -> str:
    """
    Derive a deterministic local filename for a data source entry.

    Args:
        source_entry: Source entry dictionary from data_sources.yaml.

    Returns:
        Deterministic filename string (e.g. 'ipl_json.zip', 'people.csv').
    """
    if "filename" in source_entry and source_entry["filename"]:
        return os.path.basename(source_entry["filename"])

    url = source_entry.get("url", "")
    parsed_url = urllib.parse.urlparse(url)
    url_path = parsed_url.path.strip()

    path_filename = os.path.basename(url_path)

    # Check if basename has an explicit extension (e.g., .zip, .csv, .json, .pdf, .html)
    if path_filename and re.search(r"\.[a-zA-Z0-9]{2,5}$", path_filename):
        return path_filename

    # Fallback: slugify source name and append extension based on format
    source_name = source_entry.get("source_name", "raw_data")
    slug = re.sub(r"[^\w\-_]", "_", source_name.lower())
    slug = re.sub(r"_+", "_", slug).strip("_")

    fmt = str(source_entry.get("format", "")).lower()
    if "zip" in fmt:
        ext = ".zip"
    elif "csv" in fmt:
        ext = ".csv"
    elif "json" in fmt:
        ext = ".json"
    elif "html" in fmt or "web" in fmt:
        ext = ".html"
    elif "pdf" in fmt:
        ext = ".pdf"
    else:
        ext = ".dat"

    return f"{slug}{ext}"


def download_source(
    source_name: str,
    config_path: Union[str, Path] = "configs/data_sources.yaml",
    raw_dir: Optional[Path] = None,
    overwrite: bool = False,
    opener: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Acquire raw data for a specific source configured in data_sources.yaml.

    Preserves original downloaded file in data/raw/, prevents silent overwrites,
    calculates SHA-256 hash, and updates the provenance manifest data/raw/manifest.json.

    Args:
        source_name: Name of the configured data source to download.
        config_path: Path to data_sources.yaml.
        raw_dir: Directory where raw files are saved (defaults to project data/raw/).
        overwrite: If False, raises DuplicateFileError if target file already exists.
        opener: Optional urlopen callable (for mocking in tests).

    Returns:
        Provenance manifest entry dict for the acquired dataset.

    Raises:
        IngestionError: If source is unlisted or download fails.
        DuplicateFileError: If file already exists and overwrite is False.
    """
    source = get_source_by_name(source_name, config_path=config_path)

    root = get_project_root()
    if raw_dir is None:
        target_dir = root / "data" / "raw"
    else:
        target_dir = Path(raw_dir)

    target_dir.mkdir(parents=True, exist_ok=True)

    filename = derive_deterministic_filename(source)
    filename = os.path.basename(filename)
    target_path = (target_dir / filename).resolve()

    # Path traversal safeguard
    resolved_dir = target_dir.resolve()
    if not target_path.is_relative_to(resolved_dir) if hasattr(target_path, "is_relative_to") else not str(target_path).startswith(str(resolved_dir)):
        raise IngestionError(f"Invalid target path '{target_path}': path traversal attempt detected.")

    if target_path.exists() and not overwrite:
        raise DuplicateFileError(
            f"Raw file already exists at '{target_path}'. "
            "Raw files are immutable and silent overwrites are strictly prohibited. "
            "Set overwrite=True only if explicit re-acquisition is intended."
        )

    url = source.get("url")
    if not url:
        raise IngestionError(f"Data source '{source_name}' has no configured URL.")

    # Execute HTTP GET
    http_status = None
    content_type = None

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "RCB-Auction-Intelligence-Engine/1.0 (Research Pipeline)"
            },
        )

        if opener is None:
            opener = urllib.request.urlopen

        with opener(req) as response:
            http_status = getattr(response, "status", getattr(response, "code", 200))
            headers = getattr(response, "headers", None)
            if headers:
                content_type = headers.get("Content-Type")

            content_bytes = response.read()

        # Write untouched raw content to file
        with open(target_path, "wb") as f:
            f.write(content_bytes)

    except DuplicateFileError:
        raise
    except Exception as exc:
        raise IngestionError(
            f"Failed to download raw data for source '{source_name}' from '{url}': {exc}"
        ) from exc

    # Calculate checksum and file size
    sha256_hash = compute_sha256(target_path)
    file_size_bytes = target_path.stat().st_size
    retrieved_at = datetime.now(timezone.utc).isoformat()

    # Determine relative path from project root for portability
    try:
        relative_path = target_path.relative_to(root).as_posix()
    except ValueError:
        relative_path = target_path.as_posix()

    entry = {
        "source_name": source["source_name"],
        "provider": source.get("provider", ""),
        "url": url,
        "local_path": relative_path,
        "file_size_bytes": file_size_bytes,
        "sha256": sha256_hash,
        "retrieved_at": retrieved_at,
        "http_status": http_status,
        "content_type": content_type,
        "license_or_usage_notes": source.get("license_or_usage_notes", ""),
        "authority_level": source.get("authority_level", "unspecified"),
    }

    # Update provenance manifest
    manifest_path = get_manifest_path(target_dir)
    manifest_data = load_manifest(manifest_path)
    record_manifest_entry(manifest_data, entry)
    save_manifest(manifest_data, manifest_path)

    return entry
