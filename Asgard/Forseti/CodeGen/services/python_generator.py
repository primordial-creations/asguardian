"""
Python Code Generator Service.

Generates Python API client code from OpenAPI specifications.
"""

import json
import re
import time
from pathlib import Path
from typing import Any, Optional, cast

import yaml  # type: ignore[import-untyped]

from Asgard.Forseti.CodeGen.models.codegen_models import (
    CodeGenConfig,
    CodeGenReport,
    GeneratedFile,
    HttpClientType,
    MethodDefinition,
    ParameterDefinition,
    PropertyDefinition,
    TargetLanguage,
    TypeDefinition,
)


class PythonGeneratorService:
    """
    Service for generating Python API clients from OpenAPI specifications.

    Generates type-safe Python code with support for requests, httpx, and aiohttp.

    Usage:
        generator = PythonGeneratorService()
        result = generator.generate("api.yaml")
        for file in result.generated_files:
            print(f"Generated: {file.path}")
    """

    def __init__(self, config: Optional[CodeGenConfig] = None):
        """
        Initialize the Python generator.

        Args:
            config: Optional configuration for code generation.
        """
        self.config = config or CodeGenConfig(target_language=TargetLanguage.PYTHON)

        # Set default HTTP client for Python
        if not self.config.http_client:
            self.config.http_client = (
                HttpClientType.HTTPX if self.config.use_async else HttpClientType.REQUESTS
            )

    def generate(
        self,
        spec_path: str | Path,
        output_dir: Optional[str | Path] = None
    ) -> CodeGenReport:
        """
        Generate Python client from OpenAPI specification.

        Args:
            spec_path: Path to the OpenAPI specification file.
            output_dir: Optional output directory for generated files.

        Returns:
            CodeGenReport with generated files and statistics.
        """
        start_time = time.time()
        spec_path = Path(spec_path)
        warnings: list[str] = []
        errors: list[str] = []

        # Load specification
        try:
            spec_data = self._load_spec_file(spec_path)
        except Exception as e:
            errors.append(f"Failed to load specification: {e}")
            return CodeGenReport(
                success=False,
                source_spec=str(spec_path),
                target_language=TargetLanguage.PYTHON,
                errors=errors,
                generation_time_ms=(time.time() - start_time) * 1000,
            )

        # Parse types from spec
        types = self._parse_types(spec_data, warnings)

        # Parse methods from spec
        methods = self._parse_methods(spec_data, types, warnings)

        # Generate files
        generated_files: list[GeneratedFile] = []

        # Generate models file
        if self.config.generate_models:
            models_file = self._generate_models_file(types, spec_data)
            generated_files.append(models_file)

        # Generate client file
        if self.config.generate_client:
            client_file = self._generate_client_file(methods, types, spec_data)
            generated_files.append(client_file)

        # Generate __init__.py
        init_file = self._generate_init_file(generated_files)
        generated_files.append(init_file)

        # Calculate totals
        total_lines = sum(f.line_count for f in generated_files)

        # Write files if output directory specified
        if output_dir:
            self._write_files(generated_files, Path(output_dir))

        return CodeGenReport(
            success=len(errors) == 0,
            source_spec=str(spec_path),
            target_language=TargetLanguage.PYTHON,
            generated_files=generated_files,
            types_generated=len(types),
            methods_generated=len(methods),
            total_lines=total_lines,
            warnings=warnings,
            errors=errors,
            generation_time_ms=(time.time() - start_time) * 1000,
        )

    def _load_spec_file(self, spec_path: Path) -> dict[str, Any]:
        """Load a specification file."""
        content = spec_path.read_text(encoding="utf-8")

        try:
            return cast(dict[str, Any], yaml.safe_load(content))
        except yaml.YAMLError:
            return cast(dict[str, Any], json.loads(content))

    def _parse_types(
        self,
        spec_data: dict[str, Any],
        warnings: list[str]
    ) -> dict[str, TypeDefinition]:
        """Parse type definitions from OpenAPI schemas."""
        types: dict[str, TypeDefinition] = {}
        components = spec_data.get("components", {})
        schemas = components.get("schemas", {})

        for schema_name, schema_data in schemas.items():
            if not isinstance(schema_data, dict):
                continue

            type_def = self._schema_to_type(schema_name, schema_data, warnings)
            types[schema_name] = type_def

        return types

    def _schema_to_type(
        self,
        name: str,
        schema: dict[str, Any],
        warnings: list[str]
    ) -> TypeDefinition:
        """Convert a JSON Schema to a TypeDefinition."""
        # Check if it's an enum
        if "enum" in schema:
            return TypeDefinition(
                name=name,
                description=schema.get("description"),
                is_enum=True,
                enum_values=schema["enum"],
            )

        # Parse properties
        properties: dict[str, PropertyDefinition] = {}
        schema_props = schema.get("properties", {})
        required_props = schema.get("required", [])

        for prop_name, prop_schema in schema_props.items():
            prop_def = self._schema_to_property(prop_name, prop_schema, prop_name in required_props)
            properties[prop_name] = prop_def

        return TypeDefinition(
            name=name,
            description=schema.get("description"),
            properties=properties,
            required_properties=required_props,
        )

    def _schema_to_property(
        self,
        name: str,
        schema: dict[str, Any],
        required: bool
    ) -> PropertyDefinition:
        """Convert a JSON Schema property to a PropertyDefinition."""
        type_name = self._json_type_to_python(schema)
        is_array = schema.get("type") == "array"
        array_item_type = None

        if is_array and "items" in schema:
            array_item_type = self._json_type_to_python(schema["items"])

        return PropertyDefinition(
            name=name,
            type_name=type_name,
            description=schema.get("description"),
            required=required,
            nullable=schema.get("nullable", False),
            default_value=schema.get("default"),
            format=schema.get("format"),
            is_array=is_array,
            array_item_type=array_item_type,
        )

    def _json_type_to_python(self, schema: dict[str, Any]) -> str:
        """Convert JSON Schema type to Python type."""
        if "$ref" in schema:
            ref = cast(str, schema["$ref"])
            return ref.split("/")[-1]

        schema_type = schema.get("type", "Any")

        if schema_type == "string":
            format_type = schema.get("format")
            if format_type == "date":
                return "date"
            elif format_type == "date-time":
                return "datetime"
            return "str"
        elif schema_type == "integer":
            return "int"
        elif schema_type == "number":
            return "float"
        elif schema_type == "boolean":
            return "bool"
        elif schema_type == "array":
            items = schema.get("items", {})
            item_type = self._json_type_to_python(items)
            return f"list[{item_type}]"
        elif schema_type == "object":
            if "additionalProperties" in schema:
                value_type = self._json_type_to_python(schema["additionalProperties"])
                return f"dict[str, {value_type}]"
            return "dict[str, Any]"
        elif isinstance(schema_type, list):
            py_types = [self._json_type_to_python({"type": t}) for t in schema_type if t != "null"]
            if "null" in schema_type:
                py_types.append("None")
            return " | ".join(py_types)

        if "oneOf" in schema or "anyOf" in schema:
            variants = schema.get("oneOf") or schema.get("anyOf", [])
            py_types = [self._json_type_to_python(v) for v in variants]
            return " | ".join(py_types)

        return "Any"

    def _parse_methods(
        self,
        spec_data: dict[str, Any],
        types: dict[str, TypeDefinition],
        warnings: list[str]
    ) -> list[MethodDefinition]:
        """Parse API methods from OpenAPI paths."""
        methods: list[MethodDefinition] = []
        paths = spec_data.get("paths", {})
        http_methods = ["get", "post", "put", "patch", "delete", "options", "head"]

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            path_params = self._parse_parameters(path_item.get("parameters", []))

            for method in http_methods:
                if method not in path_item:
                    continue

                operation = path_item[method]
                if not isinstance(operation, dict):
                    continue

                method_def = self._operation_to_method(
                    path, method, operation, path_params, warnings
                )
                methods.append(method_def)

        return methods

    def _parse_parameters(
        self,
        params: list[dict[str, Any]]
    ) -> list[ParameterDefinition]:
        """Parse OpenAPI parameters."""
        result: list[ParameterDefinition] = []

        for param in params:
            if not isinstance(param, dict):
                continue

            param_def = ParameterDefinition(
                name=param.get("name", ""),
                location=param.get("in", "query"),
                type_name=self._json_type_to_python(param.get("schema", {})),
                description=param.get("description"),
                required=param.get("required", False),
                default_value=param.get("schema", {}).get("default"),
            )
            result.append(param_def)

        return result

    def _operation_to_method(
        self,
        path: str,
        http_method: str,
        operation: dict[str, Any],
        path_params: list[ParameterDefinition],
        warnings: list[str]
    ) -> MethodDefinition:
        """Convert an OpenAPI operation to a MethodDefinition."""
        op_params = self._parse_parameters(operation.get("parameters", []))
        all_params = path_params + op_params

        request_body_type = None
        if "requestBody" in operation:
            request_body = operation["requestBody"]
            content = request_body.get("content", {})
            for content_type, media in content.items():
                if "schema" in media:
                    request_body_type = self._json_type_to_python(media["schema"])
                    break

        response_type = None
        responses = operation.get("responses", {})
        for status_code in ["200", "201", "default"]:
            if status_code in responses:
                response = responses[status_code]
                content = response.get("content", {})
                for content_type, media in content.items():
                    if "schema" in media:
                        response_type = self._json_type_to_python(media["schema"])
                        break
                if response_type:
                    break

        method_name = operation.get("operationId")
        if not method_name:
            method_name = self._generate_method_name(path, http_method)

        return MethodDefinition(
            name=self._to_snake_case(method_name),
            http_method=http_method.upper(),
            path=path,
            description=operation.get("summary") or operation.get("description"),
            parameters=all_params,
            request_body_type=request_body_type,
            response_type=response_type,
            tags=operation.get("tags", []),
            deprecated=operation.get("deprecated", False),
        )

    def _generate_method_name(self, path: str, method: str) -> str:
        """Generate a method name from path and HTTP method."""
        clean_path = path.replace("{", "by_").replace("}", "")
        clean_path = re.sub(r"[^a-zA-Z0-9_]", "_", clean_path)
        parts = [p for p in clean_path.split("_") if p]

        return f"{method}_{'_'.join(parts)}"

    def _to_snake_case(self, name: str) -> str:
        """Convert a name to snake_case."""
        name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
        name = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", name)
        return name.replace("-", "_").lower()

    def _generate_models_file(
        self,
        types: dict[str, TypeDefinition],
        spec_data: dict[str, Any]
    ) -> GeneratedFile:
        """Generate the models.py file."""
        lines: list[str] = []
        info = spec_data.get("info", {})

        # File header
        lines.append('"""')
        lines.append(f'{info.get("title", "API")} - Model Definitions')
        lines.append("")
        lines.append("Generated by Forseti CodeGen")
        if info.get("version"):
            lines.append(f'API Version: {info.get("version")}')
        lines.append('"""')
        lines.append("")

        # Imports
        lines.append("from datetime import date, datetime")
        lines.append("from enum import Enum")
        lines.append("from typing import Any, Optional")
        lines.append("")
        lines.append("from pydantic import BaseModel, Field")
        lines.append("")
        lines.append("")

        # Generate types
        for type_name, type_def in types.items():
            type_code = self._generate_type(type_def)
            lines.extend(type_code)
            lines.append("")
            lines.append("")

        content = "\n".join(lines)

        return GeneratedFile(
            path="models.py",
            content=content,
            language=TargetLanguage.PYTHON,
            file_type="models",
            line_count=len(lines),
        )

    def _generate_type(self, type_def: TypeDefinition) -> list[str]:
        """Generate Python code for a type definition."""
        lines: list[str] = []

        if type_def.is_enum:
            # Generate Enum
            lines.append(f"class {type_def.name}(str, Enum):")
            if type_def.description and self.config.include_documentation:
                lines.append(f'    """{type_def.description}"""')
                lines.append("")

            for value in type_def.enum_values:
                if isinstance(value, str):
                    enum_name = value.upper().replace("-", "_").replace(" ", "_")
                    lines.append(f'    {enum_name} = "{value}"')
                else:
                    lines.append(f"    VALUE_{value} = {value}")
        else:
            # Generate Pydantic model
            lines.append(f"class {type_def.name}(BaseModel):")

            if type_def.description and self.config.include_documentation:
                lines.append(f'    """{type_def.description}"""')
                lines.append("")

            if not type_def.properties:
                lines.append("    pass")
            else:
                for prop_name, prop_def in type_def.properties.items():
                    prop_code = self._generate_property(prop_def)
                    lines.append(f"    {prop_code}")

        return lines

    def _generate_property(self, prop_def: PropertyDefinition) -> str:
        """Generate a single property definition."""
        type_str = prop_def.type_name

        # Handle optional
        if not prop_def.required:
            type_str = f"Optional[{type_str}]"

        # Handle nullable
        if prop_def.nullable and prop_def.required:
            type_str = f"{prop_def.type_name} | None"

        # Build Field arguments
        field_args: list[str] = []

        if prop_def.default_value is not None:
            if isinstance(prop_def.default_value, str):
                field_args.append(f'default="{prop_def.default_value}"')
            else:
                field_args.append(f"default={prop_def.default_value}")
        elif not prop_def.required:
            field_args.append("default=None")

        if prop_def.description and self.config.include_documentation:
            escaped_desc = prop_def.description.replace('"', '\\"')
            field_args.append(f'description="{escaped_desc}"')

        if field_args:
            return f"{prop_def.name}: {type_str} = Field({', '.join(field_args)})"
        else:
            return f"{prop_def.name}: {type_str}"

    def _generate_client_file(
        self,
        methods: list[MethodDefinition],
        types: dict[str, TypeDefinition],
        spec_data: dict[str, Any]
    ) -> GeneratedFile:
        """Generate the client.py file."""
        lines: list[str] = []
        info = spec_data.get("info", {})
        is_async = self.config.use_async

        # File header
        lines.append('"""')
        lines.append(f'{info.get("title", "API")} - API Client')
        lines.append("")
        lines.append("Generated by Forseti CodeGen")
        lines.append('"""')
        lines.append("")

        # Imports
        lines.append("from typing import Any, Optional")
        lines.append("")

        if is_async and self.config.http_client == HttpClientType.HTTPX:
            lines.append("import httpx")
        elif is_async and self.config.http_client == HttpClientType.AIOHTTP:
            lines.append("import aiohttp")
        else:
            lines.append("import requests")
        lines.append("")

        # Import models
        type_imports = self._get_type_imports(methods, types)
        if type_imports:
            lines.append(f"from .models import {', '.join(sorted(type_imports))}")
            lines.append("")
        lines.append("")

        # Exception class
        lines.append("class ApiError(Exception):")
        lines.append('    """API error with status code and response."""')
        lines.append("")
        lines.append("    def __init__(self, message: str, status_code: int, response: Any = None):")
        lines.append("        super().__init__(message)")
        lines.append("        self.status_code = status_code")
        lines.append("        self.response = response")
        lines.append("")
        lines.append("")

        # Client class
        lines.append("class ApiClient:")
        lines.append(f'    """{info.get("title", "API")} client."""')
        lines.append("")

        # Constructor
        lines.append("    def __init__(")
        lines.append("        self,")
        lines.append("        base_url: str,")
        lines.append("        headers: Optional[dict[str, str]] = None,")
        if is_async and self.config.http_client == HttpClientType.HTTPX:
            lines.append("        client: Optional[httpx.AsyncClient] = None,")
        lines.append("    ):")
        lines.append('        self.base_url = base_url.rstrip("/")')
        lines.append("        self.headers = {")
        lines.append('            "Content-Type": "application/json",')
        lines.append("            **(headers or {}),")
        lines.append("        }")
        if is_async and self.config.http_client == HttpClientType.HTTPX:
            lines.append("        self._client = client")
        lines.append("")

        # Request method
        lines.extend(self._generate_request_method(is_async))
        lines.append("")

        # API methods
        for method in methods:
            method_code = self._generate_api_method(method, is_async)
            lines.extend(method_code)
            lines.append("")

        content = "\n".join(lines)

        return GeneratedFile(
            path="client.py",
            content=content,
            language=TargetLanguage.PYTHON,
            file_type="client",
            line_count=len(lines),
        )

    def _get_type_imports(
        self,
        methods: list[MethodDefinition],
        types: dict[str, TypeDefinition]
    ) -> set[str]:
        """Get the set of types that need to be imported."""
        imports: set[str] = set()

        for method in methods:
            if method.request_body_type:
                base_type = method.request_body_type.split("[")[0]
                if base_type in types:
                    imports.add(base_type)

            if method.response_type:
                base_type = method.response_type.split("[")[0]
                if base_type in types:
                    imports.add(base_type)

        return imports

    def _generate_request_method(self, is_async: bool) -> list[str]:
        """Generate the private request method."""
        lines: list[str] = []
        async_kw = "async " if is_async else ""
        await_kw = "await " if is_async else ""

        if is_async and self.config.http_client == HttpClientType.HTTPX:
            lines.append(f"    {async_kw}def _request(")
            lines.append("        self,")
            lines.append("        method: str,")
            lines.append("        path: str,")
            lines.append("        params: Optional[dict[str, Any]] = None,")
            lines.append("        json_data: Optional[Any] = None,")
            lines.append("    ) -> Any:")
            lines.append('        """Make an HTTP request."""')
            lines.append('        url = f"{self.base_url}{path}"')
            lines.append("")
            lines.append("        if self._client:")
            lines.append("            response = await self._client.request(")
            lines.append("                method, url, params=params, json=json_data, headers=self.headers")
            lines.append("            )")
            lines.append("        else:")
            lines.append("            async with httpx.AsyncClient() as client:")
            lines.append("                response = await client.request(")
            lines.append("                    method, url, params=params, json=json_data, headers=self.headers")
            lines.append("                )")
            lines.append("")
            lines.append("        if response.status_code >= 400:")
            lines.append("            raise ApiError(")
            lines.append('                f"Request failed: {response.status_code}",')
            lines.append("                response.status_code,")
            lines.append("                response.text,")
            lines.append("            )")
            lines.append("")
            lines.append("        if response.status_code == 204:")
            lines.append("            return None")
            lines.append("")
            lines.append("        return response.json()")
        else:
            lines.append("    def _request(")
            lines.append("        self,")
            lines.append("        method: str,")
            lines.append("        path: str,")
            lines.append("        params: Optional[dict[str, Any]] = None,")
            lines.append("        json_data: Optional[Any] = None,")
            lines.append("    ) -> Any:")
            lines.append('        """Make an HTTP request."""')
            lines.append('        url = f"{self.base_url}{path}"')
            lines.append("")
            lines.append("        response = requests.request(")
            lines.append("            method, url, params=params, json=json_data, headers=self.headers")
            lines.append("        )")
            lines.append("")
            lines.append("        if response.status_code >= 400:")
            lines.append("            raise ApiError(")
            lines.append('                f"Request failed: {response.status_code}",')
            lines.append("                response.status_code,")
            lines.append("                response.text,")
            lines.append("            )")
            lines.append("")
            lines.append("        if response.status_code == 204:")
            lines.append("            return None")
            lines.append("")
            lines.append("        return response.json()")

        return lines

    def _generate_api_method(self, method: MethodDefinition, is_async: bool) -> list[str]:
        """Generate a single API method."""
        lines: list[str] = []
        async_kw = "async " if is_async else ""
        await_kw = "await " if is_async else ""

        # Docstring
        if self.config.include_documentation and method.description:
            lines.append(f"    {async_kw}def {method.name}(")
        else:
            lines.append(f"    {async_kw}def {method.name}(")

        # Parameters
        lines.append("        self,")
        for param in method.parameters:
            optional = " = None" if not param.required else ""
            lines.append(f"        {param.name}: {param.type_name}{optional},")

        if method.request_body_type:
            lines.append(f"        data: {method.request_body_type},")

        response_type = method.response_type or "Any"
        lines.append(f"    ) -> {response_type}:")

        # Docstring
        if self.config.include_documentation and method.description:
            lines.append(f'        """{method.description}')
            if method.deprecated:
                lines.append("")
                lines.append("        .. deprecated::")
            lines.append('        """')

        # Build path
        path = method.path
        path_params = [p for p in method.parameters if p.location == "path"]
        query_params = [p for p in method.parameters if p.location == "query"]

        for param in path_params:
            path = path.replace(f"{{{param.name}}}", f"{{{param.name}}}")

        lines.append(f'        path = f"{path}"')

        # Build params
        if query_params:
            lines.append("        params = {")
            for param in query_params:
                lines.append(f'            "{param.name}": {param.name},')
            lines.append("        }")
            lines.append("        params = {k: v for k, v in params.items() if v is not None}")
        else:
            lines.append("        params = None")

        # Make request
        json_arg = ", json_data=data.model_dump()" if method.request_body_type else ""

        lines.append(f'        result = {await_kw}self._request("{method.http_method}", path, params=params{json_arg})')

        # Return with type conversion if needed
        if response_type != "Any" and response_type not in ["str", "int", "float", "bool", "None"]:
            base_type = response_type.split("[")[0]
            if response_type.startswith("list["):
                lines.append(f"        return [{base_type.rstrip(']')}(**item) for item in result]")
            else:
                lines.append(f"        return {base_type}(**result) if result else None")
        else:
            lines.append("        return result")

        return lines

    def _generate_init_file(self, generated_files: list[GeneratedFile]) -> GeneratedFile:
        """Generate the __init__.py file."""
        lines: list[str] = []

        lines.append('"""')
        lines.append("API Client Package")
        lines.append("")
        lines.append("Generated by Forseti CodeGen")
        lines.append('"""')
        lines.append("")

        # Import from modules
        for file in generated_files:
            if file.path == "__init__.py":
                continue

            module_name = file.path.replace(".py", "")
            lines.append(f"from .{module_name} import *")

        content = "\n".join(lines)

        return GeneratedFile(
            path="__init__.py",
            content=content,
            language=TargetLanguage.PYTHON,
            file_type="index",
            line_count=len(lines),
        )

    def _write_files(self, files: list[GeneratedFile], output_dir: Path) -> None:
        """Write generated files to disk."""
        output_dir.mkdir(parents=True, exist_ok=True)

        for file in files:
            file_path = output_dir / file.path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(file.content, encoding="utf-8")
