"""
JSONSchema Utilities - Helper functions for JSON Schema handling.
"""

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]


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
            # Try JSON first, then YAML
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
            # Deep merge dictionaries
            result[key] = merge_schemas(result[key], value, deep=True)
        elif key in result and isinstance(result[key], list) and isinstance(value, list):
            # Extend lists
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

    # Get definitions from schema or external
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
        # Handle $ref
        if "$ref" in obj:
            ref = obj["$ref"]
            resolved = _resolve_ref(ref, definitions)
            if resolved:
                # Merge with any additional properties
                base = _resolve_refs_recursive(resolved, definitions, depth - 1)
                extra = {k: v for k, v in obj.items() if k != "$ref"}
                if extra:
                    return merge_schemas(base, extra)
                return base
            return obj

        # Recursively resolve other properties
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
        # External ref - not supported
        return None

    # Parse JSON pointer
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


def validate_schema_syntax(schema: dict[str, Any]) -> list[str]:
    """
    Validate JSON Schema syntax.

    Args:
        schema: Schema to validate.

    Returns:
        List of syntax errors (empty if valid).
    """
    errors: list[str] = []

    # Check for $schema
    if "$schema" not in schema:
        errors.append("Missing $schema declaration")

    # Check type is valid
    valid_types = {"string", "number", "integer", "boolean", "array", "object", "null"}
    if "type" in schema:
        schema_type = schema["type"]
        if isinstance(schema_type, str):
            if schema_type not in valid_types:
                errors.append(f"Invalid type: {schema_type}")
        elif isinstance(schema_type, list):
            for t in schema_type:
                if t not in valid_types:
                    errors.append(f"Invalid type in array: {t}")

    # Check properties structure
    if "properties" in schema:
        if not isinstance(schema["properties"], dict):
            errors.append("'properties' must be an object")
        else:
            for prop_name, prop_schema in schema["properties"].items():
                if not isinstance(prop_schema, (dict, bool)):
                    errors.append(f"Property '{prop_name}' schema must be object or boolean")

    # Check required is array
    if "required" in schema:
        if not isinstance(schema["required"], list):
            errors.append("'required' must be an array")
        else:
            for item in schema["required"]:
                if not isinstance(item, str):
                    errors.append("'required' items must be strings")

    # Check items structure
    if "items" in schema:
        if not isinstance(schema["items"], (dict, list, bool)):
            errors.append("'items' must be object, array, or boolean")

    # Check enum is array
    if "enum" in schema:
        if not isinstance(schema["enum"], list):
            errors.append("'enum' must be an array")
        elif len(schema["enum"]) == 0:
            errors.append("'enum' must have at least one value")

    # Check numeric constraints
    for constraint in ["minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf"]:
        if constraint in schema:
            if not isinstance(schema[constraint], (int, float)):
                errors.append(f"'{constraint}' must be a number")

    # Check string constraints
    for constraint in ["minLength", "maxLength"]:
        if constraint in schema:
            if not isinstance(schema[constraint], int) or schema[constraint] < 0:
                errors.append(f"'{constraint}' must be a non-negative integer")

    # Check array constraints
    for constraint in ["minItems", "maxItems"]:
        if constraint in schema:
            if not isinstance(schema[constraint], int) or schema[constraint] < 0:
                errors.append(f"'{constraint}' must be a non-negative integer")

    # Check pattern is valid regex
    if "pattern" in schema:
        try:
            re.compile(schema["pattern"])
        except re.error as e:
            errors.append(f"Invalid regex pattern: {e}")

    # Recursively check nested schemas
    for key in ["properties", "definitions", "$defs"]:
        if key in schema and isinstance(schema[key], dict):
            for name, sub_schema in schema[key].items():
                if isinstance(sub_schema, dict):
                    sub_errors = validate_schema_syntax(sub_schema)
                    for error in sub_errors:
                        errors.append(f"{key}/{name}: {error}")

    if "items" in schema and isinstance(schema["items"], dict):
        sub_errors = validate_schema_syntax(schema["items"])
        for error in sub_errors:
            errors.append(f"items: {error}")

    for combiner in ["allOf", "anyOf", "oneOf"]:
        if combiner in schema and isinstance(schema[combiner], list):
            for i, sub_schema in enumerate(schema[combiner]):
                if isinstance(sub_schema, dict):
                    sub_errors = validate_schema_syntax(sub_schema)
                    for error in sub_errors:
                        errors.append(f"{combiner}[{i}]: {error}")

    return errors


