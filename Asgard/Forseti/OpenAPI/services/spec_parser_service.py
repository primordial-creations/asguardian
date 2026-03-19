"""
OpenAPI Specification Parser Service.

Parses and normalizes OpenAPI specifications.
"""

from pathlib import Path
from typing import Any, Optional, cast

from Asgard.Forseti.OpenAPI.models.openapi_models import (
    OpenAPIConfig,
    OpenAPIInfo,
    OpenAPISpec,
    OpenAPIVersion,
)
from Asgard.Forseti.OpenAPI.utilities.openapi_utils import (
    load_spec_file,
    detect_openapi_version,
    resolve_references,
)


class SpecParserService:
    """
    Service for parsing OpenAPI specifications.

    Parses specifications from files or dictionaries and returns
    structured OpenAPI models.

    Usage:
        service = SpecParserService()
        spec = service.parse("openapi.yaml")
        print(f"API Title: {spec.info.title}")
        print(f"Paths: {spec.path_count}")
    """

    def __init__(self, config: Optional[OpenAPIConfig] = None):
        """
        Initialize the parser service.

        Args:
            config: Optional configuration for parsing behavior.
        """
        self.config = config or OpenAPIConfig()

    def parse(self, spec_path: str | Path) -> OpenAPISpec:
        """
        Parse an OpenAPI specification file.

        Args:
            spec_path: Path to the OpenAPI specification file.

        Returns:
            Parsed OpenAPISpec model.

        Raises:
            FileNotFoundError: If the specification file does not exist.
            ValueError: If the specification is invalid.
        """
        spec_path = Path(spec_path)
        if not spec_path.exists():
            raise FileNotFoundError(f"Specification file not found: {spec_path}")

        spec_data = load_spec_file(spec_path)
        return self.parse_data(spec_data)

    def parse_data(self, spec_data: dict[str, Any]) -> OpenAPISpec:
        """
        Parse an OpenAPI specification from a dictionary.

        Args:
            spec_data: Parsed OpenAPI specification as a dictionary.

        Returns:
            Parsed OpenAPISpec model.

        Raises:
            ValueError: If the specification is invalid.
        """
        version = detect_openapi_version(spec_data)

        if version == OpenAPIVersion.V2_0:
            spec_data = self._convert_swagger_to_openapi(spec_data)

        # Resolve internal references
        resolved_data = resolve_references(spec_data)

        # Extract info
        info_data = resolved_data.get("info", {})
        info = OpenAPIInfo(
            title=info_data.get("title", "Untitled API"),
            version=info_data.get("version", "1.0.0"),
            description=info_data.get("description"),
            terms_of_service=info_data.get("termsOfService"),
            summary=info_data.get("summary"),
        )

        # Build spec
        return OpenAPISpec(
            openapi=resolved_data.get("openapi", "3.0.0"),
            info=info,
            servers=resolved_data.get("servers"),
            paths=resolved_data.get("paths", {}),
            components=resolved_data.get("components"),
            security=resolved_data.get("security"),
            tags=resolved_data.get("tags"),
            external_docs=resolved_data.get("externalDocs"),
        )

    def _convert_swagger_to_openapi(self, spec_data: dict[str, Any]) -> dict[str, Any]:
        """
        Convert a Swagger 2.0 specification to OpenAPI 3.0 format.

        Args:
            spec_data: Swagger 2.0 specification.

        Returns:
            OpenAPI 3.0 formatted specification.
        """
        converted = {
            "openapi": "3.0.0",
            "info": spec_data.get("info", {}),
            "paths": {},
            "components": {
                "schemas": spec_data.get("definitions", {}),
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

        # Convert paths
        paths = spec_data.get("paths", {})
        for path, path_item in paths.items():
            converted["paths"][path] = self._convert_path_item(path_item)

        # Convert security definitions
        security_defs = spec_data.get("securityDefinitions", {})
        for name, sec_def in security_defs.items():
            converted["components"]["securitySchemes"][name] = (
                self._convert_security_definition(sec_def)
            )

        return converted

    def _convert_path_item(self, path_item: dict[str, Any]) -> dict[str, Any]:
        """Convert a Swagger 2.0 path item to OpenAPI 3.0."""
        converted = {}
        http_methods = ["get", "put", "post", "delete", "options", "head", "patch"]

        for method in http_methods:
            if method in path_item:
                converted[method] = self._convert_operation(path_item[method])

        # Copy non-operation fields
        for key in ["summary", "description", "parameters"]:
            if key in path_item:
                converted[key] = path_item[key]

        return converted

    def _convert_operation(self, operation: dict[str, Any]) -> dict[str, Any]:
        """Convert a Swagger 2.0 operation to OpenAPI 3.0."""
        converted: dict[str, Any] = {
            "responses": {},
        }

        # Copy basic fields
        for key in ["operationId", "summary", "description", "tags", "deprecated", "security"]:
            if key in operation:
                converted[key] = operation[key]

        # Convert parameters
        parameters = []
        request_body = None

        for param in operation.get("parameters", []):
            if param.get("in") == "body":
                request_body = {
                    "description": param.get("description", ""),
                    "required": param.get("required", False),
                    "content": {
                        "application/json": {
                            "schema": param.get("schema", {}),
                        }
                    }
                }
            elif param.get("in") == "formData":
                if request_body is None:
                    request_body = {
                        "content": {
                            "application/x-www-form-urlencoded": {
                                "schema": {
                                    "type": "object",
                                    "properties": {},
                                }
                            }
                        }
                    }
                content = request_body["content"]["application/x-www-form-urlencoded"]
                content["schema"]["properties"][param["name"]] = {
                    "type": param.get("type", "string"),
                    "description": param.get("description", ""),
                }
            else:
                # Query, header, path, cookie parameters
                converted_param = {
                    "name": param.get("name"),
                    "in": param.get("in"),
                    "description": param.get("description", ""),
                    "required": param.get("required", False),
                    "schema": {
                        "type": param.get("type", "string"),
                    }
                }
                if "format" in param:
                    converted_param["schema"]["format"] = param["format"]
                if "enum" in param:
                    converted_param["schema"]["enum"] = param["enum"]
                parameters.append(converted_param)

        if parameters:
            converted["parameters"] = parameters
        if request_body:
            converted["requestBody"] = request_body

        # Convert responses
        for status_code, response in operation.get("responses", {}).items():
            converted_response = {
                "description": response.get("description", ""),
            }
            if "schema" in response:
                converted_response["content"] = {
                    "application/json": {
                        "schema": response["schema"],
                    }
                }
            if "headers" in response:
                converted_response["headers"] = response["headers"]
            converted["responses"][status_code] = converted_response

        return converted

    def _convert_security_definition(self, sec_def: dict[str, Any]) -> dict[str, Any]:
        """Convert a Swagger 2.0 security definition to OpenAPI 3.0."""
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

            if flow_type == "implicit":
                flows["implicit"] = flow_data
            elif flow_type == "password":
                flows["password"] = flow_data
            elif flow_type == "application":
                flows["clientCredentials"] = flow_data
            elif flow_type == "accessCode":
                flows["authorizationCode"] = flow_data

            return {
                "type": "oauth2",
                "flows": flows,
            }

        return sec_def

    def get_paths(self, spec: OpenAPISpec) -> list[str]:
        """
        Get all paths from a specification.

        Args:
            spec: Parsed OpenAPI specification.

        Returns:
            List of path strings.
        """
        return list(spec.paths.keys())

    def get_operations(self, spec: OpenAPISpec) -> list[tuple[str, str, dict]]:
        """
        Get all operations from a specification.

        Args:
            spec: Parsed OpenAPI specification.

        Returns:
            List of tuples (method, path, operation_data).
        """
        operations = []
        http_methods = ["get", "put", "post", "delete", "options", "head", "patch", "trace"]

        for path, path_item in spec.paths.items():
            if not isinstance(path_item, dict):
                continue
            for method in http_methods:
                if method in path_item:
                    operations.append((method.upper(), path, path_item[method]))

        return operations

    def get_schemas(self, spec: OpenAPISpec) -> dict[str, Any]:
        """
        Get all schemas from a specification.

        Args:
            spec: Parsed OpenAPI specification.

        Returns:
            Dictionary of schema name to schema definition.
        """
        if spec.components and "schemas" in spec.components:
            return cast(dict[str, Any], spec.components["schemas"])
        return {}
