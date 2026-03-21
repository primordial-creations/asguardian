"""
OpenAPI Specification Converter Service.

Converts between OpenAPI specification versions.
"""

from pathlib import Path
from typing import Any, Optional

from Asgard.Forseti.OpenAPI.models.openapi_models import (
    OpenAPIConfig,
    OpenAPIVersion,
)
from Asgard.Forseti.OpenAPI.utilities.openapi_utils import (
    load_spec_file,
    save_spec_file,
    detect_openapi_version,
)
from Asgard.Forseti.OpenAPI.services._spec_converter_2_to_3_helpers import (
    convert_2_to_3_0,
    convert_exclusive_bounds,
    convert_nullable_to_type_array,
    convert_parameter_2_to_3,
    convert_path_item_2_to_3,
    convert_operation_2_to_3,
    convert_schema_2_to_3,
    convert_security_def_2_to_3,
)
from Asgard.Forseti.OpenAPI.services._spec_converter_3_to_2_helpers import (
    convert_3_0_to_2,
    convert_operation_3_to_2,
    convert_path_item_3_to_2,
    convert_schema_3_to_2,
    convert_security_scheme_3_to_2,
    convert_type_array_to_nullable,
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
        return convert_2_to_3_0(
            spec_data,
            self._convert_schema_2_to_3,
            self._convert_path_item_2_to_3,
            convert_security_def_2_to_3,
        )

    def _convert_schema_2_to_3(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Convert a schema from Swagger 2.0 to OpenAPI 3.0."""
        return convert_schema_2_to_3(schema, self._convert_schema_2_to_3)

    def _convert_path_item_2_to_3(self, path_item: dict[str, Any]) -> dict[str, Any]:
        """Convert a path item from Swagger 2.0 to OpenAPI 3.0."""
        return convert_path_item_2_to_3(
            path_item,
            self._convert_operation_2_to_3,
            convert_parameter_2_to_3,
        )

    def _convert_operation_2_to_3(self, operation: dict[str, Any]) -> dict[str, Any]:
        """Convert an operation from Swagger 2.0 to OpenAPI 3.0."""
        return convert_operation_2_to_3(
            operation,
            self._convert_schema_2_to_3,
            convert_parameter_2_to_3,
        )

    def _convert_3_0_to_3_1(self, spec_data: dict[str, Any]) -> dict[str, Any]:
        """Convert OpenAPI 3.0 to 3.1."""
        converted = dict(spec_data)
        converted["openapi"] = "3.1.0"
        convert_nullable_to_type_array(converted)
        convert_exclusive_bounds(converted)
        return converted

    def _convert_3_1_to_3_0(self, spec_data: dict[str, Any]) -> dict[str, Any]:
        """Convert OpenAPI 3.1 to 3.0."""
        converted = dict(spec_data)
        converted["openapi"] = "3.0.3"
        convert_type_array_to_nullable(converted)
        return converted

    def _convert_3_0_to_2(self, spec_data: dict[str, Any]) -> dict[str, Any]:
        """Convert OpenAPI 3.0 to Swagger 2.0."""
        return convert_3_0_to_2(
            spec_data,
            self._convert_schema_3_to_2,
            self._convert_path_item_3_to_2,
            convert_security_scheme_3_to_2,
        )

    def _convert_schema_3_to_2(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Convert a schema from OpenAPI 3.0 to Swagger 2.0."""
        return convert_schema_3_to_2(schema, self._convert_schema_3_to_2)

    def _convert_path_item_3_to_2(self, path_item: dict[str, Any]) -> dict[str, Any]:
        """Convert a path item from OpenAPI 3.0 to Swagger 2.0."""
        return convert_path_item_3_to_2(path_item, self._convert_operation_3_to_2)

    def _convert_operation_3_to_2(self, operation: dict[str, Any]) -> dict[str, Any]:
        """Convert an operation from OpenAPI 3.0 to Swagger 2.0."""
        return convert_operation_3_to_2(operation, self._convert_schema_3_to_2)

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
