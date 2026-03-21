"""
GraphQL Schema Generator Helpers.

Helper functions for SchemaGeneratorService.
"""

import re
from typing import Any, Optional, cast

from Asgard.Forseti.GraphQL.models.graphql_models import (
    GraphQLField,
    GraphQLSchema,
    GraphQLType,
    GraphQLTypeKind,
)


TYPE_MAP: dict[str, str] = {
    "str": "String",
    "int": "Int",
    "float": "Float",
    "bool": "Boolean",
    "list": "[String]",
    "dict": "JSON",
    "datetime": "DateTime",
    "date": "Date",
    "uuid": "ID",
    "UUID": "ID",
}


def field_to_sdl(field: GraphQLField) -> str:
    """Convert a GraphQL field to SDL."""
    args_str = ""
    if field.arguments:
        args = []
        for arg in field.arguments:
            arg_str = f"{arg.name}: {arg.type_name}"
            if arg.default_value is not None:
                arg_str += f" = {arg.default_value}"
            args.append(arg_str)
        args_str = f"({', '.join(args)})"

    field_def = f"{field.name}{args_str}: {field.type_name}"

    if field.is_deprecated:
        reason = field.deprecation_reason or ""
        if reason:
            field_def += f' @deprecated(reason: "{reason}")'
        else:
            field_def += " @deprecated"

    return field_def


def type_to_sdl(gql_type: GraphQLType) -> str:
    """Convert a GraphQL type to SDL."""
    lines = []

    if gql_type.description:
        lines.append('"""')
        lines.append(gql_type.description)
        lines.append('"""')

    kind_keyword = {
        GraphQLTypeKind.OBJECT: "type",
        GraphQLTypeKind.INTERFACE: "interface",
        GraphQLTypeKind.INPUT_OBJECT: "input",
        GraphQLTypeKind.ENUM: "enum",
        GraphQLTypeKind.UNION: "union",
        GraphQLTypeKind.SCALAR: "scalar",
    }.get(gql_type.kind, "type")

    if gql_type.kind == GraphQLTypeKind.SCALAR:
        lines.append(f"scalar {gql_type.name}")
        return "\n".join(lines)

    if gql_type.kind == GraphQLTypeKind.ENUM:
        lines.append(f"enum {gql_type.name} {{")
        for value in gql_type.enum_values:
            lines.append(f"  {value}")
        lines.append("}")
        return "\n".join(lines)

    if gql_type.kind == GraphQLTypeKind.UNION:
        types_str = " | ".join(gql_type.possible_types)
        lines.append(f"union {gql_type.name} = {types_str}")
        return "\n".join(lines)

    implements = ""
    if gql_type.interfaces:
        implements = " implements " + " & ".join(gql_type.interfaces)

    lines.append(f"{kind_keyword} {gql_type.name}{implements} {{")

    fields = gql_type.input_fields if gql_type.kind == GraphQLTypeKind.INPUT_OBJECT else gql_type.fields
    for field in fields:
        lines.append(f"  {field_to_sdl(field)}")

    lines.append("}")
    return "\n".join(lines)


def schema_to_sdl(schema: GraphQLSchema) -> str:
    """Convert a GraphQL schema to SDL."""
    lines = []

    used_types: set[str] = set()
    for gql_type in schema.types:
        for field in gql_type.fields:
            base_type = field.type_name.replace("[", "").replace("]", "").replace("!", "")
            used_types.add(base_type)

    custom_scalars = used_types - {"String", "Int", "Float", "Boolean", "ID"}
    custom_scalars -= {t.name for t in schema.types}
    for scalar in sorted(custom_scalars):
        lines.append(f"scalar {scalar}")
    if custom_scalars:
        lines.append("")

    for gql_type in schema.types:
        lines.append(type_to_sdl(gql_type))
        lines.append("")

    return "\n".join(lines)


def openapi_type_to_graphql(schema: dict[str, Any], recurse_fn: Any) -> str:
    """Convert an OpenAPI type to a GraphQL type."""
    if "$ref" in schema:
        ref = cast(str, schema["$ref"])
        return ref.split("/")[-1]

    schema_type = schema.get("type", "string")
    schema_format = schema.get("format")

    type_map = {
        "string": "String",
        "integer": "Int",
        "number": "Float",
        "boolean": "Boolean",
        "array": "[String]",
        "object": "JSON",
    }

    if schema_format == "uuid":
        return "ID"
    elif schema_format in ["date", "date-time"]:
        return "DateTime"

    if schema_type == "array" and "items" in schema:
        item_type = recurse_fn(schema["items"])
        return f"[{item_type}]"

    return type_map.get(schema_type, "String")


def openapi_schema_to_type(
    name: str,
    schema: dict[str, Any],
    openapi_type_fn: Any,
) -> Optional[GraphQLType]:
    """Convert an OpenAPI schema to a GraphQL type."""
    fields: list[GraphQLField] = []
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    for prop_name, prop_schema in properties.items():
        type_name = openapi_type_fn(prop_schema)
        if prop_name in required:
            type_name = f"{type_name}!"

        fields.append(GraphQLField(
            name=prop_name,
            type_name=type_name,
            description=prop_schema.get("description"),
        ))

    if not fields:
        return None

    return GraphQLType(
        name=name,
        kind=GraphQLTypeKind.OBJECT,
        description=schema.get("description"),
        fields=fields,
    )


def openapi_operation_to_field(
    path: str,
    method: str,
    operation: dict[str, Any],
    openapi_type_fn: Any,
) -> Optional[GraphQLField]:
    """Convert an OpenAPI operation to a GraphQL field."""
    operation_id = operation.get("operationId")
    if not operation_id:
        operation_id = method + re.sub(r'[^a-zA-Z0-9]', '_', path).title().replace("_", "")

    responses = operation.get("responses", {})
    return_type = "Boolean"
    for status in ["200", "201", "default"]:
        if status in responses:
            response = responses[status]
            content = response.get("content", {})
            if "application/json" in content:
                schema = content["application/json"].get("schema", {})
                return_type = openapi_type_fn(schema)
            break

    return GraphQLField(
        name=operation_id,
        type_name=return_type,
        description=operation.get("summary") or operation.get("description"),
    )
