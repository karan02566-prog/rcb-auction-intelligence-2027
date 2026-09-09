"""Unit tests for src/utils (config, logger, exceptions)."""

import logging
from pathlib import Path
import pytest
import yaml

from src.utils.config import get_project_root, load_config, resolve_path
from src.utils.exceptions import (
    ConfigurationError,
    DataQualityError,
    IngestionError,
    RCBProjectError,
    ValidationError,
)
from src.utils.logger import get_logger


def test_exception_hierarchy():
    """Verify custom exceptions inherit from base RCBProjectError."""
    assert issubclass(ConfigurationError, RCBProjectError)
    assert issubclass(IngestionError, RCBProjectError)
    assert issubclass(ValidationError, RCBProjectError)
    assert issubclass(DataQualityError, RCBProjectError)

    err = ConfigurationError("Test error")
    assert isinstance(err, RCBProjectError)
    assert str(err) == "Test error"


def test_logger_creation_and_no_duplicates():
    """Verify logger setup and handler deduplication."""
    logger_name = "test_rcb_logger"
    logger1 = get_logger(name=logger_name, level=logging.DEBUG)
    assert logger1.name == logger_name
    assert logger1.level == logging.DEBUG
    initial_handler_count = len(logger1.handlers)
    assert initial_handler_count == 1

    # Calling get_logger again should not add a duplicate handler
    logger2 = get_logger(name=logger_name, level=logging.INFO)
    assert len(logger2.handlers) == initial_handler_count


def test_get_project_root(project_root):
    """Verify project root resolution."""
    root = get_project_root()
    assert root.exists()
    assert (root / "PRD.md").exists()
    assert root == project_root


def test_load_config_valid(temp_dir):
    """Verify loading valid YAML config file."""
    config_file = temp_dir / "sample_config.yaml"
    data = {"database": {"name": "rcb_db"}, "thresholds": {"min_balls": 30}}
    config_file.write_text(yaml.dump(data), encoding="utf-8")

    loaded = load_config(config_file)
    assert loaded == data
    assert loaded["database"]["name"] == "rcb_db"


def test_load_config_empty(temp_dir):
    """Verify loading empty YAML file returns empty dict."""
    config_file = temp_dir / "empty.yaml"
    config_file.write_text("", encoding="utf-8")

    loaded = load_config(config_file)
    assert loaded == {}


def test_load_config_missing():
    """Verify loading missing config file raises ConfigurationError."""
    with pytest.raises(ConfigurationError, match="Configuration file not found"):
        load_config("non_existent_config_file_12345.yaml")


def test_load_config_invalid_yaml(temp_dir):
    """Verify loading malformed YAML raises ConfigurationError."""
    config_file = temp_dir / "bad_syntax.yaml"
    config_file.write_text("key: [unclosed_list", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="Error parsing YAML file"):
        load_config(config_file)


def test_load_config_non_dict_yaml(temp_dir):
    """Verify YAML that evaluates to non-dict raises ConfigurationError."""
    config_file = temp_dir / "list_config.yaml"
    config_file.write_text("- item1\n- item2", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="must contain a YAML dictionary"):
        load_config(config_file)


def test_resolve_path():
    """Verify resolve_path works for absolute and relative paths."""
    root = get_project_root()
    resolved_rel = resolve_path("data/raw")
    assert resolved_rel == (root / "data" / "raw").resolve()

    abs_path = root / "PRD.md"
    resolved_abs = resolve_path(abs_path)
    assert resolved_abs == abs_path.resolve()
