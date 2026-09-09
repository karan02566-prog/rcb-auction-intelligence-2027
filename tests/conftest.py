"""Pytest fixtures and shared configuration for testing."""

import shutil
import tempfile
from pathlib import Path
import pytest

from src.utils.config import get_project_root


@pytest.fixture
def project_root() -> Path:
    """Provide absolute Path to project root directory."""
    return get_project_root()


@pytest.fixture
def temp_dir():
    """Provide a temporary directory cleaned up after test completion."""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)
