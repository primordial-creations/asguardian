"""
Go Code Generator Service.

Generates Go API client code from OpenAPI specifications.
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


class GolangGeneratorService:
    """
    Service for generating Go API clients from OpenAPI specifications.

    Generates idiomatic Go code using net/http.

    Usage:
        generator = GolangGeneratorService()
        result = generator.generate("api.yaml")
        for file in result.generated_files:
            print(f"Generated: {file.path}")
    """

    def __init__(self, config: Optional[CodeGenConfig] = None):
        """
        Initialize the Go generator.

        Args:
            config: Optional configuration for code generation.
        """
        self.config = config or CodeGenConfig(target_language=TargetLanguage.GOLANG)

        # Set default HTTP client for Go
        if not self.config.http_client:
            self.config.http_client = HttpClientType.NET_HTTP

    def generate(
        self,
        spec_path: str | Path,
        output_dir: Optional[str | Path] = None
    ) -> CodeGenReport:
        """
        Generate Go client from OpenAPI specification.

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
                target_language=TargetLanguage.GOLANG,
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

        # Calculate totals
        total_lines = sum(f.line_count for f in generated_files)

        # Write files if output directory specified
        if output_dir:
            self._write_files(generated_files, Path(output_dir))

        return CodeGenReport(
            success=len(errors) == 0,
            source_spec=str(spec_path),
            target_language=TargetLanguage.GOLANG,
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
        type_name = self._json_type_to_go(schema, required)
        is_array = schema.get("type") == "array"
        array_item_type = None

        if is_array and "items" in schema:
            array_item_type = self._json_type_to_go(schema["items"], True)

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

    def _json_type_to_go(self, schema: dict[str, Any], required: bool = True) -> str:
        """Convert JSON Schema type to Go type."""
        if "$ref" in schema:
            ref = schema["$ref"]
            type_name = ref.split("/")[-1]
            return f"*{type_name}" if not required else type_name

        schema_type = schema.get("type", "interface{}")
        nullable = schema.get("nullable", False)

        if schema_type == "string":
            format_type = schema.get("format")
            if format_type == "date" or format_type == "date-time":
                base = "time.Time"
            else:
                base = "string"
            return f"*{base}" if nullable or not required else base

        elif schema_type == "integer":
            format_type = schema.get("format")
            if format_type == "int64":
                base = "int64"
            elif format_type == "int32":
                base = "int32"
            else:
                base = "int"
            return f"*{base}" if nullable or not required else base

        elif schema_type == "number":
            format_type = schema.get("format")
            if format_type == "float":
                base = "float32"
            else:
                base = "float64"
            return f"*{base}" if nullable or not required else base

        elif schema_type == "boolean":
            return "*bool" if nullable or not required else "bool"

        elif schema_type == "array":
            items = schema.get("items", {})
            item_type = self._json_type_to_go(items, True)
            return f"[]{item_type}"

        elif schema_type == "object":
            if "additionalProperties" in schema:
                value_type = self._json_type_to_go(schema["additionalProperties"], True)
                return f"map[string]{value_type}"
            return "map[string]interface{}"

        return "interface{}"

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
                type_name=self._json_type_to_go(param.get("schema", {}), param.get("required", False)),
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
                    request_body_type = self._json_type_to_go(media["schema"])
                    break

        response_type = None
        responses = operation.get("responses", {})
        for status_code in ["200", "201", "default"]:
            if status_code in responses:
                response = responses[status_code]
                content = response.get("content", {})
                for content_type, media in content.items():
                    if "schema" in media:
                        response_type = self._json_type_to_go(media["schema"])
                        break
                if response_type:
                    break

        method_name = operation.get("operationId")
        if not method_name:
            method_name = self._generate_method_name(path, http_method)

        return MethodDefinition(
            name=self._to_pascal_case(method_name),
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
        clean_path = path.replace("{", "By").replace("}", "")
        clean_path = re.sub(r"[^a-zA-Z0-9]", "_", clean_path)
        parts = [p for p in clean_path.split("_") if p]

        return f"{method}_{'_'.join(parts)}"

    def _to_pascal_case(self, name: str) -> str:
        """Convert a name to PascalCase."""
        parts = re.split(r"[-_]", name)
        return "".join(p.capitalize() for p in parts)

    def _to_camel_case(self, name: str) -> str:
        """Convert a name to camelCase."""
        pascal = self._to_pascal_case(name)
        return pascal[0].lower() + pascal[1:] if pascal else ""

    def _generate_models_file(
        self,
        types: dict[str, TypeDefinition],
        spec_data: dict[str, Any]
    ) -> GeneratedFile:
        """Generate the models.go file."""
        lines: list[str] = []
        info = spec_data.get("info", {})

        # Package declaration
        lines.append(f"// {info.get('title', 'API')} - Model Definitions")
        lines.append("//")
        lines.append("// Generated by Forseti CodeGen")
        if info.get("version"):
            lines.append(f"// API Version: {info.get('version')}")
        lines.append("")
        lines.append(f"package {self.config.package_name}")
        lines.append("")

        # Check if we need time import
        needs_time = False
        for type_def in types.values():
            for prop_def in type_def.properties.values():
                if "time.Time" in prop_def.type_name:
                    needs_time = True
                    break

        # Imports
        if needs_time:
            lines.append('import "time"')
            lines.append("")

        # Generate types
        for type_name, type_def in types.items():
            type_code = self._generate_type(type_def)
            lines.extend(type_code)
            lines.append("")

        content = "\n".join(lines)

        return GeneratedFile(
            path="models.go",
            content=content,
            language=TargetLanguage.GOLANG,
            file_type="models",
            line_count=len(lines),
        )

    def _generate_type(self, type_def: TypeDefinition) -> list[str]:
        """Generate Go code for a type definition."""
        lines: list[str] = []

        if type_def.description and self.config.include_documentation:
            lines.append(f"// {type_def.name} {type_def.description}")

        if type_def.is_enum:
            # Generate string enum type
            lines.append(f"type {type_def.name} string")
            lines.append("")
            lines.append("const (")
            for value in type_def.enum_values:
                if isinstance(value, str):
                    const_name = f"{type_def.name}{value.replace('-', '').replace('_', '').title()}"
                    lines.append(f'\t{const_name} {type_def.name} = "{value}"')
                else:
                    const_name = f"{type_def.name}{value}"
                    lines.append(f"\t{const_name} {type_def.name} = {value}")
            lines.append(")")
        else:
            # Generate struct
            lines.append(f"type {type_def.name} struct {{")

            for prop_name, prop_def in type_def.properties.items():
                go_name = self._to_pascal_case(prop_name)
                json_tag = f'`json:"{prop_name},omitempty"`'

                if prop_def.description and self.config.include_documentation:
                    lines.append(f"\t// {prop_def.description}")

                lines.append(f"\t{go_name} {prop_def.type_name} {json_tag}")

            lines.append("}")

        return lines

    def _generate_client_file(
        self,
        methods: list[MethodDefinition],
        types: dict[str, TypeDefinition],
        spec_data: dict[str, Any]
    ) -> GeneratedFile:
        """Generate the client.go file."""
        lines: list[str] = []
        info = spec_data.get("info", {})

        # Package declaration
        lines.append(f"// {info.get('title', 'API')} - API Client")
        lines.append("//")
        lines.append("// Generated by Forseti CodeGen")
        lines.append("")
        lines.append(f"package {self.config.package_name}")
        lines.append("")

        # Imports
        lines.append("import (")
        lines.append('\t"bytes"')
        lines.append('\t"encoding/json"')
        lines.append('\t"fmt"')
        lines.append('\t"io"')
        lines.append('\t"net/http"')
        lines.append('\t"net/url"')
        lines.append('\t"strings"')
        lines.append(")")
        lines.append("")

        # ApiError type
        lines.append("// ApiError represents an API error response")
        lines.append("type ApiError struct {")
        lines.append("\tStatusCode int")
        lines.append("\tMessage    string")
        lines.append("\tBody       string")
        lines.append("}")
        lines.append("")
        lines.append("func (e *ApiError) Error() string {")
        lines.append('\treturn fmt.Sprintf("API error %d: %s", e.StatusCode, e.Message)')
        lines.append("}")
        lines.append("")

        # Client struct
        lines.append("// Client is the API client")
        lines.append("type Client struct {")
        lines.append("\tbaseURL    string")
        lines.append("\thttpClient *http.Client")
        lines.append("\theaders    map[string]string")
        lines.append("}")
        lines.append("")

        # ClientOption type
        lines.append("// ClientOption configures the client")
        lines.append("type ClientOption func(*Client)")
        lines.append("")

        # WithHTTPClient option
        lines.append("// WithHTTPClient sets a custom HTTP client")
        lines.append("func WithHTTPClient(client *http.Client) ClientOption {")
        lines.append("\treturn func(c *Client) {")
        lines.append("\t\tc.httpClient = client")
        lines.append("\t}")
        lines.append("}")
        lines.append("")

        # WithHeader option
        lines.append("// WithHeader adds a custom header")
        lines.append("func WithHeader(key, value string) ClientOption {")
        lines.append("\treturn func(c *Client) {")
        lines.append("\t\tc.headers[key] = value")
        lines.append("\t}")
        lines.append("}")
        lines.append("")

        # NewClient constructor
        lines.append("// NewClient creates a new API client")
        lines.append("func NewClient(baseURL string, opts ...ClientOption) *Client {")
        lines.append("\tc := &Client{")
        lines.append('\t\tbaseURL:    strings.TrimSuffix(baseURL, "/"),')
        lines.append("\t\thttpClient: http.DefaultClient,")
        lines.append("\t\theaders: map[string]string{")
        lines.append('\t\t\t"Content-Type": "application/json",')
        lines.append("\t\t},")
        lines.append("\t}")
        lines.append("\tfor _, opt := range opts {")
        lines.append("\t\topt(c)")
        lines.append("\t}")
        lines.append("\treturn c")
        lines.append("}")
        lines.append("")

        # doRequest helper method
        lines.extend(self._generate_do_request_method())
        lines.append("")

        # API methods
        for method in methods:
            method_code = self._generate_api_method(method)
            lines.extend(method_code)
            lines.append("")

        content = "\n".join(lines)

        return GeneratedFile(
            path="client.go",
            content=content,
            language=TargetLanguage.GOLANG,
            file_type="client",
            line_count=len(lines),
        )

    def _generate_do_request_method(self) -> list[str]:
        """Generate the doRequest helper method."""
        lines: list[str] = []

        lines.append("func (c *Client) doRequest(method, path string, query url.Values, body interface{}, result interface{}) error {")
        lines.append('\tfullURL := c.baseURL + path')
        lines.append('\tif len(query) > 0 {')
        lines.append('\t\tfullURL += "?" + query.Encode()')
        lines.append("\t}")
        lines.append("")
        lines.append("\tvar bodyReader io.Reader")
        lines.append("\tif body != nil {")
        lines.append("\t\tjsonBody, err := json.Marshal(body)")
        lines.append("\t\tif err != nil {")
        lines.append("\t\t\treturn err")
        lines.append("\t\t}")
        lines.append("\t\tbodyReader = bytes.NewReader(jsonBody)")
        lines.append("\t}")
        lines.append("")
        lines.append("\treq, err := http.NewRequest(method, fullURL, bodyReader)")
        lines.append("\tif err != nil {")
        lines.append("\t\treturn err")
        lines.append("\t}")
        lines.append("")
        lines.append("\tfor key, value := range c.headers {")
        lines.append("\t\treq.Header.Set(key, value)")
        lines.append("\t}")
        lines.append("")
        lines.append("\tresp, err := c.httpClient.Do(req)")
        lines.append("\tif err != nil {")
        lines.append("\t\treturn err")
        lines.append("\t}")
        lines.append("\tdefer resp.Body.Close()")
        lines.append("")
        lines.append("\tif resp.StatusCode >= 400 {")
        lines.append("\t\trespBody, _ := io.ReadAll(resp.Body)")
        lines.append("\t\treturn &ApiError{")
        lines.append("\t\t\tStatusCode: resp.StatusCode,")
        lines.append('\t\t\tMessage:    fmt.Sprintf("request failed: %s", resp.Status),')
        lines.append("\t\t\tBody:       string(respBody),")
        lines.append("\t\t}")
        lines.append("\t}")
        lines.append("")
        lines.append("\tif resp.StatusCode == http.StatusNoContent || result == nil {")
        lines.append("\t\treturn nil")
        lines.append("\t}")
        lines.append("")
        lines.append("\treturn json.NewDecoder(resp.Body).Decode(result)")
        lines.append("}")

        return lines

    def _generate_api_method(self, method: MethodDefinition) -> list[str]:
        """Generate a single API method."""
        lines: list[str] = []

        # Documentation
        if self.config.include_documentation and method.description:
            lines.append(f"// {method.name} {method.description}")
            if method.deprecated:
                lines.append("// Deprecated: This method is deprecated")

        # Method signature
        params = self._generate_method_params(method)
        return_type = self._get_return_type(method)

        lines.append(f"func (c *Client) {method.name}({params}) ({return_type}) {{")

        # Build path
        path = method.path
        path_params = [p for p in method.parameters if p.location == "path"]
        query_params = [p for p in method.parameters if p.location == "query"]

        # Replace path parameters
        for param in path_params:
            go_name = self._to_camel_case(param.name)
            path = path.replace(f"{{{param.name}}}", f"%v")
            if path.count("%v") > 0:
                lines.append(f'\tpath := fmt.Sprintf("{path}", {go_name})')
                break
        else:
            lines.append(f'\tpath := "{path}"')

        # Build query parameters
        if query_params:
            lines.append("\tquery := url.Values{}")
            for param in query_params:
                go_name = self._to_camel_case(param.name)
                if "*" in param.type_name:
                    lines.append(f"\tif {go_name} != nil {{")
                    lines.append(f'\t\tquery.Set("{param.name}", fmt.Sprintf("%v", *{go_name}))')
                    lines.append("\t}")
                else:
                    lines.append(f'\tquery.Set("{param.name}", fmt.Sprintf("%v", {go_name}))')
        else:
            lines.append("\tquery := url.Values{}")

        # Make request
        body_arg = "nil"
        if method.request_body_type:
            body_arg = "body"

        result_arg = "nil"
        if method.response_type and method.response_type != "":
            lines.append(f"\tvar result {method.response_type}")
            result_arg = "&result"

        lines.append(f'\terr := c.doRequest("{method.http_method}", path, query, {body_arg}, {result_arg})')

        if method.response_type:
            lines.append("\treturn result, err")
        else:
            lines.append("\treturn err")

        lines.append("}")

        return lines

    def _generate_method_params(self, method: MethodDefinition) -> str:
        """Generate method parameter list."""
        params: list[str] = []

        # Path and query parameters
        for param in method.parameters:
            go_name = self._to_camel_case(param.name)
            params.append(f"{go_name} {param.type_name}")

        # Request body
        if method.request_body_type:
            params.append(f"body {method.request_body_type}")

        return ", ".join(params)

    def _get_return_type(self, method: MethodDefinition) -> str:
        """Get the return type for a method."""
        if method.response_type:
            return f"{method.response_type}, error"
        return "error"

    def _write_files(self, files: list[GeneratedFile], output_dir: Path) -> None:
        """Write generated files to disk."""
        output_dir.mkdir(parents=True, exist_ok=True)

        for file in files:
            file_path = output_dir / file.path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(file.content, encoding="utf-8")
