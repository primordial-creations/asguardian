"""
OpenAPI Specification Converter Service.

Converts between OpenAPI specification versions.
"""

import re
from pathlib import Path
from typing import Any, Optional

from Asgard.Forseti.OpenAPI.models.openapi_models import (
    OpenAPIConfig,
    OpenAPISpec,
    OpenAPIVersion,
)
from Asgard.Forseti.OpenAPI.utilities.openapi_utils import (
    load_spec_file,
    save_spec_file,
    detect_openapi_version,
)


class SpecConverterService:
    """
    Service for converting OpenAPI specifications between versions.

    Supports conversion between Swagger 2.0, OpenAPI 3.0, and OpenAPI 3.1.

    Usage:
        service = SpecConverterService()
        converted = service.convert("swagger.yaml", OpenAPIVersion.V3_1)
        service.save("openapi.yaml", converted)
    """

    def __init__(self, config: Optional[OpenAPIConfig] = None):
        """
        Initialize the converter service.

        Args:
            config: Optional configuration for conversion behavior.
        """
        self.config = config or OpenAPIConfig()

    def convert(
        self,
        spec_path: str | Path,
        target_version: OpenAPIVersion
    ) -> dict[str, Any]:
        """
        Convert a specification to a target version.

        Args:
            spec_path: Path to the source specification.
            target_version: Target OpenAPI version.

        Returns:
            Converted specification dictionary.

        Raises:
            FileNotFoundError: If the specification file does not exist.
            ValueError: If conversion is not supported.
        """
        spec_path = Path(spec_path)
        if not spec_path.exists():
            raise FileNotFoundError(f"Specification file not found: {spec_path}")

        spec_data = load_spec_file(spec_path)
        return self.convert_data(spec_data, target_version)

    def convert_data(
        self,
        spec_data: dict[str, Any],
        target_version: OpenAPIVersion
    ) -> dict[str, Any]:
        """
        Convert specification data to a target version.

        Args:
            spec_data: Source specification dictionary.
            target_version: Target OpenAPI version.

        Returns:
            Converted specification dictionary.

        Raises:
            ValueError: If conversion is not supported.
        """
        source_version = detect_openapi_version(spec_data)

        if source_version == target_version:
            return spec_data

        # Conversion paths
        if source_version == OpenAPIVersion.V2_0:
            if target_version == OpenAPIVersion.V3_0:
                return self._convert_2_to_3_0(spec_data)
            elif target_version == OpenAPIVersion.V3_1:
                converted = self._convert_2_to_3_0(spec_data)
                return self._convert_3_0_to_3_1(converted)

        elif source_version == OpenAPIVersion.V3_0:
            if target_version == OpenAPIVersion.V2_0:
                return self._convert_3_0_to_2(spec_data)
            elif target_version == OpenAPIVersion.V3_1:
                return self._convert_3_0_to_3_1(spec_data)

        elif source_version == OpenAPIVersion.V3_1:
            if target_version == OpenAPIVersion.V2_0:
                converted = self._convert_3_1_to_3_0(spec_data)
                return self._convert_3_0_to_2(converted)
            elif target_version == OpenAPIVersion.V3_0:
                return self._convert_3_1_to_3_0(spec_data)

        raise ValueError(
            f"Conversion from {source_version} to {target_version} is not supported"
        )

    def _convert_2_to_3_0(self, spec_data: dict[str, Any]) -> dict[str, Any]:
        """Convert Swagger 2.0 to OpenAPI 3.0."""
        converted = {
            "openapi": "3.0.3",
            "info": spec_data.get("info", {}),
            "paths": {},
            "components": {
                "schemas": {},
                "securitySchemes": {},
            },
        }

        # Convert host/basePath/schemes to servers
        host = spec_data.get("host", "localhost")
        base_path = spec_data.get("basePath", "/")
        schemes = spec_data.get("schemes", ["https"])
        converted["servers"] = [
            {"url": f"{scheme}://{host}{base_path}"}
            for scheme in schemes
        ]

        # Convert definitions to components/schemas
        definitions = spec_data.get("definitions", {})
        for name, schema in definitions.items():
            converted["components"]["schemas"][name] = self._convert_schema_2_to_3(schema)

        # Convert paths
        paths = spec_data.get("paths", {})
        for path, path_item in paths.items():
            converted["paths"][path] = self._convert_path_item_2_to_3(path_item)

        # Convert security definitions
        security_defs = spec_data.get("securityDefinitions", {})
        for name, sec_def in security_defs.items():
            converted["components"]["securitySchemes"][name] = (
                self._convert_security_def_2_to_3(sec_def)
            )

        # Copy security
        if "security" in spec_data:
            converted["security"] = spec_data["security"]

        # Copy tags
        if "tags" in spec_data:
            converted["tags"] = spec_data["tags"]

        # Copy external docs
        if "externalDocs" in spec_data:
            converted["externalDocs"] = spec_data["externalDocs"]

        return converted

    def _convert_schema_2_to_3(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Convert a schema from Swagger 2.0 to OpenAPI 3.0."""
        converted = dict(schema)

        # Convert $ref paths
        if "$ref" in converted:
            ref = converted["$ref"]
            if ref.startswith("#/definitions/"):
                converted["$ref"] = ref.replace("#/definitions/", "#/components/schemas/")

        # Recursively convert nested schemas
        for key in ["items", "additionalProperties"]:
            if key in converted and isinstance(converted[key], dict):
                converted[key] = self._convert_schema_2_to_3(converted[key])

        if "properties" in converted:
            for prop_name, prop_schema in converted["properties"].items():
                if isinstance(prop_schema, dict):
                    converted["properties"][prop_name] = self._convert_schema_2_to_3(prop_schema)

        for key in ["allOf", "oneOf", "anyOf"]:
            if key in converted:
                converted[key] = [
                    self._convert_schema_2_to_3(s) if isinstance(s, dict) else s
                    for s in converted[key]
                ]

        return converted

    def _convert_path_item_2_to_3(self, path_item: dict[str, Any]) -> dict[str, Any]:
        """Convert a path item from Swagger 2.0 to OpenAPI 3.0."""
        converted: dict[str, Any] = {}
        http_methods = ["get", "put", "post", "delete", "options", "head", "patch"]

        for method in http_methods:
            if method in path_item:
                converted[method] = self._convert_operation_2_to_3(path_item[method])

        # Copy non-operation fields
        for key in ["summary", "description"]:
            if key in path_item:
                converted[key] = path_item[key]

        # Convert path-level parameters
        if "parameters" in path_item:
            converted["parameters"] = [
                self._convert_parameter_2_to_3(p)
                for p in path_item["parameters"]
                if p.get("in") != "body"
            ]

        return converted

    def _convert_operation_2_to_3(self, operation: dict[str, Any]) -> dict[str, Any]:
        """Convert an operation from Swagger 2.0 to OpenAPI 3.0."""
        converted: dict[str, Any] = {
            "responses": {},
        }

        # Copy basic fields
        for key in ["operationId", "summary", "description", "tags", "deprecated", "security"]:
            if key in operation:
                converted[key] = operation[key]

        # Convert parameters and extract request body
        parameters = []
        request_body = None

        for param in operation.get("parameters", []):
            if param.get("in") == "body":
                request_body = {
                    "description": param.get("description", ""),
                    "required": param.get("required", False),
                    "content": {
                        "application/json": {
                            "schema": self._convert_schema_2_to_3(param.get("schema", {})),
                        }
                    }
                }
            elif param.get("in") == "formData":
                if request_body is None:
                    consumes = operation.get("consumes", ["application/x-www-form-urlencoded"])
                    media_type = consumes[0] if consumes else "application/x-www-form-urlencoded"
                    request_body = {
                        "content": {
                            media_type: {
                                "schema": {
                                    "type": "object",
                                    "properties": {},
                                }
                            }
                        }
                    }
                content_type = list(request_body["content"].keys())[0]
                schema = request_body["content"][content_type]["schema"]
                schema["properties"][param["name"]] = {
                    "type": param.get("type", "string"),
                }
                if param.get("format"):
                    schema["properties"][param["name"]]["format"] = param["format"]
                if param.get("required"):
                    if "required" not in schema:
                        schema["required"] = []
                    schema["required"].append(param["name"])
            else:
                parameters.append(self._convert_parameter_2_to_3(param))

        if parameters:
            converted["parameters"] = parameters
        if request_body:
            converted["requestBody"] = request_body

        # Convert responses
        produces = operation.get("produces", ["application/json"])
        media_type = produces[0] if produces else "application/json"

        for status_code, response in operation.get("responses", {}).items():
            converted_response = {
                "description": response.get("description", ""),
            }
            if "schema" in response:
                converted_response["content"] = {
                    media_type: {
                        "schema": self._convert_schema_2_to_3(response["schema"]),
                    }
                }
            if "headers" in response:
                converted_response["headers"] = response["headers"]
            converted["responses"][status_code] = converted_response

        return converted

    def _convert_parameter_2_to_3(self, param: dict[str, Any]) -> dict[str, Any]:
        """Convert a parameter from Swagger 2.0 to OpenAPI 3.0."""
        converted = {
            "name": param.get("name"),
            "in": param.get("in"),
        }

        if "description" in param:
            converted["description"] = param["description"]
        if "required" in param:
            converted["required"] = param["required"]

        # Build schema from parameter properties
        schema: dict[str, Any] = {}
        for key in ["type", "format", "enum", "default", "minimum", "maximum",
                    "minLength", "maxLength", "pattern", "items"]:
            if key in param:
                schema[key] = param[key]

        if schema:
            converted["schema"] = schema

        return converted

    def _convert_security_def_2_to_3(self, sec_def: dict[str, Any]) -> dict[str, Any]:
        """Convert a security definition from Swagger 2.0 to OpenAPI 3.0."""
        sec_type = sec_def.get("type")

        if sec_type == "basic":
            return {
                "type": "http",
                "scheme": "basic",
            }
        elif sec_type == "apiKey":
            return {
                "type": "apiKey",
                "in": sec_def.get("in"),
                "name": sec_def.get("name"),
            }
        elif sec_type == "oauth2":
            flows = {}
            flow_type = sec_def.get("flow")
            flow_data = {
                "scopes": sec_def.get("scopes", {}),
            }
            if "authorizationUrl" in sec_def:
                flow_data["authorizationUrl"] = sec_def["authorizationUrl"]
            if "tokenUrl" in sec_def:
                flow_data["tokenUrl"] = sec_def["tokenUrl"]

            flow_map = {
                "implicit": "implicit",
                "password": "password",
                "application": "clientCredentials",
                "accessCode": "authorizationCode",
            }
            if flow_type in flow_map:
                flows[flow_map[flow_type]] = flow_data

            return {
                "type": "oauth2",
                "flows": flows,
            }

        return sec_def

    def _convert_3_0_to_3_1(self, spec_data: dict[str, Any]) -> dict[str, Any]:
        """Convert OpenAPI 3.0 to 3.1."""
        converted = dict(spec_data)
        converted["openapi"] = "3.1.0"

        # Convert nullable to type array
        self._convert_nullable_to_type_array(converted)

        # Convert exclusiveMinimum/Maximum to numbers
        self._convert_exclusive_bounds(converted)

        return converted

    def _convert_3_1_to_3_0(self, spec_data: dict[str, Any]) -> dict[str, Any]:
        """Convert OpenAPI 3.1 to 3.0."""
        converted = dict(spec_data)
        converted["openapi"] = "3.0.3"

        # Convert type arrays back to nullable
        self._convert_type_array_to_nullable(converted)

        return converted

    def _convert_3_0_to_2(self, spec_data: dict[str, Any]) -> dict[str, Any]:
        """Convert OpenAPI 3.0 to Swagger 2.0."""
        converted = {
            "swagger": "2.0",
            "info": spec_data.get("info", {}),
            "paths": {},
            "definitions": {},
            "securityDefinitions": {},
        }

        # Convert servers to host/basePath/schemes
        servers = spec_data.get("servers", [])
        if servers:
            server_url = servers[0].get("url", "https://localhost/")
            match = re.match(r"(https?)://([^/]+)(.*)", server_url)
            if match:
                converted["schemes"] = [match.group(1)]
                converted["host"] = match.group(2)
                converted["basePath"] = match.group(3) or "/"

        # Convert components/schemas to definitions
        schemas = spec_data.get("components", {}).get("schemas", {})
        for name, schema in schemas.items():
            converted["definitions"][name] = self._convert_schema_3_to_2(schema)

        # Convert paths
        paths = spec_data.get("paths", {})
        for path, path_item in paths.items():
            converted["paths"][path] = self._convert_path_item_3_to_2(path_item)

        # Convert security schemes
        sec_schemes = spec_data.get("components", {}).get("securitySchemes", {})
        for name, sec_scheme in sec_schemes.items():
            converted["securityDefinitions"][name] = self._convert_security_scheme_3_to_2(sec_scheme)

        # Copy security and tags
        for key in ["security", "tags", "externalDocs"]:
            if key in spec_data:
                converted[key] = spec_data[key]

        return converted

    def _convert_schema_3_to_2(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Convert a schema from OpenAPI 3.0 to Swagger 2.0."""
        converted = dict(schema)

        # Convert $ref paths
        if "$ref" in converted:
            ref = converted["$ref"]
            if ref.startswith("#/components/schemas/"):
                converted["$ref"] = ref.replace("#/components/schemas/", "#/definitions/")

        # Remove nullable (not supported in 2.0)
        converted.pop("nullable", None)

        # Recursively convert nested schemas
        for key in ["items", "additionalProperties"]:
            if key in converted and isinstance(converted[key], dict):
                converted[key] = self._convert_schema_3_to_2(converted[key])

        if "properties" in converted:
            for prop_name, prop_schema in converted["properties"].items():
                if isinstance(prop_schema, dict):
                    converted["properties"][prop_name] = self._convert_schema_3_to_2(prop_schema)

        return converted

    def _convert_path_item_3_to_2(self, path_item: dict[str, Any]) -> dict[str, Any]:
        """Convert a path item from OpenAPI 3.0 to Swagger 2.0."""
        converted: dict[str, Any] = {}
        http_methods = ["get", "put", "post", "delete", "options", "head", "patch"]

        for method in http_methods:
            if method in path_item:
                converted[method] = self._convert_operation_3_to_2(path_item[method])

        for key in ["summary", "description", "parameters"]:
            if key in path_item:
                converted[key] = path_item[key]

        return converted

    def _convert_operation_3_to_2(self, operation: dict[str, Any]) -> dict[str, Any]:
        """Convert an operation from OpenAPI 3.0 to Swagger 2.0."""
        converted: dict[str, Any] = {
            "responses": {},
        }

        for key in ["operationId", "summary", "description", "tags", "deprecated", "security"]:
            if key in operation:
                converted[key] = operation[key]

        # Convert parameters
        parameters = list(operation.get("parameters", []))

        # Convert requestBody to body parameter
        if "requestBody" in operation:
            req_body = operation["requestBody"]
            content = req_body.get("content", {})
            for media_type, media_content in content.items():
                body_param = {
                    "name": "body",
                    "in": "body",
                    "required": req_body.get("required", False),
                    "schema": self._convert_schema_3_to_2(media_content.get("schema", {})),
                }
                if "description" in req_body:
                    body_param["description"] = req_body["description"]
                parameters.append(body_param)
                break  # Only use first content type

        if parameters:
            converted["parameters"] = parameters

        # Convert responses
        for status_code, response in operation.get("responses", {}).items():
            converted_response = {
                "description": response.get("description", ""),
            }
            content = response.get("content", {})
            for media_type, media_content in content.items():
                if "schema" in media_content:
                    converted_response["schema"] = self._convert_schema_3_to_2(
                        media_content["schema"]
                    )
                break
            converted["responses"][status_code] = converted_response

        return converted

    def _convert_security_scheme_3_to_2(self, sec_scheme: dict[str, Any]) -> dict[str, Any]:
        """Convert a security scheme from OpenAPI 3.0 to Swagger 2.0."""
        sec_type = sec_scheme.get("type")

        if sec_type == "http" and sec_scheme.get("scheme") == "basic":
            return {"type": "basic"}
        elif sec_type == "apiKey":
            return {
                "type": "apiKey",
                "in": sec_scheme.get("in"),
                "name": sec_scheme.get("name"),
            }
        elif sec_type == "oauth2":
            flows = sec_scheme.get("flows", {})
            result = {"type": "oauth2"}

            flow_map = {
                "implicit": "implicit",
                "password": "password",
                "clientCredentials": "application",
                "authorizationCode": "accessCode",
            }

            for flow_name, flow_type in flow_map.items():
                if flow_name in flows:
                    result["flow"] = flow_type
                    flow = flows[flow_name]
                    if "authorizationUrl" in flow:
                        result["authorizationUrl"] = flow["authorizationUrl"]
                    if "tokenUrl" in flow:
                        result["tokenUrl"] = flow["tokenUrl"]
                    if "scopes" in flow:
                        result["scopes"] = flow["scopes"]
                    break

            return result

        return sec_scheme

    def _convert_nullable_to_type_array(self, obj: Any) -> None:
        """Recursively convert nullable: true to type arrays (3.0 to 3.1)."""
        if isinstance(obj, dict):
            if obj.get("nullable") is True and "type" in obj:
                obj["type"] = [obj["type"], "null"]
                del obj["nullable"]
            for value in obj.values():
                self._convert_nullable_to_type_array(value)
        elif isinstance(obj, list):
            for item in obj:
                self._convert_nullable_to_type_array(item)

    def _convert_type_array_to_nullable(self, obj: Any) -> None:
        """Recursively convert type arrays to nullable: true (3.1 to 3.0)."""
        if isinstance(obj, dict):
            if isinstance(obj.get("type"), list) and "null" in obj["type"]:
                types = [t for t in obj["type"] if t != "null"]
                if len(types) == 1:
                    obj["type"] = types[0]
                    obj["nullable"] = True
            for value in obj.values():
                self._convert_type_array_to_nullable(value)
        elif isinstance(obj, list):
            for item in obj:
                self._convert_type_array_to_nullable(item)

    def _convert_exclusive_bounds(self, obj: Any) -> None:
        """Convert exclusive bounds from boolean to number (3.0 to 3.1)."""
        if isinstance(obj, dict):
            if obj.get("exclusiveMinimum") is True and "minimum" in obj:
                obj["exclusiveMinimum"] = obj.pop("minimum")
            if obj.get("exclusiveMaximum") is True and "maximum" in obj:
                obj["exclusiveMaximum"] = obj.pop("maximum")
            for value in obj.values():
                self._convert_exclusive_bounds(value)
        elif isinstance(obj, list):
            for item in obj:
                self._convert_exclusive_bounds(item)

    def save(
        self,
        output_path: str | Path,
        spec_data: dict[str, Any]
    ) -> None:
        """
        Save a specification to a file.

        Args:
            output_path: Path to save the specification.
            spec_data: Specification data to save.
        """
        save_spec_file(Path(output_path), spec_data)
