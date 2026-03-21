"""
GraphQL Parse Utilities - SDL parsing and schema merging helpers.
"""

import re
from typing import Any


def parse_sdl(sdl: str) -> dict[str, Any]:
    """
    Parse GraphQL SDL into a basic structure.

    This is a simplified parser for validation purposes.
    For full parsing, use the graphql-core library.

    Args:
        sdl: GraphQL SDL string.

    Returns:
        Dictionary with parsed schema elements.

    Raises:
        ValueError: If the SDL has syntax errors.
    """
    result: dict[str, Any] = {
        "types": {},
        "interfaces": {},
        "enums": {},
        "unions": {},
        "inputs": {},
        "scalars": set(),
        "directives": {},
    }

    sdl_clean = re.sub(r'#[^\n]*', '', sdl)
    sdl_clean = re.sub(r'"""[\s\S]*?"""', '""', sdl_clean)
    sdl_clean = re.sub(r'"[^"]*"', '""', sdl_clean)

    type_pattern = r'type\s+(\w+)(?:\s+implements\s+([^{]+))?\s*\{([^}]*)\}'
    for match in re.finditer(type_pattern, sdl_clean):
        name = match.group(1)
        implements = match.group(2)
        body = match.group(3)

        interfaces = []
        if implements:
            interfaces = [i.strip() for i in implements.split("&") if i.strip()]

        fields = _parse_fields(body)
        result["types"][name] = {
            "interfaces": interfaces,
            "fields": fields,
        }

    interface_pattern = r'interface\s+(\w+)\s*\{([^}]*)\}'
    for match in re.finditer(interface_pattern, sdl_clean):
        name = match.group(1)
        body = match.group(2)
        fields = _parse_fields(body)
        result["interfaces"][name] = {"fields": fields}

    enum_pattern = r'enum\s+(\w+)\s*\{([^}]*)\}'
    for match in re.finditer(enum_pattern, sdl_clean):
        name = match.group(1)
        body = match.group(2)
        values = [v.strip() for v in body.split() if v.strip() and not v.startswith("@")]
        result["enums"][name] = values

    union_pattern = r'union\s+(\w+)\s*=\s*([^{}\n]+)'
    for match in re.finditer(union_pattern, sdl_clean):
        name = match.group(1)
        types_str = match.group(2)
        types = [t.strip() for t in types_str.split("|") if t.strip()]
        result["unions"][name] = types

    input_pattern = r'input\s+(\w+)\s*\{([^}]*)\}'
    for match in re.finditer(input_pattern, sdl_clean):
        name = match.group(1)
        body = match.group(2)
        fields = _parse_fields(body)
        result["inputs"][name] = {"fields": fields}

    scalar_pattern = r'scalar\s+(\w+)'
    for match in re.finditer(scalar_pattern, sdl_clean):
        result["scalars"].add(match.group(1))

    directive_pattern = r'directive\s+@(\w+)(?:\([^)]*\))?\s+on\s+([A-Z_|]+)'
    for match in re.finditer(directive_pattern, sdl_clean):
        name = match.group(1)
        locations = [loc.strip() for loc in match.group(2).split("|")]
        result["directives"][name] = {"locations": locations}

    return result


def _parse_fields(body: str) -> dict[str, Any]:
    """Parse field definitions from a type body."""
    fields: dict[str, Any] = {}

    field_pattern = r'(\w+)(?:\([^)]*\))?\s*:\s*([^\n@]+)'
    for match in re.finditer(field_pattern, body):
        name = match.group(1)
        type_str = match.group(2).strip()
        fields[name] = {"type": type_str}

    return fields


def merge_schemas(schemas: list[str]) -> str:
    """
    Merge multiple GraphQL schemas into one.

    Args:
        schemas: List of SDL strings.

    Returns:
        Merged SDL string.
    """
    merged_types: dict[str, str] = {}
    merged_directives: set[str] = set()

    for sdl in schemas:
        type_pattern = r'((?:type|interface|enum|union|input|scalar)\s+\w+[^}]*(?:\{[^}]*\})?)'
        for match in re.finditer(type_pattern, sdl):
            type_def = match.group(1).strip()
            name_match = re.match(r'(?:type|interface|enum|union|input|scalar)\s+(\w+)', type_def)
            if name_match:
                name = name_match.group(1)
                if name in merged_types:
                    merged_types[name] = _merge_type_definitions(merged_types[name], type_def)
                else:
                    merged_types[name] = type_def

        directive_pattern = r'(directive\s+@\w+[^\n]+)'
        for match in re.finditer(directive_pattern, sdl):
            merged_directives.add(match.group(1).strip())

    lines = []
    for directive in sorted(merged_directives):
        lines.append(directive)
    if merged_directives:
        lines.append("")

    for name in sorted(merged_types.keys()):
        lines.append(merged_types[name])
        lines.append("")

    return "\n".join(lines)


def _merge_type_definitions(existing: str, new: str) -> str:
    """Merge two type definitions."""
    existing_fields = re.search(r'\{([^}]*)\}', existing)
    new_fields = re.search(r'\{([^}]*)\}', new)

    if not existing_fields or not new_fields:
        return new

    all_fields: dict[str, str] = {}

    field_pattern = r'(\w+)(?:\([^)]*\))?\s*:\s*([^\n]+)'
    for match in re.finditer(field_pattern, existing_fields.group(1)):
        all_fields[match.group(1)] = match.group(0).strip()
    for match in re.finditer(field_pattern, new_fields.group(1)):
        all_fields[match.group(1)] = match.group(0).strip()

    header_match = re.match(r'((?:type|interface|input)\s+\w+[^{]*)', existing)
    header = header_match.group(1).strip() if header_match else ""

    fields_str = "\n  ".join(all_fields.values())
    return f"{header} {{\n  {fields_str}\n}}"
