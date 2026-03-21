"""
GraphQL Utilities - Helper functions for GraphQL schema handling.
"""

import re
from pathlib import Path
from typing import Any

from Asgard.Forseti.GraphQL.models.graphql_models import GraphQLSchema, GraphQLType, GraphQLTypeKind
from Asgard.Forseti.GraphQL.utilities._graphql_parse_utils import (
    merge_schemas,
    parse_sdl,
)


# Built-in scalar types
BUILTIN_SCALARS = {"String", "Int", "Float", "Boolean", "ID"}

# Built-in directives
BUILTIN_DIRECTIVES = {"skip", "include", "deprecated", "specifiedBy"}


def load_schema_file(file_path: Path) -> str:
    """
    Load a GraphQL schema from a file.

    Args:
        file_path: Path to the schema file.

    Returns:
        Schema SDL string.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Schema file not found: {file_path}")

    return file_path.read_text(encoding="utf-8")


def save_schema_file(file_path: Path, sdl: str) -> None:
    """
    Save a GraphQL schema to a file.

    Args:
        file_path: Path to save the schema.
        sdl: Schema SDL string.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(sdl, encoding="utf-8")


def validate_type_name(name: str) -> bool:
    """
    Validate a GraphQL type name.

    Args:
        name: Type name to validate.

    Returns:
        True if valid, False otherwise.
    """
    if not re.match(r'^[_A-Za-z][_0-9A-Za-z]*$', name):
        return False

    if name.startswith("__"):
        return False

    return True


def is_builtin_type(name: str) -> bool:
    """
    Check if a type name is a built-in scalar.

    Args:
        name: Type name to check.

    Returns:
        True if built-in, False otherwise.
    """
    clean_name = name.replace("!", "").replace("[", "").replace("]", "").strip()
    return clean_name in BUILTIN_SCALARS


def extract_base_type(type_ref: str) -> str:
    """
    Extract the base type name from a type reference.

    Args:
        type_ref: Type reference (e.g., "[User!]!").

    Returns:
        Base type name (e.g., "User").
    """
    return type_ref.replace("!", "").replace("[", "").replace("]", "").strip()


def format_type_ref(
    base_type: str,
    is_list: bool = False,
    is_non_null: bool = False,
    is_item_non_null: bool = False
) -> str:
    """
    Format a type reference string.

    Args:
        base_type: Base type name.
        is_list: Whether it's a list type.
        is_non_null: Whether the type is non-null.
        is_item_non_null: Whether list items are non-null.

    Returns:
        Formatted type reference.
    """
    result = base_type
    if is_list:
        if is_item_non_null:
            result = f"[{result}!]"
        else:
            result = f"[{result}]"
    if is_non_null:
        result = f"{result}!"
    return result


def get_all_type_references(sdl: str) -> set[str]:
    """
    Get all type references in a schema.

    Args:
        sdl: GraphQL SDL string.

    Returns:
        Set of referenced type names.
    """
    refs: set[str] = set()

    type_ref_pattern = r':\s*\[?\s*(\w+)[\]!]*'
    for match in re.finditer(type_ref_pattern, sdl):
        refs.add(match.group(1))

    implements_pattern = r'implements\s+([A-Za-z_&\s]+)\s*\{'
    for match in re.finditer(implements_pattern, sdl):
        interfaces = match.group(1).split("&")
        for interface in interfaces:
            refs.add(interface.strip())

    union_pattern = r'union\s+\w+\s*=\s*([^{}\n]+)'
    for match in re.finditer(union_pattern, sdl):
        members = match.group(1).split("|")
        for member in members:
            refs.add(member.strip())

    return refs


def count_fields(sdl: str) -> int:
    """
    Count the number of fields in a schema.

    Args:
        sdl: GraphQL SDL string.

    Returns:
        Number of fields.
    """
    clean = re.sub(r'#[^\n]*', '', sdl)
    clean = re.sub(r'"""[\s\S]*?"""', '', clean)
    clean = re.sub(r'"[^"]*"', '', clean)

    field_pattern = r'^\s+\w+\s*[:(]'
    return len(re.findall(field_pattern, clean, re.MULTILINE))


__all__ = [
    "BUILTIN_DIRECTIVES",
    "BUILTIN_SCALARS",
    "count_fields",
    "extract_base_type",
    "format_type_ref",
    "get_all_type_references",
    "is_builtin_type",
    "load_schema_file",
    "merge_schemas",
    "parse_sdl",
    "save_schema_file",
    "validate_type_name",
]
