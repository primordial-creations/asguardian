"""
GraphQL Introspection Service.

Introspects GraphQL endpoints to extract schema information.
"""

import json
from typing import Any, Optional, cast
from urllib.request import Request, urlopen
from urllib.error import URLError

from Asgard.Forseti.GraphQL.models.graphql_models import (
    GraphQLConfig,
    GraphQLSchema,
    GraphQLType,
    GraphQLField,
    GraphQLArgument,
    GraphQLDirective,
    GraphQLTypeKind,
    GraphQLDirectiveLocation,
)


class IntrospectionService:
    """
    Service for introspecting GraphQL endpoints.

    Queries GraphQL endpoints to extract schema information.

    Usage:
        service = IntrospectionService()
        schema = service.introspect("http://localhost:4000/graphql")
        print(f"Types: {len(schema.types)}")
    """

    INTROSPECTION_QUERY = """
    query IntrospectionQuery {
      __schema {
        queryType { name }
        mutationType { name }
        subscriptionType { name }
        types {
          ...FullType
        }
        directives {
          name
          description
          locations
          args {
            ...InputValue
          }
        }
      }
    }

    fragment FullType on __Type {
      kind
      name
      description
      fields(includeDeprecated: true) {
        name
        description
        args {
          ...InputValue
        }
        type {
          ...TypeRef
        }
        isDeprecated
        deprecationReason
      }
      inputFields {
        ...InputValue
      }
      interfaces {
        ...TypeRef
      }
      enumValues(includeDeprecated: true) {
        name
        description
        isDeprecated
        deprecationReason
      }
      possibleTypes {
        ...TypeRef
      }
    }

    fragment InputValue on __InputValue {
      name
      description
      type {
        ...TypeRef
      }
      defaultValue
    }

    fragment TypeRef on __Type {
      kind
      name
      ofType {
        kind
        name
        ofType {
          kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
              ofType {
                kind
                name
                ofType {
                  kind
                  name
                  ofType {
                    kind
                    name
                  }
                }
              }
            }
          }
        }
      }
    }
    """

    def __init__(self, config: Optional[GraphQLConfig] = None):
        """
        Initialize the introspection service.

        Args:
            config: Optional configuration for introspection behavior.
        """
        self.config = config or GraphQLConfig()

    def introspect(
        self,
        endpoint: str,
        headers: Optional[dict[str, str]] = None,
        timeout: int = 30
    ) -> GraphQLSchema:
        """
        Introspect a GraphQL endpoint.

        Args:
            endpoint: GraphQL endpoint URL.
            headers: Optional HTTP headers.
            timeout: Request timeout in seconds.

        Returns:
            Introspected GraphQLSchema.

        Raises:
            ConnectionError: If the endpoint cannot be reached.
            ValueError: If the response is not valid GraphQL.
        """
        if not self.config.allow_introspection:
            raise ValueError("Introspection is disabled in configuration")

        result = self._execute_query(endpoint, headers, timeout)
        return self._parse_introspection_result(result)

    def _execute_query(
        self,
        endpoint: str,
        headers: Optional[dict[str, str]],
        timeout: int
    ) -> dict[str, Any]:
        """Execute the introspection query."""
        request_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if headers:
            request_headers.update(headers)

        payload = json.dumps({
            "query": self.INTROSPECTION_QUERY,
        }).encode("utf-8")

        request = Request(endpoint, data=payload, headers=request_headers)

        try:
            with urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except URLError as e:
            raise ConnectionError(f"Failed to connect to endpoint: {e}")

        if "errors" in result:
            errors = result["errors"]
            error_messages = [e.get("message", str(e)) for e in errors]
            raise ValueError(f"GraphQL errors: {', '.join(error_messages)}")

        if "data" not in result or "__schema" not in result["data"]:
            raise ValueError("Invalid introspection response")

        return cast(dict[str, Any], result["data"]["__schema"])

    def _parse_introspection_result(self, schema_data: dict[str, Any]) -> GraphQLSchema:
        """Parse introspection result into a GraphQL schema."""
        types: list[GraphQLType] = []
        directives: list[GraphQLDirective] = []

        # Parse types
        for type_data in schema_data.get("types", []):
            gql_type = self._parse_type(type_data)
            if gql_type:
                types.append(gql_type)

        # Parse directives
        for directive_data in schema_data.get("directives", []):
            directive = self._parse_directive(directive_data)
            if directive:
                directives.append(directive)

        return GraphQLSchema(
            query_type=schema_data.get("queryType", {}).get("name"),
            mutation_type=schema_data.get("mutationType", {}).get("name") if schema_data.get("mutationType") else None,
            subscription_type=schema_data.get("subscriptionType", {}).get("name") if schema_data.get("subscriptionType") else None,
            types=types,
            directives=directives,
        )

    def _parse_type(self, type_data: dict[str, Any]) -> Optional[GraphQLType]:
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
            field = self._parse_field(field_data)
            if field:
                fields.append(field)

        input_fields: list[GraphQLField] = []
        for field_data in type_data.get("inputFields") or []:
            field = self._parse_input_field(field_data)
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

    def _parse_field(self, field_data: dict[str, Any]) -> Optional[GraphQLField]:
        """Parse a field from introspection data."""
        name = field_data.get("name")
        if not name:
            return None

        type_name = self._format_type_ref(field_data.get("type", {}))

        arguments: list[GraphQLArgument] = []
        for arg_data in field_data.get("args") or []:
            arg = self._parse_argument(arg_data)
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

    def _parse_input_field(self, field_data: dict[str, Any]) -> Optional[GraphQLField]:
        """Parse an input field from introspection data."""
        name = field_data.get("name")
        if not name:
            return None

        type_name = self._format_type_ref(field_data.get("type", {}))

        return GraphQLField(
            name=name,
            type_name=type_name,
            description=field_data.get("description"),
        )

    def _parse_argument(self, arg_data: dict[str, Any]) -> Optional[GraphQLArgument]:
        """Parse an argument from introspection data."""
        name = arg_data.get("name")
        if not name:
            return None

        type_name = self._format_type_ref(arg_data.get("type", {}))
        is_required = type_name.endswith("!")

        return GraphQLArgument(
            name=name,
            type_name=type_name,
            description=arg_data.get("description"),
            default_value=arg_data.get("defaultValue"),
            is_required=is_required,
        )

    def _parse_directive(self, directive_data: dict[str, Any]) -> Optional[GraphQLDirective]:
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
            arg = self._parse_argument(arg_data)
            if arg:
                arguments.append(arg)

        return GraphQLDirective(
            name=name,
            description=directive_data.get("description"),
            locations=locations,
            arguments=arguments,
        )

    def _format_type_ref(self, type_ref: dict[str, Any]) -> str:
        """Format a type reference as a string."""
        kind = type_ref.get("kind")
        name = type_ref.get("name")
        of_type = type_ref.get("ofType")

        if kind == "NON_NULL":
            inner = self._format_type_ref(of_type) if of_type else "Unknown"
            return f"{inner}!"
        elif kind == "LIST":
            inner = self._format_type_ref(of_type) if of_type else "Unknown"
            return f"[{inner}]"
        elif name:
            return cast(str, name)
        else:
            return "Unknown"

    def to_sdl(self, schema: GraphQLSchema) -> str:
        """
        Convert an introspected schema to SDL.

        Args:
            schema: Introspected schema.

        Returns:
            SDL string representation.
        """
        lines = []

        # Schema definition
        if schema.mutation_type or schema.subscription_type:
            lines.append("schema {")
            lines.append(f"  query: {schema.query_type}")
            if schema.mutation_type:
                lines.append(f"  mutation: {schema.mutation_type}")
            if schema.subscription_type:
                lines.append(f"  subscription: {schema.subscription_type}")
            lines.append("}")
            lines.append("")

        # Directives
        for directive in schema.directives:
            if not directive.name.startswith("__"):
                lines.append(self._directive_to_sdl(directive))
                lines.append("")

        # Types (excluding built-ins)
        for gql_type in schema.types:
            if not gql_type.name.startswith("__"):
                lines.append(self._type_to_sdl(gql_type))
                lines.append("")

        return "\n".join(lines)

    def _directive_to_sdl(self, directive: GraphQLDirective) -> str:
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

    def _type_to_sdl(self, gql_type: GraphQLType) -> str:
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
                lines.append(f"  {self._field_to_sdl(field)}")
            lines.append("}")
        else:  # OBJECT
            implements = ""
            if gql_type.interfaces:
                implements = " implements " + " & ".join(gql_type.interfaces)
            lines.append(f"type {gql_type.name}{implements} {{")
            for field in gql_type.fields:
                lines.append(f"  {self._field_to_sdl(field)}")
            lines.append("}")

        return "\n".join(lines)

    def _field_to_sdl(self, field: GraphQLField) -> str:
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
