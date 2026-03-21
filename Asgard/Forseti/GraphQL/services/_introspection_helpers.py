"""
GraphQL Introspection Helpers.

Helper functions for IntrospectionService.
"""

from typing import Any, Callable, Optional, cast

from Asgard.Forseti.GraphQL.models.graphql_models import (
    GraphQLArgument,
    GraphQLDirective,
    GraphQLDirectiveLocation,
    GraphQLField,
    GraphQLSchema,
    GraphQLType,
    GraphQLTypeKind,
)


def format_type_ref(type_ref: dict[str, Any]) -> str:
    """Format a type reference as a string."""
    kind = type_ref.get("kind")
    name = type_ref.get("name")
    of_type = type_ref.get("ofType")

    if kind == "NON_NULL":
        inner = format_type_ref(of_type) if of_type else "Unknown"
        return f"{inner}!"
    elif kind == "LIST":
        inner = format_type_ref(of_type) if of_type else "Unknown"
        return f"[{inner}]"
    elif name:
        return cast(str, name)
    else:
        return "Unknown"


def parse_argument(arg_data: dict[str, Any]) -> Optional[GraphQLArgument]:
    """Parse an argument from introspection data."""
    name = arg_data.get("name")
    if not name:
        return None

    type_name = format_type_ref(arg_data.get("type", {}))
    is_required = type_name.endswith("!")

    return GraphQLArgument(
        name=name,
        type_name=type_name,
        description=arg_data.get("description"),
        default_value=arg_data.get("defaultValue"),
        is_required=is_required,
    )


def parse_field(field_data: dict[str, Any]) -> Optional[GraphQLField]:
    """Parse a field from introspection data."""
    name = field_data.get("name")
    if not name:
        return None

    type_name = format_type_ref(field_data.get("type", {}))

    arguments: list[GraphQLArgument] = []
    for arg_data in field_data.get("args") or []:
        arg = parse_argument(arg_data)
        if arg:
            arguments.append(arg)

    return GraphQLField(
        name=name,
        type_name=type_name,
        description=field_data.get("description"),
        arguments=arguments,
        is_deprecated=field_data.get("isDeprecated", False),
        deprecation_reason=field_data.get("deprecationReason"),
    )


def parse_input_field(field_data: dict[str, Any]) -> Optional[GraphQLField]:
    """Parse an input field from introspection data."""
    name = field_data.get("name")
    if not name:
        return None

    type_name = format_type_ref(field_data.get("type", {}))

    return GraphQLField(
        name=name,
        type_name=type_name,
        description=field_data.get("description"),
    )


def parse_type(type_data: dict[str, Any]) -> Optional[GraphQLType]:
    """Parse a type from introspection data."""
    name = type_data.get("name")
    if not name:
        return None

    kind_str = type_data.get("kind", "OBJECT")
    try:
        kind = GraphQLTypeKind(kind_str)
    except ValueError:
        kind = GraphQLTypeKind.OBJECT

    fields: list[GraphQLField] = []
    for field_data in type_data.get("fields") or []:
        field = parse_field(field_data)
        if field:
            fields.append(field)

    input_fields: list[GraphQLField] = []
    for field_data in type_data.get("inputFields") or []:
        field = parse_input_field(field_data)
        if field:
            input_fields.append(field)

    interfaces = [
        i.get("name") for i in (type_data.get("interfaces") or [])
        if i.get("name")
    ]

    possible_types = [
        t.get("name") for t in (type_data.get("possibleTypes") or [])
        if t.get("name")
    ]

    enum_values = [
        v.get("name") for v in (type_data.get("enumValues") or [])
        if v.get("name")
    ]

    return GraphQLType(
        name=name,
        kind=kind,
        description=type_data.get("description"),
        fields=fields,
        input_fields=input_fields,
        interfaces=interfaces,
        possible_types=possible_types,
        enum_values=enum_values,
    )


def parse_directive(directive_data: dict[str, Any]) -> Optional[GraphQLDirective]:
    """Parse a directive from introspection data."""
    name = directive_data.get("name")
    if not name:
        return None

    locations: list[GraphQLDirectiveLocation] = []
    for loc_str in directive_data.get("locations") or []:
        try:
            locations.append(GraphQLDirectiveLocation(loc_str))
        except ValueError:
            pass

    arguments: list[GraphQLArgument] = []
    for arg_data in directive_data.get("args") or []:
        arg = parse_argument(arg_data)
        if arg:
            arguments.append(arg)

    return GraphQLDirective(
        name=name,
        description=directive_data.get("description"),
        locations=locations,
        arguments=arguments,
    )


