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

        # Set default HTTP client for TypeScript
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

        # Load specification
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

        # Parse types from spec
        types = self._parse_types(spec_data, warnings)

        # Parse methods from spec
        methods = self._parse_methods(spec_data, types, warnings)

        # Generate files
        generated_files: list[GeneratedFile] = []

        # Generate types file
        if self.config.generate_types:
            types_file = self._generate_types_file(types, spec_data)
            generated_files.append(types_file)

        # Generate client file
        if self.config.generate_client:
            client_file = self._generate_client_file(methods, types, spec_data)
            generated_files.append(client_file)

        # Generate index file
        index_file = self._generate_index_file(generated_files)
        generated_files.append(index_file)

        # Calculate totals
        total_lines = sum(f.line_count for f in generated_files)

        # Write files if output directory specified
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
        type_name = self._json_type_to_ts(schema)
        is_array = schema.get("type") == "array"
        array_item_type = None

        if is_array and "items" in schema:
            array_item_type = self._json_type_to_ts(schema["items"])

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

    def _json_type_to_ts(self, schema: dict[str, Any]) -> str:
        """Convert JSON Schema type to TypeScript type."""
        if "$ref" in schema:
            # Extract type name from reference
            ref = cast(str, schema["$ref"])
            return ref.split("/")[-1]

        schema_type = schema.get("type", "any")

        if schema_type == "string":
            format_type = schema.get("format")
            if format_type == "date" or format_type == "date-time":
                return "string"  # Could be Date, but string is safer
            return "string"
        elif schema_type == "integer" or schema_type == "number":
            return "number"
        elif schema_type == "boolean":
            return "boolean"
        elif schema_type == "array":
            items = schema.get("items", {})
            item_type = self._json_type_to_ts(items)
            return f"{item_type}[]"
        elif schema_type == "object":
            if "additionalProperties" in schema:
                value_type = self._json_type_to_ts(schema["additionalProperties"])
                return f"Record<string, {value_type}>"
            return "Record<string, unknown>"
        elif isinstance(schema_type, list):
            # Union type
            ts_types = [self._json_type_to_ts({"type": t}) for t in schema_type if t != "null"]
            if "null" in schema_type:
                ts_types.append("null")
            return " | ".join(ts_types)

        # Handle oneOf/anyOf
        if "oneOf" in schema or "anyOf" in schema:
            variants = schema.get("oneOf") or schema.get("anyOf", [])
            ts_types = [self._json_type_to_ts(v) for v in variants]
            return " | ".join(ts_types)

        return "unknown"

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
                type_name=self._json_type_to_ts(param.get("schema", {})),
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
        # Parse operation parameters
        op_params = self._parse_parameters(operation.get("parameters", []))
        all_params = path_params + op_params

        # Parse request body
        request_body_type = None
        if "requestBody" in operation:
            request_body = operation["requestBody"]
            content = request_body.get("content", {})
            for content_type, media in content.items():
                if "schema" in media:
                    request_body_type = self._json_type_to_ts(media["schema"])
                    break

        # Parse response type
        response_type = None
        responses = operation.get("responses", {})
        for status_code in ["200", "201", "default"]:
            if status_code in responses:
                response = responses[status_code]
                content = response.get("content", {})
                for content_type, media in content.items():
                    if "schema" in media:
                        response_type = self._json_type_to_ts(media["schema"])
                        break
                if response_type:
                    break

        # Generate method name
        method_name = operation.get("operationId")
        if not method_name:
            method_name = self._generate_method_name(path, http_method)

        return MethodDefinition(
            name=self._to_camel_case(method_name),
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
        # Clean path
        clean_path = path.replace("{", "By_").replace("}", "")
        clean_path = re.sub(r"[^a-zA-Z0-9_]", "_", clean_path)
        parts = [p for p in clean_path.split("_") if p]

        return f"{method}_{'_'.join(parts)}"

    def _to_camel_case(self, name: str) -> str:
        """Convert a name to camelCase."""
        # Handle snake_case and kebab-case
        parts = re.split(r"[-_]", name)
        if not parts:
            return name

        return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])

    def _to_pascal_case(self, name: str) -> str:
        """Convert a name to PascalCase."""
        parts = re.split(r"[-_]", name)
        return "".join(p.capitalize() for p in parts)

    def _generate_types_file(
        self,
        types: dict[str, TypeDefinition],
        spec_data: dict[str, Any]
    ) -> GeneratedFile:
        """Generate the types.ts file."""
        lines: list[str] = []

        # File header
        info = spec_data.get("info", {})
        lines.append("/**")
        lines.append(f" * {info.get('title', 'API')} - Type Definitions")
        lines.append(" * ")
        lines.append(" * Generated by Forseti CodeGen")
        if info.get("version"):
            lines.append(f" * API Version: {info.get('version')}")
        lines.append(" */")
        lines.append("")

        # Generate types
        for type_name, type_def in types.items():
            type_code = self._generate_type(type_def)
            lines.extend(type_code)
            lines.append("")

        content = "\n".join(lines)

        return GeneratedFile(
            path="types.ts",
            content=content,
            language=TargetLanguage.TYPESCRIPT,
            file_type="types",
            line_count=len(lines),
        )

    def _generate_type(self, type_def: TypeDefinition) -> list[str]:
        """Generate TypeScript code for a type definition."""
        lines: list[str] = []

        # Documentation
        if type_def.description and self.config.include_documentation:
            lines.append("/**")
            lines.append(f" * {type_def.description}")
            lines.append(" */")

        if type_def.is_enum:
            # Generate enum
            lines.append(f"export type {type_def.name} = ")
            enum_values = [
                f'"{v}"' if isinstance(v, str) else str(v)
                for v in type_def.enum_values
            ]
            lines[-1] += " | ".join(enum_values) + ";"
        else:
            # Generate interface
            lines.append(f"export interface {type_def.name} {{")

            for prop_name, prop_def in type_def.properties.items():
                # Property documentation
                if prop_def.description and self.config.include_documentation:
                    lines.append(f"  /** {prop_def.description} */")

                # Property definition
                optional = "?" if not prop_def.required else ""
                nullable = " | null" if prop_def.nullable else ""

                lines.append(f"  {prop_name}{optional}: {prop_def.type_name}{nullable};")

            lines.append("}")

        return lines

    def _generate_client_file(
        self,
        methods: list[MethodDefinition],
        types: dict[str, TypeDefinition],
        spec_data: dict[str, Any]
    ) -> GeneratedFile:
        """Generate the client.ts file."""
        lines: list[str] = []
        info = spec_data.get("info", {})

        # File header
        lines.append("/**")
        lines.append(f" * {info.get('title', 'API')} - API Client")
        lines.append(" * ")
        lines.append(" * Generated by Forseti CodeGen")
        lines.append(" */")
        lines.append("")

        # Imports
        type_imports = self._get_type_imports(methods, types)
        if type_imports:
            lines.append(f"import {{ {', '.join(sorted(type_imports))} }} from './types';")
            lines.append("")

        # Client configuration interface
        lines.append("export interface ApiClientConfig {")
        lines.append("  baseUrl: string;")
        lines.append("  headers?: Record<string, string>;")
        if self.config.http_client == HttpClientType.FETCH:
            lines.append("  fetchFn?: typeof fetch;")
        lines.append("}")
        lines.append("")

        # Error class
        lines.append("export class ApiError extends Error {")
        lines.append("  constructor(")
        lines.append("    message: string,")
        lines.append("    public status: number,")
        lines.append("    public response?: unknown")
        lines.append("  ) {")
        lines.append("    super(message);")
        lines.append("    this.name = 'ApiError';")
        lines.append("  }")
        lines.append("}")
        lines.append("")

        # Client class
        lines.append("export class ApiClient {")
        lines.append("  private baseUrl: string;")
        lines.append("  private headers: Record<string, string>;")
        if self.config.http_client == HttpClientType.FETCH:
            lines.append("  private fetchFn: typeof fetch;")
        lines.append("")

        # Constructor
        lines.append("  constructor(config: ApiClientConfig) {")
        lines.append("    this.baseUrl = config.baseUrl.replace(/\\/$/, '');")
        lines.append("    this.headers = {")
        lines.append("      'Content-Type': 'application/json',")
        lines.append("      ...config.headers,")
        lines.append("    };")
        if self.config.http_client == HttpClientType.FETCH:
            lines.append("    this.fetchFn = config.fetchFn || fetch;")
        lines.append("  }")
        lines.append("")

        # Request method
        lines.extend(self._generate_request_method())
        lines.append("")

        # API methods
        for method in methods:
            method_code = self._generate_api_method(method)
            lines.extend(method_code)
            lines.append("")

        lines.append("}")
        lines.append("")

        # Export default
        lines.append("export default ApiClient;")

        content = "\n".join(lines)

        return GeneratedFile(
            path="client.ts",
            content=content,
            language=TargetLanguage.TYPESCRIPT,
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
            if method.request_body_type and method.request_body_type in types:
                imports.add(method.request_body_type)

            if method.response_type:
                # Handle array types
                response_type = method.response_type.rstrip("[]")
                if response_type in types:
                    imports.add(response_type)

            for param in method.parameters:
                param_type = param.type_name.rstrip("[]")
                if param_type in types:
                    imports.add(param_type)

        return imports

    def _generate_request_method(self) -> list[str]:
        """Generate the private request method."""
        lines: list[str] = []

        if self.config.http_client == HttpClientType.FETCH:
            lines.append("  private async request<T>(")
            lines.append("    method: string,")
            lines.append("    path: string,")
            lines.append("    options: {")
            lines.append("      query?: Record<string, string | number | boolean | undefined>;")
            lines.append("      body?: unknown;")
            lines.append("      headers?: Record<string, string>;")
            lines.append("    } = {}")
            lines.append("  ): Promise<T> {")
            lines.append("    let url = `${this.baseUrl}${path}`;")
            lines.append("")
            lines.append("    if (options.query) {")
            lines.append("      const params = new URLSearchParams();")
            lines.append("      for (const [key, value] of Object.entries(options.query)) {")
            lines.append("        if (value !== undefined) {")
            lines.append("          params.append(key, String(value));")
            lines.append("        }")
            lines.append("      }")
            lines.append("      const queryString = params.toString();")
            lines.append("      if (queryString) {")
            lines.append("        url += `?${queryString}`;")
            lines.append("      }")
            lines.append("    }")
            lines.append("")
            lines.append("    const response = await this.fetchFn(url, {")
            lines.append("      method,")
            lines.append("      headers: { ...this.headers, ...options.headers },")
            lines.append("      body: options.body ? JSON.stringify(options.body) : undefined,")
            lines.append("    });")
            lines.append("")
            lines.append("    if (!response.ok) {")
            lines.append("      const errorBody = await response.text().catch(() => undefined);")
            lines.append("      throw new ApiError(")
            lines.append("        `Request failed: ${response.status} ${response.statusText}`,")
            lines.append("        response.status,")
            lines.append("        errorBody")
            lines.append("      );")
            lines.append("    }")
            lines.append("")
            lines.append("    if (response.status === 204) {")
            lines.append("      return undefined as T;")
            lines.append("    }")
            lines.append("")
            lines.append("    return response.json();")
            lines.append("  }")

        return lines

    def _generate_api_method(self, method: MethodDefinition) -> list[str]:
        """Generate a single API method."""
        lines: list[str] = []

        # Documentation
        if self.config.include_documentation and method.description:
            lines.append("  /**")
            lines.append(f"   * {method.description}")
            if method.deprecated:
                lines.append("   * @deprecated")
            for param in method.parameters:
                if param.description:
                    lines.append(f"   * @param {param.name} - {param.description}")
            lines.append("   */")

        # Method signature
        params = self._generate_method_params(method)
        return_type = method.response_type or "void"

        lines.append(f"  async {method.name}({params}): Promise<{return_type}> {{")

        # Build path with parameters
        path_params = [p for p in method.parameters if p.location == "path"]
        query_params = [p for p in method.parameters if p.location == "query"]

        path = method.path
        for param in path_params:
            path = path.replace(f"{{{param.name}}}", f"${{{param.name}}}")

        lines.append(f"    const path = `{path}`;")

        # Build query parameters
        if query_params:
            lines.append("    const query = {")
            for param in query_params:
                lines.append(f"      {param.name},")
            lines.append("    };")

        # Make request
        request_options = []
        if query_params:
            request_options.append("query")
        if method.request_body_type:
            request_options.append("body: data")

        options_str = ", { " + ", ".join(request_options) + " }" if request_options else ""

        lines.append(f"    return this.request<{return_type}>('{method.http_method}', path{options_str});")
        lines.append("  }")

        return lines

    def _generate_method_params(self, method: MethodDefinition) -> str:
        """Generate method parameter list."""
        params: list[str] = []

        # Path and query parameters
        for param in method.parameters:
            optional = "" if param.required else "?"
            params.append(f"{param.name}{optional}: {param.type_name}")

        # Request body
        if method.request_body_type:
            params.append(f"data: {method.request_body_type}")

        return ", ".join(params)

    def _generate_index_file(self, generated_files: list[GeneratedFile]) -> GeneratedFile:
        """Generate the index.ts file."""
        lines: list[str] = []

        lines.append("/**")
        lines.append(" * API Client - Index")
        lines.append(" * ")
        lines.append(" * Generated by Forseti CodeGen")
        lines.append(" */")
        lines.append("")

        # Re-export from all generated files
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
