"""Unit tests for Phase 1.5 provenance verification."""

import json
from pathlib import Path

from src.ingestion.manifest import compute_bytes_sha256, load_manifest, save_manifest, record_manifest_entry
from src.ingestion.verify_provenance import (
    find_untracked_raw_files,
    verify_all_sources,
    generate_provenance_report,
)


def _make_manifest_with_one_valid_entry(tmp_path):
    raw_dir = tmp_path / "data" / "raw"
    raw_dir.mkdir(parents=True)
    data_file = raw_dir / "sample.json"
    data_file.write_bytes(b'{"ok": true}')

    manifest_path = raw_dir / "manifest.json"
    manifest = {"manifest_version": "1.0", "updated_at": None, "entries": {}}
    manifest = record_manifest_entry(
        manifest,
        {
            "source_name": "Test Source",
            "local_path": str(Path("data/raw/sample.json")),
            "sha256": compute_bytes_sha256(data_file.read_bytes()),
        },
    )
    save_manifest(manifest, manifest_path)
    return raw_dir, manifest_path, data_file


def test_verify_all_sources_no_manifest_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("src.ingestion.verify_provenance.get_project_root", lambda: tmp_path)
    monkeypatch.setattr("src.ingestion.manifest.get_project_root", lambda: tmp_path)
    result = verify_all_sources()
    assert result["verified"] == []
    assert result["failed"] == []


def test_find_untracked_raw_files_detects_extra_file(tmp_path, monkeypatch):
    raw_dir, manifest_path, _ = _make_manifest_with_one_valid_entry(tmp_path)
    stray = raw_dir / "stray.csv"
    stray.write_text("a,b\n1,2\n", encoding="utf-8")

    untracked = find_untracked_raw_files(
        raw_dir=raw_dir,
        manifest_entries={
            "Test Source": {"local_path": "data/raw/sample.json"},
        },
    )
    assert any("stray.csv" in u for u in untracked)
    assert not any("sample.json" in u for u in untracked)
    assert not any("manifest.json" in u for u in untracked)


def test_find_untracked_raw_files_none_when_fully_tracked(tmp_path):
    raw_dir, _, _ = _make_manifest_with_one_valid_entry(tmp_path)
    untracked = find_untracked_raw_files(
        raw_dir=raw_dir,
        manifest_entries={"Test Source": {"local_path": "data/raw/sample.json"}},
    )
    assert untracked == []


def test_find_untracked_raw_files_missing_dir_returns_empty(tmp_path):
    untracked = find_untracked_raw_files(raw_dir=tmp_path / "does_not_exist", manifest_entries={})
    assert untracked == []


def test_generate_provenance_report_writes_valid_json(tmp_path, monkeypatch):
    monkeypatch.setattr("src.ingestion.verify_provenance.get_project_root", lambda: tmp_path)
    monkeypatch.setattr("src.ingestion.manifest.get_project_root", lambda: tmp_path)

    out_path = tmp_path / "reports" / "data_provenance_manifest.json"
    result_path = generate_provenance_report(out_path)

    assert result_path == out_path
    assert out_path.exists()
    report = json.loads(out_path.read_text(encoding="utf-8"))
    assert "sha256_verification" in report
    assert "untracked_raw_files" in report
    assert "status" in report
    assert report["status"] in ("PASS", "ATTENTION_REQUIRED")


def test_generate_provenance_report_status_pass_when_clean(tmp_path, monkeypatch):
    raw_dir, manifest_path, data_file = _make_manifest_with_one_valid_entry(tmp_path)
    monkeypatch.setattr("src.ingestion.verify_provenance.get_project_root", lambda: tmp_path)
    monkeypatch.setattr("src.ingestion.manifest.get_project_root", lambda: tmp_path)

    out_path = tmp_path / "reports" / "data_provenance_manifest.json"
    generate_provenance_report(out_path)
    report = json.loads(out_path.read_text(encoding="utf-8"))

    assert report["sha256_verification"]["verified_count"] == 1
    assert report["sha256_verification"]["failed_count"] == 0
    assert report["untracked_raw_files"]["count"] == 0
    assert report["status"] == "PASS"


def test_register_untracked_raw_files_backfills_and_reaches_zero(tmp_path, monkeypatch):
    from src.ingestion.verify_provenance import register_untracked_raw_files

    raw_dir, manifest_path, _ = _make_manifest_with_one_valid_entry(tmp_path)
    stray = raw_dir / "extracted" / "match1.json"
    stray.parent.mkdir(parents=True)
    stray.write_text('{"id": 1}', encoding="utf-8")

    monkeypatch.setattr("src.ingestion.verify_provenance.get_project_root", lambda: tmp_path)
    monkeypatch.setattr("src.ingestion.manifest.get_project_root", lambda: tmp_path)

    n = register_untracked_raw_files()
    assert n == 1

    remaining = find_untracked_raw_files()
    assert remaining == []

    # idempotent: second run registers nothing new
    assert register_untracked_raw_files() == 0


def test_prune_missing_manifest_entries_removes_deleted_file(tmp_path, monkeypatch):
    from src.ingestion.verify_provenance import prune_missing_manifest_entries

    raw_dir, manifest_path, data_file = _make_manifest_with_one_valid_entry(tmp_path)
    monkeypatch.setattr("src.ingestion.verify_provenance.get_project_root", lambda: tmp_path)
    monkeypatch.setattr("src.ingestion.manifest.get_project_root", lambda: tmp_path)

    data_file.unlink()  # simulate deleting the raw file from disk

    removed = prune_missing_manifest_entries()
    assert removed == ["Test Source"]

    manifest = load_manifest()
    assert manifest["entries"] == {}


def test_prune_missing_manifest_entries_keeps_present_files(tmp_path, monkeypatch):
    from src.ingestion.verify_provenance import prune_missing_manifest_entries

    _make_manifest_with_one_valid_entry(tmp_path)
    monkeypatch.setattr("src.ingestion.verify_provenance.get_project_root", lambda: tmp_path)
    monkeypatch.setattr("src.ingestion.manifest.get_project_root", lambda: tmp_path)

    removed = prune_missing_manifest_entries()
    assert removed == []
    assert "Test Source" in load_manifest()["entries"]