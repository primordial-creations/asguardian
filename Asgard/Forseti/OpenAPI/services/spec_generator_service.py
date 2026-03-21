"""
OpenAPI Specification Generator Service.

Generates OpenAPI specifications from source code analysis.
"""

import json
from pathlib import Path
from typing import Any, Optional, cast

import yaml  # type: ignore[import-untyped]

from Asgard.Forseti.OpenAPI.models.openapi_models import (
    OpenAPIConfig,
    OpenAPIInfo,
    OpenAPISpec,
)
from Asgard.Forseti.OpenAPI.services._spec_generator_helpers import (
    analyze_fastapi_file,
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

        python_files = list(source_path.rglob("*.py"))

        for py_file in python_files:
            try:
                file_paths, file_schemas = analyze_fastapi_file(py_file)
                paths.update(file_paths)
                schemas.update(file_schemas)
            except Exception:
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
