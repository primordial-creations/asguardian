"""
Forseti OpenAPI Module - OpenAPI/Swagger Specification Management

This module provides comprehensive OpenAPI specification handling including:
- Specification validation against OpenAPI standards
- Specification parsing and normalization
- Version conversion (OpenAPI 2.0/3.0/3.1)
- Specification generation from code

Usage:
    from Asgard.Forseti.OpenAPI import SpecValidatorService, OpenAPIConfig

    # Validate an OpenAPI specification
    service = SpecValidatorService()
    result = service.validate("openapi.yaml")
    print(f"Valid: {result.is_valid}")
    for error in result.errors:
        print(f"  - {error.message}")

    # Parse a specification
    from Asgard.Forseti.OpenAPI import SpecParserService
    parser = SpecParserService()
    spec = parser.parse("openapi.yaml")
    print(f"Title: {spec.info.title}")
    print(f"Version: {spec.info.version}")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

# Import models
from Asgard.Forseti.OpenAPI.models import (
    OpenAPIConfig,
    OpenAPISpec,
    OpenAPIInfo,
    OpenAPIPath,
    OpenAPIOperation,
    OpenAPIParameter,
    OpenAPIResponse,
    OpenAPISchema,
    OpenAPIValidationResult,
    OpenAPIValidationError,
    OpenAPIVersion,
    ValidationSeverity,
)

# Import services
from Asgard.Forseti.OpenAPI.services import (
    CompletenessService,
    SpecValidatorService,
    SpecParserService,
    SpecGeneratorService,
    SpecConverterService,
)

# Import utilities
from Asgard.Forseti.OpenAPI.utilities import (
    load_spec_file,
    save_spec_file,
    detect_openapi_version,
    normalize_path,
    merge_specs,
)

__all__ = [
    # Models
    "OpenAPIConfig",
    "OpenAPISpec",
    "OpenAPIInfo",
    "OpenAPIPath",
    "OpenAPIOperation",
    "OpenAPIParameter",
    "OpenAPIResponse",
    "OpenAPISchema",
    "OpenAPIValidationResult",
    "OpenAPIValidationError",
    "OpenAPIVersion",
    "ValidationSeverity",
    # Services
    "CompletenessService",
    "SpecValidatorService",
    "SpecParserService",
    "SpecGeneratorService",
    "SpecConverterService",
    # Utilities
    "load_spec_file",
    "save_spec_file",
    "detect_openapi_version",
    "normalize_path",
    "merge_specs",
]
