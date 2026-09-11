"""Unit tests for the source catalog (configs/source_manifest.json) validation logic."""

import json
import pytest

from src.ingestion.manifest import (
    get_source_catalog_path,
    load_source_catalog,
    validate_source_catalog,
    REQUIRED_SOURCE_FIELDS,
)
from src.utils.exceptions import ProvenanceError


def _valid_entry(**overrides):
    entry = {
        "source_name": "Test Source",
        "competition": "IPL",
        "provider": "Test Provider",
        "url": "https://example.com/data.zip",
        "format": "JSON",
        "scope": "test scope",
        "license": "Test License",
        "authority_level": "primary",
        "status": "active",
        "known_limitations": "none",
    }
    entry.update(overrides)
    return entry


def test_source_catalog_file_exists_and_loads():
    """The real configs/source_manifest.json must exist and load as valid JSON."""
    path = get_source_catalog_path()
    assert path.exists(), f"Missing source catalog at {path}"
    catalog = load_source_catalog(path)
    assert isinstance(catalog["sources"], list)
    assert len(catalog["sources"]) > 0


def test_real_source_catalog_passes_validation():
    """The real project source catalog must satisfy schema and coverage rules."""
    catalog = load_source_catalog()
    assert validate_source_catalog(catalog) is True


def test_real_source_catalog_covers_required_competitions():
    catalog = load_source_catalog()
    required = catalog["required_competitions"]
    expected = ["IPL", "BBL", "CPL", "SA20", "ILT20", "MLC", "The Hundred", "Indian Domestic T20s"]
    for competition in expected:
        assert competition in required


def test_load_source_catalog_missing_file_raises(tmp_path):
    with pytest.raises(ProvenanceError):
        load_source_catalog(tmp_path / "does_not_exist.json")


def test_load_source_catalog_malformed_json_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ProvenanceError):
        load_source_catalog(bad)


def test_load_source_catalog_missing_sources_key_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"manifest_version": "1.0"}), encoding="utf-8")
    with pytest.raises(ProvenanceError):
        load_source_catalog(bad)


def test_validate_source_catalog_empty_sources_raises():
    with pytest.raises(ProvenanceError):
        validate_source_catalog({"sources": []})


def test_validate_source_catalog_missing_required_field_raises():
    entry = _valid_entry()
    del entry["license"]
    with pytest.raises(ProvenanceError, match="missing required field"):
        validate_source_catalog({"sources": [entry]})


def test_validate_source_catalog_duplicate_source_name_raises():
    entry_a = _valid_entry()
    entry_b = _valid_entry()
    with pytest.raises(ProvenanceError, match="Duplicate source_name"):
        validate_source_catalog({"sources": [entry_a, entry_b]})


def test_validate_source_catalog_invalid_status_raises():
    entry = _valid_entry(status="not_a_real_status")
    with pytest.raises(ProvenanceError, match="invalid status"):
        validate_source_catalog({"sources": [entry]})


def test_validate_source_catalog_active_without_url_raises():
    entry = _valid_entry(url=None)
    with pytest.raises(ProvenanceError, match="missing a 'url'"):
        validate_source_catalog({"sources": [entry]})


def test_validate_source_catalog_planned_without_url_is_allowed():
    entry = _valid_entry(url=None, status="planned")
    assert validate_source_catalog({"sources": [entry]}) is True


def test_validate_source_catalog_missing_required_competition_raises():
    entry = _valid_entry(competition="IPL")
    catalog = {"sources": [entry], "required_competitions": ["IPL", "BBL"]}
    with pytest.raises(ProvenanceError, match="Required competition 'BBL'"):
        validate_source_catalog(catalog)


def test_required_source_fields_constant_matches_rules_md():
    """rules.md Section 2 requires: source, URL, retrieval date, competition,
    seasons, format, known limitations. We track these as source_name/provider,
    url, (per-file provenance log), competition, scope, format, known_limitations."""
    for field in ("source_name", "competition", "url", "format", "known_limitations"):
        assert field in REQUIRED_SOURCE_FIELDS