def schema_to_typescript(schema: dict[str, Any], name: str = "Schema") -> str:
    """
    Convert JSON Schema to TypeScript interface.

    Args:
        schema: JSON Schema dictionary.
        name: Name for the TypeScript interface.

    Returns:
        TypeScript interface string.
    """
    lines = []
    lines.append(f"interface {name} {{")

    if "properties" in schema:
        required = set(schema.get("required", []))
        for prop_name, prop_schema in schema["properties"].items():
            ts_type = _json_type_to_typescript(prop_schema)
            optional = "" if prop_name in required else "?"
            lines.append(f"  {prop_name}{optional}: {ts_type};")

    lines.append("}")
    return "\n".join(lines)


def _json_type_to_typescript(schema: dict[str, Any]) -> str:
    """Convert JSON Schema type to TypeScript type."""
    if isinstance(schema, bool):
        return "any" if schema else "never"

    if "$ref" in schema:
        # Extract type name from reference
        ref = cast(str, schema["$ref"])
        if ref.startswith("#/definitions/") or ref.startswith("#/$defs/"):
            return ref.split("/")[-1]
        return "any"

    if "enum" in schema:
        values = schema["enum"]
        return " | ".join(
            f'"{v}"' if isinstance(v, str) else str(v)
            for v in values
        )

    if "const" in schema:
        v = schema["const"]
        return f'"{v}"' if isinstance(v, str) else str(v)

    schema_type = schema.get("type")

    if isinstance(schema_type, list):
        types = [_json_type_to_typescript({"type": t}) for t in schema_type]
        return " | ".join(types)

    type_mapping = {
        "string": "string",
        "number": "number",
        "integer": "number",
        "boolean": "boolean",
        "null": "null",
    }

    if schema_type in type_mapping:
        return type_mapping[schema_type]

    if schema_type == "array":
        if "items" in schema:
            item_type = _json_type_to_typescript(schema["items"])
            return f"{item_type}[]"
        return "any[]"

    if schema_type == "object":
        if "properties" in schema:
            # Would need recursion for nested interfaces
            return "object"
        if "additionalProperties" in schema:
            if isinstance(schema["additionalProperties"], dict):
                value_type = _json_type_to_typescript(schema["additionalProperties"])
                return f"Record<string, {value_type}>"
        return "Record<string, any>"

    # Combiners
    if "anyOf" in schema:
        types = [_json_type_to_typescript(s) for s in schema["anyOf"]]
        return " | ".join(types)

    if "oneOf" in schema:
        types = [_json_type_to_typescript(s) for s in schema["oneOf"]]
        return " | ".join(types)

    if "allOf" in schema:
        types = [_json_type_to_typescript(s) for s in schema["allOf"]]
        return " & ".join(types)

    return "any"


def get_schema_complexity(schema: dict[str, Any]) -> dict[str, int]:
    """
    Calculate complexity metrics for a schema.

    Args:
        schema: JSON Schema dictionary.

    Returns:
        Dictionary with complexity metrics.
    """
    metrics = {
        "total_properties": 0,
        "required_properties": 0,
        "nested_depth": 0,
        "definitions_count": 0,
        "ref_count": 0,
    }

    def analyze(obj: Any, depth: int = 0) -> None:
        if not isinstance(obj, dict):
            return

        metrics["nested_depth"] = max(metrics["nested_depth"], depth)

        if "$ref" in obj:
            metrics["ref_count"] += 1

        if "properties" in obj:
            metrics["total_properties"] += len(obj["properties"])
            for prop_schema in obj["properties"].values():
                analyze(prop_schema, depth + 1)

        if "required" in obj:
            metrics["required_properties"] += len(obj["required"])

        for key in ["definitions", "$defs"]:
            if key in obj:
                metrics["definitions_count"] += len(obj[key])
                for def_schema in obj[key].values():
                    analyze(def_schema, depth)

        if "items" in obj and isinstance(obj["items"], dict):
            analyze(obj["items"], depth + 1)

        for combiner in ["allOf", "anyOf", "oneOf"]:
            if combiner in obj:
                for sub_schema in obj[combiner]:
                    analyze(sub_schema, depth + 1)

    analyze(schema)
    return metrics
