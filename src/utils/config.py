"""Configuration loader utility for the RCB Auction Intelligence Engine."""

from pathlib import Path
from typing import Any, Dict, Optional, Union
import yaml

from src.utils.exceptions import ConfigurationError


def get_project_root() -> Path:
    """Return the absolute Path to the root of the project repository."""
    # Location: src/utils/config.py -> parent(utils) -> parent(src) -> parent(root)
    return Path(__file__).resolve().parent.parent.parent


def load_config(config_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Load a YAML configuration file.

    Args:
        config_path: Path to YAML config file (absolute or relative to project root).

    Returns:
        Dict containing configuration key-value mapping.

    Raises:
        ConfigurationError: If the file is missing, unreadable, or invalid YAML.
    """
    path = Path(config_path)
    if not path.is_absolute():
        path = get_project_root() / path

    if not path.exists():
        raise ConfigurationError(f"Configuration file not found: {path}")

    if not path.is_file():
        raise ConfigurationError(f"Configuration path is not a file: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Error parsing YAML file '{path}': {exc}") from exc
    except Exception as exc:
        raise ConfigurationError(f"Error reading configuration file '{path}': {exc}") from exc

    if data is None:
        return {}

    if not isinstance(data, dict):
        raise ConfigurationError(
            f"Configuration file '{path}' must contain a YAML dictionary, got {type(data).__name__}."
        )

    return data


def resolve_path(path_str: Union[str, Path], base_dir: Optional[Path] = None) -> Path:
    """
    Resolve a path relative to project root (or base_dir if specified).

    Args:
        path_str: Relative or absolute path string or Path object.
        base_dir: Optional base directory for resolution (defaults to project root).

    Returns:
        Resolved absolute Path.
    """
    if base_dir is None:
        base_dir = get_project_root()

    path = Path(path_str)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()
