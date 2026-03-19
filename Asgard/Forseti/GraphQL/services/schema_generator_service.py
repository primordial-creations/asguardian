"""
GraphQL Schema Generator Service.

Generates GraphQL schemas from source code analysis.
"""

import ast
import re
from pathlib import Path
from typing import Any, Optional, cast

from Asgard.Forseti.GraphQL.models.graphql_models import (
    GraphQLConfig,
    GraphQLSchema,
    GraphQLType,
    GraphQLField,
    GraphQLTypeKind,
)


class SchemaGeneratorService:
    """
    Service for generating GraphQL schemas from code.

    Analyzes Python source files and generates GraphQL SDL.

    Usage:
        service = SchemaGeneratorService()
        schema = service.generate_from_models("./models")
        sdl = service.to_sdl(schema)
    """

    # Python to GraphQL type mapping
    TYPE_MAP = {
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

    def __init__(self, config: Optional[GraphQLConfig] = None):
        """
        Initialize the generator service.

        Args:
            config: Optional configuration for generation behavior.
        """
        self.config = config or GraphQLConfig()

    def generate_from_models(
        self,
        source_path: str | Path,
        base_class: str = "BaseModel"
    ) -> GraphQLSchema:
        """
        Generate GraphQL schema from Pydantic models.

        Args:
            source_path: Path to the source directory.
            base_class: Base class name to identify models.

        Returns:
            Generated GraphQLSchema.
        """
        source_path = Path(source_path)
        types: list[GraphQLType] = []

        # Add Query type placeholder
        types.append(GraphQLType(
            name="Query",
            kind=GraphQLTypeKind.OBJECT,
            description="Root query type",
            fields=[],
        ))

        # Find all Python files
        python_files = list(source_path.rglob("*.py"))

        for py_file in python_files:
            try:
                file_types = self._analyze_file(py_file, base_class)
                types.extend(file_types)
            except Exception:
                continue

        return GraphQLSchema(
            query_type="Query",
            types=types,
        )

    def _analyze_file(
        self,
        file_path: Path,
        base_class: str
    ) -> list[GraphQLType]:
        """
        Analyze a Python file for model definitions.

        Args:
            file_path: Path to the Python file.
            base_class: Base class name to identify models.

        Returns:
            List of GraphQL types.
        """
        types: list[GraphQLType] = []
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if class inherits from base_class
                is_model = False
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == base_class:
                        is_model = True
                        break
                    elif isinstance(base, ast.Attribute) and base.attr == base_class:
                        is_model = True
                        break

                if is_model:
                    gql_type = self._convert_class_to_type(node)
                    if gql_type:
                        types.append(gql_type)

        return types

    def _convert_class_to_type(self, node: ast.ClassDef) -> Optional[GraphQLType]:
        """
        Convert a class definition to a GraphQL type.

        Args:
            node: AST class definition node.

        Returns:
            GraphQL type or None.
        """
        fields: list[GraphQLField] = []
        description = ast.get_docstring(node)

        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                field_name = item.target.id
                if field_name.startswith("_"):
                    continue

                type_name = self._annotation_to_graphql_type(item.annotation)
                is_optional = "Optional" in ast.dump(item.annotation)

                field = GraphQLField(
                    name=field_name,
                    type_name=type_name if is_optional else f"{type_name}!",
                )
                fields.append(field)

        if not fields:
            return None

        return GraphQLType(
            name=node.name,
            kind=GraphQLTypeKind.OBJECT,
            description=description,
            fields=fields,
        )

    def _annotation_to_graphql_type(self, annotation: ast.expr) -> str:
        """
        Convert a type annotation to a GraphQL type.

        Args:
            annotation: AST annotation node.

        Returns:
            GraphQL type string.
        """
        if isinstance(annotation, ast.Name):
            type_name = annotation.id
            return self.TYPE_MAP.get(type_name, type_name)

        elif isinstance(annotation, ast.Subscript):
            if isinstance(annotation.value, ast.Name):
                container = annotation.value.id
                if container in ["List", "list"]:
                    inner_type = self._annotation_to_graphql_type(annotation.slice)
                    return f"[{inner_type}]"
                elif container == "Optional":
                    return self._annotation_to_graphql_type(annotation.slice)
                elif container in ["Dict", "dict"]:
                    return "JSON"

        elif isinstance(annotation, ast.Constant):
            if annotation.value is None:
                return "String"

        return "String"

    def to_sdl(self, schema: GraphQLSchema) -> str:
        """
        Convert a GraphQL schema to SDL.

        Args:
            schema: GraphQL schema object.

        Returns:
            SDL string.
        """
        lines = []

        # Add custom scalars if needed
        used_types = set()
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

        # Generate type definitions
        for gql_type in schema.types:
            lines.append(self._type_to_sdl(gql_type))
            lines.append("")

        return "\n".join(lines)

    def _type_to_sdl(self, gql_type: GraphQLType) -> str:
        """
        Convert a GraphQL type to SDL.

        Args:
            gql_type: GraphQL type object.

        Returns:
            SDL string for the type.
        """
        lines = []

        # Add description
        if gql_type.description:
            lines.append(f'"""')
            lines.append(gql_type.description)
            lines.append(f'"""')

        # Type declaration
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

        # Object, Interface, or Input type
        implements = ""
        if gql_type.interfaces:
            implements = " implements " + " & ".join(gql_type.interfaces)

        lines.append(f"{kind_keyword} {gql_type.name}{implements} {{")

        # Fields
        fields = gql_type.input_fields if gql_type.kind == GraphQLTypeKind.INPUT_OBJECT else gql_type.fields
        for field in fields:
            field_line = self._field_to_sdl(field)
            lines.append(f"  {field_line}")

        lines.append("}")
        return "\n".join(lines)

    def _field_to_sdl(self, field: GraphQLField) -> str:
        """
        Convert a GraphQL field to SDL.

        Args:
            field: GraphQL field object.

        Returns:
            SDL string for the field.
        """
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

    def generate_from_openapi(
        self,
        openapi_spec: dict[str, Any]
    ) -> GraphQLSchema:
        """
        Generate GraphQL schema from an OpenAPI specification.

        Args:
            openapi_spec: OpenAPI specification dictionary.

        Returns:
            Generated GraphQLSchema.
        """
        types: list[GraphQLType] = []
        query_fields: list[GraphQLField] = []
        mutation_fields: list[GraphQLField] = []

        # Convert schemas to types
        schemas = openapi_spec.get("components", {}).get("schemas", {})
        for name, schema in schemas.items():
            gql_type = self._openapi_schema_to_type(name, schema)
            if gql_type:
                types.append(gql_type)

        # Convert paths to query/mutation fields
        paths = openapi_spec.get("paths", {})
        for path, path_item in paths.items():
            for method in ["get", "post", "put", "delete", "patch"]:
                if method in path_item:
                    operation = path_item[method]
                    field = self._openapi_operation_to_field(path, method, operation)
                    if field:
                        if method == "get":
                            query_fields.append(field)
                        else:
                            mutation_fields.append(field)

        # Add Query type
        types.append(GraphQLType(
            name="Query",
            kind=GraphQLTypeKind.OBJECT,
            fields=query_fields if query_fields else [
                GraphQLField(name="_empty", type_name="String")
            ],
        ))

        # Add Mutation type if there are mutations
        if mutation_fields:
            types.append(GraphQLType(
                name="Mutation",
                kind=GraphQLTypeKind.OBJECT,
                fields=mutation_fields,
            ))

        return GraphQLSchema(
            query_type="Query",
            mutation_type="Mutation" if mutation_fields else None,
            types=types,
        )

    def _openapi_schema_to_type(
        self,
        name: str,
        schema: dict[str, Any]
    ) -> Optional[GraphQLType]:
        """Convert an OpenAPI schema to a GraphQL type."""
        fields: list[GraphQLField] = []
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))

        for prop_name, prop_schema in properties.items():
            type_name = self._openapi_type_to_graphql(prop_schema)
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

    def _openapi_type_to_graphql(self, schema: dict[str, Any]) -> str:
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
            item_type = self._openapi_type_to_graphql(schema["items"])
            return f"[{item_type}]"

        return type_map.get(schema_type, "String")

    def _openapi_operation_to_field(
        self,
        path: str,
        method: str,
        operation: dict[str, Any]
    ) -> Optional[GraphQLField]:
        """Convert an OpenAPI operation to a GraphQL field."""
        operation_id = operation.get("operationId")
        if not operation_id:
            # Generate operation ID from path and method
            operation_id = method + re.sub(r'[^a-zA-Z0-9]', '_', path).title().replace("_", "")

        # Determine return type
        responses = operation.get("responses", {})
        return_type = "Boolean"
        for status in ["200", "201", "default"]:
            if status in responses:
                response = responses[status]
                content = response.get("content", {})
                if "application/json" in content:
                    schema = content["application/json"].get("schema", {})
                    return_type = self._openapi_type_to_graphql(schema)
                break

        return GraphQLField(
            name=operation_id,
            type_name=return_type,
            description=operation.get("summary") or operation.get("description"),
        )
