from pathlib import Path
from zipfile import ZipFile
import hashlib

import pytest

from src.ingestion.cricsheet import (
    CRICSHEET_SOURCES,
    _safe_extract,
    ingest_competition,
)


def test_cricsheet_sources_are_configured():
    assert set(CRICSHEET_SOURCES) == {
        "ipl",
        "sma",
        "bbl",
        "cpl",
        "sat",
        "ilt",
        "mlc",
        "hnd",
    }


def test_safe_extract_extracts_files(tmp_path):
    archive_path = tmp_path / "sample.zip"
    output_dir = tmp_path / "output"

    with ZipFile(archive_path, "w") as archive:
        archive.writestr("123456.json", '{"meta": {}}')
        archive.writestr("789012.json", '{"meta": {}}')

    extracted = _safe_extract(archive_path, output_dir)

    assert len(extracted) == 2
    assert (output_dir / "123456.json").exists()
    assert (output_dir / "789012.json").exists()


def test_safe_extract_rejects_path_traversal(tmp_path):
    archive_path = tmp_path / "unsafe.zip"
    output_dir = tmp_path / "output"

    with ZipFile(archive_path, "w") as archive:
        archive.writestr("../escape.txt", "unsafe")

    with pytest.raises(Exception, match="path traversal"):
        _safe_extract(archive_path, output_dir)


def test_unknown_competition_is_rejected():
    with pytest.raises(Exception, match="Unknown Cricsheet competition"):
        ingest_competition("unknown")


def test_empty_archive_is_rejected(tmp_path, monkeypatch):
    archive_path = tmp_path / "empty.zip"

    with ZipFile(archive_path, "w"):
        pass

    sha256 = hashlib.sha256(archive_path.read_bytes()).hexdigest()

    def fake_download_source(*args, **kwargs):
        return {
            "local_path": str(archive_path),
            "sha256": sha256,
        }

    monkeypatch.setattr(
        "src.ingestion.cricsheet.download_source",
        fake_download_source,
    )

    with pytest.raises(Exception, match="No non-empty extracted files"):
        ingest_competition("ipl")