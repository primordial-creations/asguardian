"""
Contract Utilities - Helper functions for API contract handling.
"""

import json
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]


def load_contract_file(file_path: Path) -> dict[str, Any]:
    """
    Load a contract/specification file.

    Supports JSON and YAML formats.

    Args:
        file_path: Path to the contract file.

    Returns:
        Parsed contract as a dictionary.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is not supported.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Contract file not found: {file_path}")

    content = file_path.read_text(encoding="utf-8")
    suffix = file_path.suffix.lower()

    try:
        if suffix == ".json":
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
        raise ValueError(f"Failed to parse contract file: {e}")


def save_contract_file(file_path: Path, contract: dict[str, Any]) -> None:
    """
    Save a contract to a file.

    Args:
        file_path: Path to save the contract.
        contract: Contract data to save.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = file_path.suffix.lower()

    if suffix == ".json":
        content = json.dumps(contract, indent=2)
    else:
        content = yaml.dump(contract, default_flow_style=False, sort_keys=False)

    file_path.write_text(content, encoding="utf-8")


def normalize_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize a specification for comparison.

    Args:
        spec: Specification dictionary.

    Returns:
        Normalized specification.
    """
    normalized = dict(spec)

    # Remove metadata that doesn't affect compatibility
    keys_to_remove = ["info", "externalDocs", "tags"]
    for key in keys_to_remove:
        normalized.pop(key, None)

    return normalized


def compare_schemas(
    old_schema: dict[str, Any],
    new_schema: dict[str, Any]
) -> dict[str, Any]:
    """
    Compare two schemas and return differences.

    Args:
        old_schema: Old schema dictionary.
        new_schema: New schema dictionary.

    Returns:
        Dictionary with differences.
    """
    differences: dict[str, list] = {
        "added_properties": [],
        "removed_properties": [],
        "modified_properties": [],
        "type_changes": [],
    }

    old_props = old_schema.get("properties", {})
    new_props = new_schema.get("properties", {})
    old_required = set(old_schema.get("required", []))
    new_required = set(new_schema.get("required", []))

    # Find added properties
    for prop in new_props:
        if prop not in old_props:
            differences["added_properties"].append({
                "name": prop,
                "required": prop in new_required,
            })

    # Find removed properties
    for prop in old_props:
        if prop not in new_props:
            differences["removed_properties"].append({
                "name": prop,
                "was_required": prop in old_required,
            })

    # Find modified properties
    for prop in old_props:
        if prop in new_props:
            old_prop = old_props[prop]
            new_prop = new_props[prop]

            changes = {}

            # Type change
            if old_prop.get("type") != new_prop.get("type"):
                changes["type"] = {
                    "old": old_prop.get("type"),
                    "new": new_prop.get("type"),
                }
                differences["type_changes"].append({
                    "property": prop,
                    "old_type": old_prop.get("type"),
                    "new_type": new_prop.get("type"),
                })

            # Required change
            was_required = prop in old_required
            is_required = prop in new_required
            if was_required != is_required:
                changes["required"] = {
                    "old": was_required,
                    "new": is_required,
                }

            if changes:
                differences["modified_properties"].append({
                    "name": prop,
                    "changes": changes,
                })

    return differences


def is_breaking_change(
    old_schema: dict[str, Any],
    new_schema: dict[str, Any]
) -> bool:
    """
    Check if schema changes are breaking.

    Args:
        old_schema: Old schema dictionary.
        new_schema: New schema dictionary.

    Returns:
        True if there are breaking changes.
    """
    differences = compare_schemas(old_schema, new_schema)

    # Removed properties are breaking
    if differences["removed_properties"]:
        return True

    # Type changes are breaking
    if differences["type_changes"]:
        return True

    # Making optional properties required is breaking
    for mod in differences["modified_properties"]:
        if "required" in mod.get("changes", {}):
            if mod["changes"]["required"]["new"] is True:
                return True

    # Adding required properties is breaking
    for added in differences["added_properties"]:
        if added.get("required"):
            return True

    return False


def extract_endpoints(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract all endpoints from a specification.

    Args:
        spec: OpenAPI specification.

    Returns:
        List of endpoint dictionaries.
    """
    endpoints = []
    paths = spec.get("paths", {})

    for path, path_item in paths.items():
        for method in ["get", "post", "put", "delete", "patch", "options", "head"]:
            if method in path_item:
                operation = path_item[method]
                endpoints.append({
                    "path": path,
                    "method": method.upper(),
                    "operationId": operation.get("operationId"),
                    "summary": operation.get("summary"),
                    "deprecated": operation.get("deprecated", False),
                })

    return endpoints


def get_schema_references(schema: dict[str, Any]) -> set[str]:
    """
    Get all schema references from a schema.

    Args:
        schema: Schema dictionary.

    Returns:
        Set of referenced schema names.
    """
    refs: set[str] = set()

    def collect_refs(obj: Any) -> None:
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref = obj["$ref"]
                if ref.startswith("#/components/schemas/"):
                    refs.add(ref.split("/")[-1])
            for value in obj.values():
                collect_refs(value)
        elif isinstance(obj, list):
            for item in obj:
                collect_refs(item)

    collect_refs(schema)
    return refs
