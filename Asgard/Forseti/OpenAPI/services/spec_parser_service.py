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
from Asgard.Forseti.OpenAPI.services._spec_parser_helpers import (
    convert_swagger_to_openapi,
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
            spec_data = convert_swagger_to_openapi(spec_data)

        resolved_data = resolve_references(spec_data)

        info_data = resolved_data.get("info", {})
        info = OpenAPIInfo(
            title=info_data.get("title", "Untitled API"),
            version=info_data.get("version", "1.0.0"),
            description=info_data.get("description"),
            terms_of_service=info_data.get("termsOfService"),
            summary=info_data.get("summary"),
        )

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
