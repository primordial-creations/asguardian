"""
OpenAPI Spec Utilities - Reference resolution, merging, and comparison helpers.
"""

from pathlib import Path
from typing import Any, Optional, cast

from Asgard.Forseti.OpenAPI.utilities._openapi_io_utils import load_spec_file


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
        if not ref.startswith("#/"):
            return None

        parts = ref[2:].split("/")
        current: Any = root
        for part in parts:
            part = part.replace("~1", "/").replace("~0", "~")
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    def resolve_refs(obj: Any, root: dict[str, Any], depth: int = 0) -> Any:
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

    if "info" in overlay_spec:
        merged["info"] = {**merged.get("info", {}), **overlay_spec["info"]}

    if "servers" in overlay_spec:
        if conflict_strategy == "overlay":
            merged["servers"] = overlay_spec["servers"]
        else:
            merged["servers"] = merged.get("servers", []) + overlay_spec["servers"]

    if "paths" in overlay_spec:
        merged_paths = dict(merged.get("paths", {}))
        for path, path_item in overlay_spec["paths"].items():
            if path in merged_paths:
                if conflict_strategy == "error":
                    raise ValueError(f"Path conflict: {path}")
                elif conflict_strategy == "overlay":
                    merged_paths[path] = {**merged_paths[path], **path_item}
            else:
                merged_paths[path] = path_item
        merged["paths"] = merged_paths

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

    if "tags" in overlay_spec:
        existing_tags = {t.get("name") for t in merged.get("tags", [])}
        merged_tags = list(merged.get("tags", []))
        for tag in overlay_spec["tags"]:
            if tag.get("name") not in existing_tags:
                merged_tags.append(tag)
        merged["tags"] = merged_tags

    return merged


def compare_specs(
    spec1_path: str | Path,
    spec2_path: str | Path,
) -> dict[str, Any]:
    """
    Compare two OpenAPI specifications and return a diff summary.

    Args:
        spec1_path: Path to the first (base) specification file.
        spec2_path: Path to the second (target) specification file.

    Returns:
        Dictionary containing added, removed, and modified paths and schemas.
    """
    spec1 = load_spec_file(Path(spec1_path))
    spec2 = load_spec_file(Path(spec2_path))

    paths1: set[str] = set(spec1.get("paths", {}).keys())
    paths2: set[str] = set(spec2.get("paths", {}).keys())

    schemas1: set[str] = set(
        spec1.get("components", {}).get("schemas", {}).keys()
    )
    schemas2: set[str] = set(
        spec2.get("components", {}).get("schemas", {}).keys()
    )

    modified_paths: list[str] = []
    for path in paths1 & paths2:
        if spec1["paths"][path] != spec2["paths"][path]:
            modified_paths.append(path)

    return {
        "paths": {
            "added": sorted(paths2 - paths1),
            "removed": sorted(paths1 - paths2),
            "modified": sorted(modified_paths),
        },
        "schemas": {
            "added": sorted(schemas2 - schemas1),
            "removed": sorted(schemas1 - schemas2),
        },
        "summary": {
            "paths_added": len(paths2 - paths1),
            "paths_removed": len(paths1 - paths2),
            "paths_modified": len(modified_paths),
            "schemas_added": len(schemas2 - schemas1),
            "schemas_removed": len(schemas1 - schemas2),
        },
    }
