"""Unit tests for raw data acquisition and provenance tracking."""

from io import BytesIO
import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from src.ingestion.fetcher import (
    derive_deterministic_filename,
    download_source,
    get_source_by_name,
    load_source_register,
)
from src.ingestion.manifest import (
    compute_bytes_sha256,
    compute_sha256,
    get_manifest_path,
    load_manifest,
    record_manifest_entry,
    save_manifest,
    verify_file_provenance,
)
from src.utils.exceptions import (
    ConfigurationError,
    DuplicateFileError,
    IngestionError,
    ProvenanceError,
)


@pytest.fixture
def mock_sources_yaml(temp_dir):
    """Create a temporary data_sources.yaml for unit testing without internet access."""
    config_file = temp_dir / "data_sources.yaml"
    content = """
sources:
  - source_name: "Mock Cricsheet IPL"
    provider: "Cricsheet"
    url: "https://cricsheet.org/downloads/ipl_json.zip"
    format: "JSON (ZIP archive)"
    license_or_usage_notes: "ODC-By 1.0"
    authority_level: "primary"

  - source_name: "Mock People Register"
    provider: "Cricsheet"
    url: "https://cricsheet.org/register/people.csv"
    format: "CSV"
    license_or_usage_notes: "ODC-By 1.0"
    authority_level: "primary"

  - source_name: "Mock IPL Auction Archive"
    provider: "BCCI"
    url: "https://www.iplt20.com/auction"
    format: "Web HTML"
    license_or_usage_notes: "Terms apply"
    authority_level: "primary"
"""
    config_file.write_text(content, encoding="utf-8")
    return config_file


def test_compute_sha256(temp_dir):
    """Verify SHA-256 calculation for files and bytes."""
    test_file = temp_dir / "sample.txt"
    test_file.write_bytes(b"hello world")

    expected_hash = compute_bytes_sha256(b"hello world")
    actual_hash = compute_sha256(test_file)

    assert actual_hash == expected_hash
    assert len(actual_hash) == 64


def test_compute_sha256_file_not_found(temp_dir):
    """Verify compute_sha256 raises ProvenanceError on non-existent file."""
    missing_file = temp_dir / "missing.txt"
    with pytest.raises(ProvenanceError, match="File not found"):
        compute_sha256(missing_file)


def test_derive_deterministic_filename():
    """Verify deterministic filename derivation logic across formats."""
    # Explicit URL filename
    entry_ipl = {
        "source_name": "Cricsheet IPL",
        "url": "https://cricsheet.org/downloads/ipl_json.zip",
        "format": "JSON (ZIP archive)",
    }
    assert derive_deterministic_filename(entry_ipl) == "ipl_json.zip"

    # Explicit CSV filename
    entry_people = {
        "source_name": "People Register",
        "url": "https://cricsheet.org/register/people.csv",
        "format": "CSV",
    }
    assert derive_deterministic_filename(entry_people) == "people.csv"

    # Web URL without filename extension -> slug fallback
    entry_auction = {
        "source_name": "IPL Official Auction Archive",
        "url": "https://www.iplt20.com/auction",
        "format": "Web HTML",
    }
    assert (
        derive_deterministic_filename(entry_auction)
        == "ipl_official_auction_archive.html"
    )

    # Explicit filename override
    entry_override = {
        "source_name": "Custom Source",
        "url": "https://example.com/data",
        "filename": "custom_filename.data",
    }
    assert derive_deterministic_filename(entry_override) == "custom_filename.data"


def test_source_lookup(mock_sources_yaml):
    """Verify loading source register and fetching by name."""
    register = load_source_register(mock_sources_yaml)
    assert len(register["sources"]) == 3

    source = get_source_by_name("Mock Cricsheet IPL", config_path=mock_sources_yaml)
    assert source["provider"] == "Cricsheet"
    assert source["url"] == "https://cricsheet.org/downloads/ipl_json.zip"


def test_source_lookup_unlisted(mock_sources_yaml):
    """Verify lookup raises IngestionError for unlisted sources."""
    with pytest.raises(IngestionError, match="is not configured"):
        get_source_by_name("Nonexistent Source", config_path=mock_sources_yaml)


