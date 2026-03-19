"""
OpenAPI Utilities - Helper functions for OpenAPI specification handling.
"""

import json
import re
from pathlib import Path
from typing import Any, Optional, cast
from urllib.parse import urlparse

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
            # Try JSON first, then YAML
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


def detect_openapi_version(spec_data: dict[str, Any]) -> Optional[OpenAPIVersion]:
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


def normalize_path(path: str) -> str:
    """
    Normalize an API path.

    - Ensures path starts with /
    - Removes trailing slashes
    - Normalizes path parameters

    Args:
        path: API path string.

    Returns:
        Normalized path string.
    """
    if not path.startswith("/"):
        path = "/" + path

    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # Normalize path parameters to consistent format
    path = re.sub(r"\{([^}]+)\}", lambda m: "{" + m.group(1).strip() + "}", path)

    return path


def merge_specs(
    base_spec: dict[str, Any],
    overlay_spec: dict[str, Any],
    conflict_strategy: str = "overlay"
) -> dict[str, Any]:
    """
    Merge two OpenAPI specifications.

    Args:
        base_spec: Base specification.
        overlay_spec: Specification to overlay on base.
        conflict_strategy: How to handle conflicts ("overlay", "base", "error").

    Returns:
        Merged specification.

    Raises:
        ValueError: If conflict_strategy is "error" and conflicts exist.
    """
    merged = dict(base_spec)

    # Merge info (overlay wins for simple fields)
    if "info" in overlay_spec:
        merged["info"] = {**merged.get("info", {}), **overlay_spec["info"]}

    # Merge servers
    if "servers" in overlay_spec:
        if conflict_strategy == "overlay":
            merged["servers"] = overlay_spec["servers"]
        else:
            merged["servers"] = merged.get("servers", []) + overlay_spec["servers"]

    # Merge paths
    if "paths" in overlay_spec:
        merged_paths = dict(merged.get("paths", {}))
        for path, path_item in overlay_spec["paths"].items():
            if path in merged_paths:
                if conflict_strategy == "error":
                    raise ValueError(f"Path conflict: {path}")
                elif conflict_strategy == "overlay":
                    merged_paths[path] = {**merged_paths[path], **path_item}
                # base strategy: keep base
            else:
                merged_paths[path] = path_item
        merged["paths"] = merged_paths

    # Merge components
    if "components" in overlay_spec:
        merged_components = dict(merged.get("components", {}))
        for component_type, components in overlay_spec["components"].items():
            if component_type not in merged_components:
                merged_components[component_type] = {}
            for name, component in components.items():
                if name in merged_components[component_type]:
                    if conflict_strategy == "error":
                        raise ValueError(f"Component conflict: {component_type}/{name}")
                    elif conflict_strategy == "overlay":
                        merged_components[component_type][name] = component
                else:
                    merged_components[component_type][name] = component
        merged["components"] = merged_components

    # Merge tags
    if "tags" in overlay_spec:
        existing_tags = {t.get("name") for t in merged.get("tags", [])}
        merged_tags = list(merged.get("tags", []))
        for tag in overlay_spec["tags"]:
            if tag.get("name") not in existing_tags:
                merged_tags.append(tag)
        merged["tags"] = merged_tags

    return merged


def resolve_references(
    spec_data: dict[str, Any],
    max_depth: int = 10
) -> dict[str, Any]:
    """
    Resolve internal $ref references in a specification.

    Args:
        spec_data: Specification with references.
        max_depth: Maximum resolution depth to prevent infinite loops.

    Returns:
        Specification with resolved references.
    """
    def get_ref_value(ref: str, root: dict[str, Any]) -> Optional[Any]:
        """Get the value at a $ref path."""
        if not ref.startswith("#/"):
            return None

        parts = ref[2:].split("/")
        current = root
        for part in parts:
            part = part.replace("~1", "/").replace("~0", "~")
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    def resolve_refs(obj: Any, root: dict[str, Any], depth: int = 0) -> Any:
        """Recursively resolve references."""
        if depth > max_depth:
            return obj

        if isinstance(obj, dict):
            if "$ref" in obj and len(obj) == 1:
                ref_value = get_ref_value(obj["$ref"], root)
                if ref_value is not None:
                    return resolve_refs(ref_value, root, depth + 1)
            return {k: resolve_refs(v, root, depth) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [resolve_refs(item, root, depth) for item in obj]
        return obj

    return cast(dict[str, Any], resolve_refs(spec_data, spec_data))


def validate_url(url: str) -> bool:
    """
    Validate a URL string.

    Args:
        url: URL string to validate.

    Returns:
        True if valid, False otherwise.
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc]) or url.startswith("/")
    except Exception:
        return False


def extract_ref_name(ref: str) -> Optional[str]:
    """
    Extract the component name from a $ref string.

    Args:
        ref: Reference string (e.g., "#/components/schemas/User").

    Returns:
        Component name or None if invalid.
    """
    if not ref.startswith("#/"):
        return None

    parts = ref.split("/")
    if len(parts) >= 2:
        return parts[-1]
    return None


def get_all_refs(spec_data: dict[str, Any]) -> set[str]:
    """
    Get all $ref values in a specification.

    Args:
        spec_data: Specification data.

    Returns:
        Set of all reference strings.
    """
    refs: set[str] = set()

    def collect_refs(obj: Any) -> None:
        if isinstance(obj, dict):
            if "$ref" in obj:
                refs.add(obj["$ref"])
            for value in obj.values():
                collect_refs(value)
        elif isinstance(obj, list):
            for item in obj:
                collect_refs(item)

    collect_refs(spec_data)
    return refs


def find_unused_schemas(spec_data: dict[str, Any]) -> list[str]:
    """
    Find schemas that are defined but never referenced.

    Args:
        spec_data: Specification data.

    Returns:
        List of unused schema names.
    """
    refs = get_all_refs(spec_data)
    schemas = spec_data.get("components", {}).get("schemas", {})

    unused = []
    for name in schemas.keys():
        ref_path = f"#/components/schemas/{name}"
        if ref_path not in refs:
            unused.append(name)

    return unused


def count_operations(spec_data: dict[str, Any]) -> dict[str, int]:
    """
    Count operations by HTTP method.

    Args:
        spec_data: Specification data.

    Returns:
        Dictionary mapping method to count.
    """
    counts: dict[str, int] = {}
    methods = ["get", "put", "post", "delete", "options", "head", "patch", "trace"]

    for path_item in spec_data.get("paths", {}).values():
        if isinstance(path_item, dict):
            for method in methods:
                if method in path_item:
                    counts[method.upper()] = counts.get(method.upper(), 0) + 1

    return counts
