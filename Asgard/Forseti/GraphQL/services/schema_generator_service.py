"""
GraphQL Schema Generator Service.

Generates GraphQL schemas from source code analysis.
"""

import ast
from pathlib import Path
from typing import Any, Optional

from Asgard.Forseti.GraphQL.models.graphql_models import (
    GraphQLConfig,
    GraphQLSchema,
    GraphQLType,
    GraphQLField,
    GraphQLTypeKind,
)
from Asgard.Forseti.GraphQL.services._schema_generator_helpers import (
    TYPE_MAP,
    openapi_operation_to_field,
    openapi_schema_to_type,
    openapi_type_to_graphql,
    schema_to_sdl,
    type_to_sdl,
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

        types.append(GraphQLType(
            name="Query",
            kind=GraphQLTypeKind.OBJECT,
            description="Root query type",
            fields=[],
        ))

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
        """Analyze a Python file for model definitions."""
        types: list[GraphQLType] = []
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
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
        """Convert a class definition to a GraphQL type."""
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
        """Convert a type annotation to a GraphQL type."""
        if isinstance(annotation, ast.Name):
            type_name = annotation.id
            return TYPE_MAP.get(type_name, type_name)

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
        return schema_to_sdl(schema)

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

        schemas = openapi_spec.get("components", {}).get("schemas", {})
        for name, schema in schemas.items():
            gql_type = openapi_schema_to_type(name, schema, self._openapi_type_to_graphql)
            if gql_type:
                types.append(gql_type)

        paths = openapi_spec.get("paths", {})
        for path, path_item in paths.items():
            for method in ["get", "post", "put", "delete", "patch"]:
                if method in path_item:
                    operation = path_item[method]
                    field = openapi_operation_to_field(path, method, operation, self._openapi_type_to_graphql)
                    if field:
                        if method == "get":
                            query_fields.append(field)
                        else:
                            mutation_fields.append(field)

        types.append(GraphQLType(
            name="Query",
            kind=GraphQLTypeKind.OBJECT,
            fields=query_fields if query_fields else [
                GraphQLField(name="_empty", type_name="String")
            ],
        ))

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

    def _openapi_type_to_graphql(self, schema: dict[str, Any]) -> str:
        """Convert an OpenAPI type to a GraphQL type."""
        return openapi_type_to_graphql(schema, self._openapi_type_to_graphql)
