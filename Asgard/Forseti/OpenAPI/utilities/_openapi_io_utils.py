"""
OpenAPI IO Utilities - File loading and saving helpers.
"""

import json
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]

from Asgard.Forseti.OpenAPI.models.openapi_models import OpenAPIVersion


def load_spec_file(file_path: Path) -> dict[str, Any]:
    """
    Load an OpenAPI specification from a file.

    Supports JSON and YAML formats based on file extension.

    Args:
        file_path: Path to the specification file.

    Returns:
        Parsed specification as a dictionary.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is not supported or parsing fails.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Specification file not found: {file_path}")

    content = file_path.read_text(encoding="utf-8")
    suffix = file_path.suffix.lower()

    try:
        if suffix in [".json"]:
            return cast(dict[str, Any], json.loads(content))
        elif suffix in [".yaml", ".yml"]:
            return cast(dict[str, Any], yaml.safe_load(content))
        else:
            try:
                return cast(dict[str, Any], json.loads(content))
            except json.JSONDecodeError:
                return cast(dict[str, Any], yaml.safe_load(content))
    except Exception as e:
        raise ValueError(f"Failed to parse specification file: {e}")


def save_spec_file(file_path: Path, spec_data: dict[str, Any]) -> None:
    """
    Save an OpenAPI specification to a file.

    Determines format based on file extension.

    Args:
        file_path: Path to save the specification.
        spec_data: Specification data to save.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = file_path.suffix.lower()

    if suffix in [".json"]:
        content = json.dumps(spec_data, indent=2)
    else:
        content = yaml.dump(spec_data, default_flow_style=False, sort_keys=False)

    file_path.write_text(content, encoding="utf-8")


def detect_openapi_version(spec_data: dict[str, Any]) -> OpenAPIVersion | None:
    """
    Detect the OpenAPI version from specification data.

    Args:
        spec_data: Parsed specification dictionary.

    Returns:
        Detected OpenAPIVersion or None if unknown.
    """
    if "openapi" in spec_data:
        version_str = spec_data["openapi"]
        if version_str.startswith("3.1"):
            return OpenAPIVersion.V3_1
        elif version_str.startswith("3.0"):
            return OpenAPIVersion.V3_0
    elif "swagger" in spec_data:
        version_str = spec_data["swagger"]
        if version_str.startswith("2."):
            return OpenAPIVersion.V2_0
    return None
