"""
TypeScript Code Generator Service.

Generates TypeScript API client code from OpenAPI specifications.
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
from Asgard.Forseti.CodeGen.services._typescript_generator_helpers import (
    generate_ts_client_file,
    generate_types_file,
)
from Asgard.Forseti.CodeGen.services._typescript_generator_parse_helpers import (
    json_type_to_ts,
    parse_ts_parameters,
    ts_operation_to_method,
)


class TypeScriptGeneratorService:
    """
    Service for generating TypeScript API clients from OpenAPI specifications.

    Generates type-safe TypeScript code with support for fetch and axios.

    Usage:
        generator = TypeScriptGeneratorService()
        result = generator.generate("api.yaml")
        for file in result.generated_files:
            print(f"Generated: {file.path}")
    """

    def __init__(self, config: Optional[CodeGenConfig] = None):
        """
        Initialize the TypeScript generator.

        Args:
            config: Optional configuration for code generation.
        """
        self.config = config or CodeGenConfig(target_language=TargetLanguage.TYPESCRIPT)

        if not self.config.http_client:
            self.config.http_client = HttpClientType.FETCH

    def generate(
        self,
        spec_path: str | Path,
        output_dir: Optional[str | Path] = None
    ) -> CodeGenReport:
        """
        Generate TypeScript client from OpenAPI specification.

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

        try:
            spec_data = self._load_spec_file(spec_path)
        except Exception as e:
            errors.append(f"Failed to load specification: {e}")
            return CodeGenReport(
                success=False,
                source_spec=str(spec_path),
                target_language=TargetLanguage.TYPESCRIPT,
                errors=errors,
                generation_time_ms=(time.time() - start_time) * 1000,
            )

        types = self._parse_types(spec_data, warnings)
        methods = self._parse_methods(spec_data, types, warnings)

        generated_files: list[GeneratedFile] = []

        if self.config.generate_types:
            generated_files.append(generate_types_file(types, spec_data, self.config))

        if self.config.generate_client:
            generated_files.append(generate_ts_client_file(methods, types, spec_data, self.config))

        generated_files.append(self._generate_index_file(generated_files))

        total_lines = sum(f.line_count for f in generated_files)

        if output_dir:
            self._write_files(generated_files, Path(output_dir))

        return CodeGenReport(
            success=len(errors) == 0,
            source_spec=str(spec_path),
            target_language=TargetLanguage.TYPESCRIPT,
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
        if "enum" in schema:
            return TypeDefinition(
                name=name,
                description=schema.get("description"),
                is_enum=True,
                enum_values=schema["enum"],
            )

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
        type_name = json_type_to_ts(schema)
        is_array = schema.get("type") == "array"
        array_item_type = None

        if is_array and "items" in schema:
            array_item_type = json_type_to_ts(schema["items"])

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

            path_params = parse_ts_parameters(path_item.get("parameters", []))

            for method in http_methods:
                if method not in path_item:
                    continue

                operation = path_item[method]
                if not isinstance(operation, dict):
                    continue

                method_def = ts_operation_to_method(
                    path, method, operation, path_params,
                    self._generate_method_name, self._to_camel_case,
                )
                methods.append(method_def)

        return methods

    def _generate_method_name(self, path: str, method: str) -> str:
        """Generate a method name from path and HTTP method."""
        clean_path = path.replace("{", "By_").replace("}", "")
        clean_path = re.sub(r"[^a-zA-Z0-9_]", "_", clean_path)
        parts = [p for p in clean_path.split("_") if p]

        return f"{method}_{'_'.join(parts)}"

    def _to_camel_case(self, name: str) -> str:
        """Convert a name to camelCase."""
        parts = re.split(r"[-_]", name)
        if not parts:
            return name

        return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])

    def _generate_index_file(self, generated_files: list[GeneratedFile]) -> GeneratedFile:
        """Generate the index.ts file."""
        lines: list[str] = []

        lines.append("/**")
        lines.append(" * API Client - Index")
        lines.append(" * ")
        lines.append(" * Generated by Forseti CodeGen")
        lines.append(" */")
        lines.append("")

        for file in generated_files:
            if file.path == "index.ts":
                continue

            module_name = file.path.replace(".ts", "")
            lines.append(f"export * from './{module_name}';")

        content = "\n".join(lines)

        return GeneratedFile(
            path="index.ts",
            content=content,
            language=TargetLanguage.TYPESCRIPT,
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
