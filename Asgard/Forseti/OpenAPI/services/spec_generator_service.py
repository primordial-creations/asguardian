"""
OpenAPI Specification Generator Service.

Generates OpenAPI specifications from source code analysis.
"""

import ast
import json
import re
import yaml  # type: ignore[import-untyped]
from pathlib import Path
from typing import Any, Optional, cast

from Asgard.Forseti.OpenAPI.models.openapi_models import (
    OpenAPIConfig,
    OpenAPIInfo,
    OpenAPISpec,
)


class SpecGeneratorService:
    """
    Service for generating OpenAPI specifications from code.

    Analyzes Python source files (FastAPI, Flask) and generates
    OpenAPI specifications.

    Usage:
        service = SpecGeneratorService()
        spec = service.generate_from_fastapi("./app")
        spec_dict = service.to_dict(spec)
    """

    def __init__(self, config: Optional[OpenAPIConfig] = None):
        """
        Initialize the generator service.

        Args:
            config: Optional configuration for generation behavior.
        """
        self.config = config or OpenAPIConfig()

    def generate_from_fastapi(
        self,
        source_path: str | Path,
        title: str = "Generated API",
        version: str = "1.0.0",
        description: Optional[str] = None,
    ) -> OpenAPISpec:
        """
        Generate OpenAPI specification from FastAPI source code.

        Args:
            source_path: Path to the FastAPI application source.
            title: API title.
            version: API version.
            description: API description.

        Returns:
            Generated OpenAPISpec.
        """
        source_path = Path(source_path)
        paths: dict[str, Any] = {}
        schemas: dict[str, Any] = {}

        # Find all Python files
        python_files = list(source_path.rglob("*.py"))

        for py_file in python_files:
            try:
                file_paths, file_schemas = self._analyze_fastapi_file(py_file)
                paths.update(file_paths)
                schemas.update(file_schemas)
            except Exception:
                # Skip files that can't be parsed
                continue

        return OpenAPISpec(
            openapi="3.1.0",
            info=OpenAPIInfo(
                title=title,
                version=version,
                description=description,
            ),
            paths=paths,
            components={"schemas": schemas} if schemas else None,
        )

    def _analyze_fastapi_file(
        self,
        file_path: Path
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Analyze a FastAPI file for routes and models.

        Args:
            file_path: Path to the Python file.

        Returns:
            Tuple of (paths dict, schemas dict).
        """
        paths: dict[str, Any] = {}
        schemas: dict[str, Any] = {}

        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content)

        # Find route decorators
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                route_info = self._extract_route_info(node)
                if route_info:
                    path, method, operation = route_info
                    if path not in paths:
                        paths[path] = {}
                    paths[path][method.lower()] = operation

            # Find Pydantic models
            elif isinstance(node, ast.ClassDef):
                schema_info = self._extract_pydantic_schema(node)
                if schema_info:
                    name, schema = schema_info
                    schemas[name] = schema

        return paths, schemas

    def _extract_route_info(
        self,
        node: ast.FunctionDef
    ) -> Optional[tuple[str, str, dict[str, Any]]]:
        """
        Extract route information from a function definition.

        Args:
            node: AST function definition node.

        Returns:
            Tuple of (path, method, operation) or None.
        """
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                func = decorator.func
                if isinstance(func, ast.Attribute):
                    method = func.attr
                    if method in ["get", "post", "put", "delete", "patch", "options", "head"]:
                        # Extract path from first argument
                        if decorator.args:
                            path_arg = decorator.args[0]
                            if isinstance(path_arg, ast.Constant):
                                path = cast(str, path_arg.value)
                                operation = self._build_operation(node, decorator)
                                return path, method.upper(), operation
        return None

    def _build_operation(
        self,
        func_node: ast.FunctionDef,
        decorator: ast.Call
    ) -> dict[str, Any]:
        """
        Build an operation object from function and decorator.

        Args:
            func_node: Function AST node.
            decorator: Decorator AST node.

        Returns:
            Operation dictionary.
        """
        operation: dict[str, Any] = {
            "operationId": func_node.name,
            "responses": {
                "200": {
                    "description": "Successful response",
                }
            }
        }

        # Extract docstring as summary/description
        docstring = ast.get_docstring(func_node)
        if docstring:
            lines = docstring.strip().split("\n")
            operation["summary"] = lines[0]
            if len(lines) > 1:
                operation["description"] = "\n".join(lines[1:]).strip()

        # Extract parameters from function arguments
        parameters = []
        for arg in func_node.args.args:
            if arg.arg not in ["self", "request", "db", "session"]:
                param = {
                    "name": arg.arg,
                    "in": "query",
                    "required": True,
                    "schema": {"type": "string"},
                }

                # Check for type annotation
                if arg.annotation:
                    param["schema"] = self._annotation_to_schema(arg.annotation)

                parameters.append(param)

        if parameters:
            operation["parameters"] = parameters

        # Extract tags from decorator keywords
        for keyword in decorator.keywords:
            if keyword.arg == "tags":
                if isinstance(keyword.value, ast.List):
                    tags = []
                    for elt in keyword.value.elts:
                        if isinstance(elt, ast.Constant):
                            tags.append(elt.value)
                    operation["tags"] = tags
            elif keyword.arg == "summary":
                if isinstance(keyword.value, ast.Constant):
                    operation["summary"] = keyword.value.value
            elif keyword.arg == "description":
                if isinstance(keyword.value, ast.Constant):
                    operation["description"] = keyword.value.value

        return operation

    def _annotation_to_schema(self, annotation: ast.expr) -> dict[str, Any]:
        """
        Convert a type annotation to a JSON schema.

        Args:
            annotation: AST annotation node.

        Returns:
            JSON schema dictionary.
        """
        if isinstance(annotation, ast.Name):
            type_name = annotation.id
            type_map = {
                "str": {"type": "string"},
                "int": {"type": "integer"},
                "float": {"type": "number"},
                "bool": {"type": "boolean"},
                "list": {"type": "array"},
                "dict": {"type": "object"},
                "List": {"type": "array"},
                "Dict": {"type": "object"},
            }
            return type_map.get(type_name, {"type": "string"})

        elif isinstance(annotation, ast.Subscript):
            # Handle generic types like List[str], Optional[int]
            if isinstance(annotation.value, ast.Name):
                container = annotation.value.id
                if container in ["List", "list"]:
                    return {
                        "type": "array",
                        "items": self._annotation_to_schema(annotation.slice),
                    }
                elif container == "Optional":
                    schema = self._annotation_to_schema(annotation.slice)
                    schema["nullable"] = True
                    return schema
                elif container in ["Dict", "dict"]:
                    return {"type": "object"}

        return {"type": "string"}

    def _extract_pydantic_schema(
        self,
        node: ast.ClassDef
    ) -> Optional[tuple[str, dict[str, Any]]]:
        """
        Extract Pydantic model as JSON schema.

        Args:
            node: AST class definition node.

        Returns:
            Tuple of (name, schema) or None.
        """
        # Check if it's a Pydantic model
        is_pydantic = False
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id in ["BaseModel", "Schema"]:
                is_pydantic = True
                break
            elif isinstance(base, ast.Attribute) and base.attr in ["BaseModel", "Schema"]:
                is_pydantic = True
                break

        if not is_pydantic:
            return None

        schema: dict[str, Any] = {
            "type": "object",
            "properties": {},
        }
        required = []

        # Extract docstring
        docstring = ast.get_docstring(node)
        if docstring:
            schema["description"] = docstring

        # Extract fields
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                field_name = item.target.id
                if field_name.startswith("_"):
                    continue

                field_schema = self._annotation_to_schema(item.annotation)

                # Check for default value
                if item.value is None:
                    required.append(field_name)
                elif isinstance(item.value, ast.Call):
                    # Could be Field() with default
                    pass

                schema["properties"][field_name] = field_schema

        if required:
            schema["required"] = required

        return node.name, schema

    def to_dict(self, spec: OpenAPISpec) -> dict[str, Any]:
        """
        Convert an OpenAPISpec to a dictionary.

        Args:
            spec: OpenAPI specification.

        Returns:
            Dictionary representation.
        """
        return cast(dict[str, Any], spec.model_dump(exclude_none=True, by_alias=True))

    def to_yaml(self, spec: OpenAPISpec) -> str:
        """
        Convert an OpenAPISpec to YAML.

        Args:
            spec: OpenAPI specification.

        Returns:
            YAML string representation.
        """
        return cast(str, yaml.dump(self.to_dict(spec), default_flow_style=False, sort_keys=False))

    def to_json(self, spec: OpenAPISpec, indent: int = 2) -> str:
        """
        Convert an OpenAPISpec to JSON.

        Args:
            spec: OpenAPI specification.
            indent: JSON indentation.

        Returns:
            JSON string representation.
        """
        return json.dumps(self.to_dict(spec), indent=indent)