def parse_introspection_result(schema_data: dict[str, Any]) -> GraphQLSchema:
    """Parse introspection result into a GraphQL schema."""
    types: list[GraphQLType] = []
    directives: list[GraphQLDirective] = []

    for type_data in schema_data.get("types", []):
        gql_type = parse_type(type_data)
        if gql_type:
            types.append(gql_type)

    for directive_data in schema_data.get("directives", []):
        directive = parse_directive(directive_data)
        if directive:
            directives.append(directive)

    return GraphQLSchema(
        query_type=schema_data.get("queryType", {}).get("name"),
        mutation_type=schema_data.get("mutationType", {}).get("name") if schema_data.get("mutationType") else None,
        subscription_type=schema_data.get("subscriptionType", {}).get("name") if schema_data.get("subscriptionType") else None,
        types=types,
        directives=directives,
    )


def field_to_sdl(field: GraphQLField) -> str:
    """Convert a field to SDL."""
    args = ""
    if field.arguments:
        arg_strs = [
            f"{arg.name}: {arg.type_name}"
            for arg in field.arguments
        ]
        args = f"({', '.join(arg_strs)})"

    field_def = f"{field.name}{args}: {field.type_name}"

    if field.is_deprecated:
        if field.deprecation_reason:
            field_def += f' @deprecated(reason: "{field.deprecation_reason}")'
        else:
            field_def += " @deprecated"

    return field_def


def directive_to_sdl(directive: GraphQLDirective) -> str:
    """Convert a directive to SDL."""
    args = ""
    if directive.arguments:
        arg_strs = [
            f"{arg.name}: {arg.type_name}"
            for arg in directive.arguments
        ]
        args = f"({', '.join(arg_strs)})"

    locations = " | ".join(loc.value for loc in directive.locations)

    lines = []
    if directive.description:
        lines.append(f'"""{directive.description}"""')
    lines.append(f"directive @{directive.name}{args} on {locations}")

    return "\n".join(lines)


def type_to_sdl(gql_type: GraphQLType) -> str:
    """Convert a type to SDL."""
    lines = []

    if gql_type.description:
        lines.append(f'"""{gql_type.description}"""')

    if gql_type.kind == GraphQLTypeKind.SCALAR:
        lines.append(f"scalar {gql_type.name}")
    elif gql_type.kind == GraphQLTypeKind.ENUM:
        lines.append(f"enum {gql_type.name} {{")
        for value in gql_type.enum_values:
            lines.append(f"  {value}")
        lines.append("}")
    elif gql_type.kind == GraphQLTypeKind.UNION:
        types_str = " | ".join(gql_type.possible_types)
        lines.append(f"union {gql_type.name} = {types_str}")
    elif gql_type.kind == GraphQLTypeKind.INPUT_OBJECT:
        lines.append(f"input {gql_type.name} {{")
        for field in gql_type.input_fields:
            lines.append(f"  {field.name}: {field.type_name}")
        lines.append("}")
    elif gql_type.kind == GraphQLTypeKind.INTERFACE:
        lines.append(f"interface {gql_type.name} {{")
        for field in gql_type.fields:
            lines.append(f"  {field_to_sdl(field)}")
        lines.append("}")
    else:
        implements = ""
        if gql_type.interfaces:
            implements = " implements " + " & ".join(gql_type.interfaces)
        lines.append(f"type {gql_type.name}{implements} {{")
        for field in gql_type.fields:
            lines.append(f"  {field_to_sdl(field)}")
        lines.append("}")

    return "\n".join(lines)


def schema_to_sdl(schema: GraphQLSchema) -> str:
    """Convert an introspected schema to SDL."""
    lines = []

    if schema.mutation_type or schema.subscription_type:
        lines.append("schema {")
        lines.append(f"  query: {schema.query_type}")
        if schema.mutation_type:
            lines.append(f"  mutation: {schema.mutation_type}")
        if schema.subscription_type:
            lines.append(f"  subscription: {schema.subscription_type}")
        lines.append("}")
        lines.append("")

    for directive in schema.directives:
        if not directive.name.startswith("__"):
            lines.append(directive_to_sdl(directive))
            lines.append("")
    for gql_type in schema.types:
        if not gql_type.name.startswith("__"):
            lines.append(type_to_sdl(gql_type))
            lines.append("")

    return "\n".join(lines)
