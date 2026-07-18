"""
Forseti MockServer Module - Mock Server Generation

This module provides mock server generation from API specifications:
- Generate mock servers from OpenAPI specifications
- Generate mock servers from AsyncAPI specifications
- Generate realistic mock data based on JSON schemas
- Support for Flask, FastAPI, and Express.js frameworks

Usage:
    from Asgard.Forseti.MockServer import MockServerGeneratorService, MockServerConfig

    # Generate a mock server from OpenAPI
    config = MockServerConfig(server_framework="fastapi", port=8080)
    generator = MockServerGeneratorService(config)
    result = generator.generate_from_openapi("api.yaml", output_dir="./mock-server")

    for file in result.generated_files:
        print(f"Generated: {file.path}")

    # Generate mock data
    from Asgard.Forseti.MockServer import MockDataGeneratorService
    data_generator = MockDataGeneratorService()
    result = data_generator.generate_from_schema(my_schema)
    print(result.data)
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

# Import models
from Asgard.Forseti.MockServer.models import (
    DataType,
    GeneratedFile,
    HttpMethod,
    MockDataConfig,
    MockDataResult,
    MockEndpoint,
    MockHeader,
    MockParameter,
    MockRequestBody,
    MockResponse,
    MockResponseType,
    MockServerConfig,
    MockServerDefinition,
    MockServerGenerationResult,
)

# Import services
from Asgard.Forseti.MockServer.services import (
    MockDataGeneratorService,
    MockServerGeneratorService,
    ValidationProxyService,
)

__all__ = [
    # Models
    "DataType",
    "GeneratedFile",
    "HttpMethod",
    "MockDataConfig",
    "MockDataResult",
    "MockEndpoint",
    "MockHeader",
    "MockParameter",
    "MockRequestBody",
    "MockResponse",
    "MockResponseType",
    "MockServerConfig",
    "MockServerDefinition",
    "MockServerGenerationResult",
    # Services
    "MockDataGeneratorService",
    "MockServerGeneratorService",
    "ValidationProxyService",
]
