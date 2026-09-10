"""Cricsheet competition archive ingestion and verification."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List
import zipfile

from src.ingestion.fetcher import download_source
from src.ingestion.manifest import compute_sha256
from src.utils.config import get_project_root
from src.utils.exceptions import IngestionError


CRICSHEET_SOURCES = {
    "ipl": "Cricsheet IPL Ball-by-Ball Dataset",
    "sma": "Cricsheet Syed Mushtaq Ali Trophy Ball-by-Ball Dataset",
    "bbl": "Cricsheet Big Bash League Ball-by-Ball Dataset",
    "cpl": "Cricsheet Caribbean Premier League Ball-by-Ball Dataset",
    "sat": "Cricsheet SA20 Ball-by-Ball Dataset",
    "ilt": "Cricsheet International League T20 Ball-by-Ball Dataset",
    "mlc": "Cricsheet Major League Cricket Ball-by-Ball Dataset",
    "hnd": "Cricsheet The Hundred Ball-by-Ball Dataset",
}


def _safe_extract(zip_path: Path, output_dir: Path) -> List[Path]:
    """Extract a Cricsheet ZIP archive without allowing path traversal."""
    output_dir.mkdir(parents=True, exist_ok=True)

    extracted: List[Path] = []
    root = output_dir.resolve()

    with zipfile.ZipFile(zip_path, "r") as archive:
        for member in archive.infolist():
            target = (output_dir / member.filename).resolve()

            if not target.is_relative_to(root):
                raise IngestionError(
                    f"Unsafe ZIP member '{member.filename}': "
                    "path traversal detected."
                )

            archive.extract(member, output_dir)

            if not member.is_dir():
                extracted.append(target)

    return extracted


def ingest_competition(
    competition: str,
    *,
    config_path: str = "configs/data_sources.yaml",
    overwrite: bool = False,
) -> Dict[str, object]:
    """
    Download, verify, and extract one configured Cricsheet competition.

    Returns a summary containing the archive path, SHA-256 hash,
    extracted file count, and extracted byte count.
    """
    if competition not in CRICSHEET_SOURCES:
        valid = ", ".join(sorted(CRICSHEET_SOURCES))
        raise IngestionError(
            f"Unknown Cricsheet competition '{competition}'. "
            f"Expected one of: {valid}"
        )

    source_name = CRICSHEET_SOURCES[competition]
    root = get_project_root()
    raw_dir = root / "data" / "raw" / "cricsheet"

    raw_dir.mkdir(parents=True, exist_ok=True)

    entry = download_source(
        source_name,
        config_path=config_path,
        raw_dir=raw_dir,
        overwrite=overwrite,
    )

    archive_path = root / entry["local_path"]

    if not archive_path.exists():
        raise IngestionError(
            f"Downloaded Cricsheet archive does not exist: {archive_path}"
        )

    if archive_path.stat().st_size == 0:
        raise IngestionError(
            f"Downloaded Cricsheet archive is empty: {archive_path}"
        )

    actual_sha256 = compute_sha256(archive_path)

    if actual_sha256 != entry["sha256"]:
        raise IngestionError(
            f"SHA-256 verification failed for '{source_name}': "
            f"manifest={entry['sha256']}, actual={actual_sha256}"
        )

    extract_dir = raw_dir / competition
    extracted_files = _safe_extract(archive_path, extract_dir)

    non_empty_files = [
        path for path in extracted_files
        if path.is_file() and path.stat().st_size > 0
    ]

    if not non_empty_files:
        raise IngestionError(
            f"No non-empty extracted files found for '{source_name}'."
        )

    return {
        "competition": competition,
        "source_name": source_name,
        "archive_path": str(archive_path),
        "sha256": actual_sha256,
        "extracted_file_count": len(non_empty_files),
        "extracted_bytes": sum(
            path.stat().st_size for path in non_empty_files
        ),
    }


def ingest_competitions(
    competitions: Iterable[str],
    *,
    config_path: str = "configs/data_sources.yaml",
    overwrite: bool = False,
) -> List[Dict[str, object]]:
    """Ingest multiple configured Cricsheet competitions."""
    return [
        ingest_competition(
            competition,
            config_path=config_path,
            overwrite=overwrite,
        )
        for competition in competitions
    ]