def test_download_source_mocked(temp_dir, mock_sources_yaml):
    """Test full acquisition workflow using a mocked HTTP opener."""
    raw_dir = temp_dir / "raw"
    mock_content = b"fake zip content for IPL ball-by-ball dataset"

    # Create mock response object
    mock_response = BytesIO(mock_content)
    mock_response.status = 200
    mock_response.headers = {"Content-Type": "application/zip"}

    mock_opener = MagicMock(return_value=mock_response)

    entry = download_source(
        source_name="Mock Cricsheet IPL",
        config_path=mock_sources_yaml,
        raw_dir=raw_dir,
        overwrite=False,
        opener=mock_opener,
    )

    # Check file was saved correctly
    saved_file = raw_dir / "ipl_json.zip"
    assert saved_file.exists()
    assert saved_file.read_bytes() == mock_content

    # Verify return entry details
    assert entry["source_name"] == "Mock Cricsheet IPL"
    assert entry["file_size_bytes"] == len(mock_content)
    assert entry["sha256"] == compute_bytes_sha256(mock_content)
    assert entry["http_status"] == 200
    assert entry["content_type"] == "application/zip"

    # Verify manifest was created
    manifest_file = raw_dir / "manifest.json"
    assert manifest_file.exists()
    manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert "Mock Cricsheet IPL" in manifest_data["entries"]


def test_duplicate_file_protection(temp_dir, mock_sources_yaml):
    """Verify that existing raw data files are protected against silent overwrite."""
    raw_dir = temp_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Pre-create the raw file
    existing_file = raw_dir / "ipl_json.zip"
    existing_file.write_bytes(b"existing untouched file content")

    mock_opener = MagicMock()

    # Default overwrite=False should raise DuplicateFileError
    with pytest.raises(DuplicateFileError, match="already exists"):
        download_source(
            source_name="Mock Cricsheet IPL",
            config_path=mock_sources_yaml,
            raw_dir=raw_dir,
            overwrite=False,
            opener=mock_opener,
        )

    # File content should remain untouched
    assert existing_file.read_bytes() == b"existing untouched file content"
    mock_opener.assert_not_called()


def test_manifest_load_save_record(temp_dir):
    """Verify manifest creation, loading, record update, and persistence."""
    manifest_path = temp_dir / "manifest.json"

    # Loading non-existent manifest returns default empty schema
    data = load_manifest(manifest_path)
    assert data["manifest_version"] == "1.0"
    assert data["entries"] == {}

    entry = {
        "source_name": "Test Source",
        "url": "https://example.com/data.csv",
        "local_path": "data/raw/data.csv",
        "sha256": "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
    }

    record_manifest_entry(data, entry)
    save_manifest(data, manifest_path)

    # Reload and verify
    reloaded = load_manifest(manifest_path)
    assert "Test Source" in reloaded["entries"]
    assert reloaded["entries"]["Test Source"]["sha256"] == entry["sha256"]


def test_verify_file_provenance(temp_dir):
    """Verify end-to-end provenance integrity checking."""
    root = temp_dir
    raw_dir = root / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    raw_file = raw_dir / "sample.csv"
    payload = b"id,name\n1,Virat\n"
    raw_file.write_bytes(payload)

    file_hash = compute_bytes_sha256(payload)

    manifest_data = {
        "manifest_version": "1.0",
        "entries": {
            "Sample Dataset": {
                "source_name": "Sample Dataset",
                "local_path": "data/raw/sample.csv",
                "sha256": file_hash,
            }
        },
    }

    manifest_path = save_manifest(manifest_data, get_manifest_path(raw_dir))

    # Provenance check should pass
    assert verify_file_provenance(
        source_name="Sample Dataset",
        manifest_path=manifest_path,
        project_root=root,
    )

    # Alter file content and verify ProvenanceError is raised
    raw_file.write_bytes(b"corrupted payload")
    with pytest.raises(ProvenanceError, match="Integrity check failed"):
        verify_file_provenance(
            source_name="Sample Dataset",
            manifest_path=manifest_path,
            project_root=root,
        )


def test_download_unlisted_source_fails(temp_dir, mock_sources_yaml):
    """Verify attempting to download an unlisted source fails loudly."""
    with pytest.raises(IngestionError, match="is not configured"):
        download_source(
            source_name="Unlisted Dataset",
            config_path=mock_sources_yaml,
            raw_dir=temp_dir / "raw",
        )


def test_path_traversal_prevention(temp_dir, mock_sources_yaml):
    """Verify that path traversal filenames are sanitized safely to target_dir."""
    raw_dir = temp_dir / "raw"
    entry_traversal = {
        "source_name": "Mock Malicious",
        "url": "https://example.com/../../etc/passwd",
        "filename": "../../etc/passwd",
    }
    filename = derive_deterministic_filename(entry_traversal)
    # os.path.basename strips directory components
    assert ".." not in filename
    assert filename == "passwd"

