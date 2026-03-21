"""
JSONSchema Utilities - Helper functions for JSON Schema handling.
"""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]

from Asgard.Forseti.JSONSchema.utilities._jsonschema_validation_utils import (
    get_schema_complexity,
    schema_to_typescript,
    validate_schema_syntax,
)


def load_schema_file(file_path: Path) -> dict[str, Any]:
    """
    Load a JSON Schema file.

    Supports JSON and YAML formats.

    Args:
        file_path: Path to the schema file.

    Returns:
        Parsed schema as a dictionary.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is not supported.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Schema file not found: {file_path}")

    content = file_path.read_text(encoding="utf-8")
    suffix = file_path.suffix.lower()

    try:
        if suffix == ".json":
            return cast(dict[str, Any], json.loads(content))
        elif suffix in [".yaml", ".yml"]:
            return cast(dict[str, Any], yaml.safe_load(content))
        else:
            try:
                return cast(dict[str, Any], json.loads(content))
            except json.JSONDecodeError:
                return cast(dict[str, Any], yaml.safe_load(content))
    except Exception as e:
        raise ValueError(f"Failed to parse schema file: {e}")


def save_schema_file(file_path: Path, schema: dict[str, Any]) -> None:
    """
    Save a JSON Schema to a file.

    Args:
        file_path: Path to save the schema.
        schema: Schema dictionary to save.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = file_path.suffix.lower()

    if suffix in [".yaml", ".yml"]:
        content = yaml.dump(schema, default_flow_style=False, sort_keys=False)
    else:
        content = json.dumps(schema, indent=2)

    file_path.write_text(content, encoding="utf-8")


def merge_schemas(
    base_schema: dict[str, Any],
    overlay_schema: dict[str, Any],
    deep: bool = True
) -> dict[str, Any]:
    """
    Merge two JSON Schemas.

    Args:
        base_schema: Base schema to merge into.
        overlay_schema: Schema to overlay on base.
        deep: Whether to deep merge nested objects.

    Returns:
        Merged schema.
    """
    if not deep:
        result = dict(base_schema)
        result.update(overlay_schema)
        return result

    result = deepcopy(base_schema)

    for key, value in overlay_schema.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_schemas(result[key], value, deep=True)
        elif key in result and isinstance(result[key], list) and isinstance(value, list):
            result[key] = result[key] + value
        else:
            result[key] = deepcopy(value)

    return result


def resolve_refs(
    schema: dict[str, Any],
    definitions: dict[str, Any] | None = None,
    max_depth: int = 100
) -> dict[str, Any]:
    """
    Resolve $ref references in a schema.

    Args:
        schema: Schema with references.
        definitions: Optional external definitions.
        max_depth: Maximum recursion depth.

    Returns:
        Schema with resolved references.
    """
    if max_depth <= 0:
        return schema

    defs = definitions or {}
    if "definitions" in schema:
        defs = {**defs, **schema["definitions"]}
    if "$defs" in schema:
        defs = {**defs, **schema["$defs"]}

    return cast(dict[str, Any], _resolve_refs_recursive(schema, defs, max_depth))


def _resolve_refs_recursive(
    obj: Any,
    definitions: dict[str, Any],
    depth: int
) -> Any:
    """Recursively resolve references."""
    if depth <= 0:
        return obj

    if isinstance(obj, dict):
        if "$ref" in obj:
            ref = obj["$ref"]
            resolved = _resolve_ref(ref, definitions)
            if resolved:
                base = _resolve_refs_recursive(resolved, definitions, depth - 1)
                extra = {k: v for k, v in obj.items() if k != "$ref"}
                if extra:
                    return merge_schemas(base, extra)
                return base
            return obj

        return {
            k: _resolve_refs_recursive(v, definitions, depth)
            for k, v in obj.items()
        }

    if isinstance(obj, list):
        return [_resolve_refs_recursive(item, definitions, depth) for item in obj]

    return obj


def _resolve_ref(ref: str, definitions: dict[str, Any]) -> dict[str, Any] | None:
    """Resolve a single $ref."""
    if not ref.startswith("#/"):
        return None

    parts = ref[2:].split("/")

    current: Any = {"definitions": definitions, "$defs": definitions}
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None

    if isinstance(current, dict):
        return deepcopy(current)
    return None


__all__ = [
    "load_schema_file",
    "save_schema_file",
    "merge_schemas",
    "resolve_refs",
    "validate_schema_syntax",
    "schema_to_typescript",
    "get_schema_complexity",
]
