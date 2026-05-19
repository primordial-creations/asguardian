"""
Tests for OpenAPI Spec Parser Service

Unit tests for OpenAPI specification parsing and conversion.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from Asgard.Forseti.OpenAPI.models.openapi_models import (
    OpenAPIConfig,
    OpenAPISpec,
    OpenAPIInfo,
)
from Asgard.Forseti.OpenAPI.services.spec_parser_service import SpecParserService


class TestSpecParserServiceInit:
    """Tests for SpecParserService initialization."""

    def test_init_with_default_config(self):
        """Test initialization with default configuration."""
        service = SpecParserService()

        assert service.config is not None
        assert isinstance(service.config, OpenAPIConfig)

    def test_init_with_custom_config(self):
        """Test initialization with custom configuration."""
        config = OpenAPIConfig(strict_mode=True)
        service = SpecParserService(config)

        assert service.config.strict_mode is True


class TestSpecParserServiceParseFile:
    """Tests for parsing specification files."""

    def test_parse_nonexistent_file(self, tmp_path):
        """Test parsing a file that doesn't exist."""
        service = SpecParserService()
        nonexistent_file = tmp_path / "nonexistent.yaml"

        with pytest.raises(FileNotFoundError):
            service.parse(nonexistent_file)

    def test_parse_valid_openapi_v3_file(self, openapi_spec_file):
        """Test parsing a valid OpenAPI 3.0 file."""
        service = SpecParserService()

        spec = service.parse(openapi_spec_file)

        assert isinstance(spec, OpenAPISpec)
        assert spec.openapi.startswith("3.")
        assert spec.info.title == "Test API"
        assert spec.info.version == "1.0.0"
        assert len(spec.paths) > 0

    def test_parse_file_with_string_path(self, openapi_spec_file):
        """Test parsing with string path instead of Path object."""
        service = SpecParserService()

        spec = service.parse(str(openapi_spec_file))

        assert isinstance(spec, OpenAPISpec)
        assert spec.info.title == "Test API"


class TestSpecParserServiceParseData:
    """Tests for parsing specification dictionaries."""

    def test_parse_openapi_v3_data(self, sample_openapi_v3_spec):
        """Test parsing OpenAPI 3.0 data."""
        service = SpecParserService()

        spec = service.parse_data(sample_openapi_v3_spec)

        assert isinstance(spec, OpenAPISpec)
        assert spec.openapi == "3.0.3"
        assert spec.info.title == "Test API"
        assert spec.info.version == "1.0.0"
        assert spec.info.description == "A test API specification"

    def test_parse_spec_with_servers(self, sample_openapi_v3_spec):
        """Test parsing specification with servers."""
        service = SpecParserService()

        spec = service.parse_data(sample_openapi_v3_spec)

        assert spec.servers is not None
        assert len(spec.servers) > 0
        assert spec.servers[0].url == "https://api.test.com/v1"

    def test_parse_spec_with_components(self, sample_openapi_v3_spec):
        """Test parsing specification with components."""
        service = SpecParserService()

        spec = service.parse_data(sample_openapi_v3_spec)

        assert spec.components is not None
        assert "schemas" in spec.components
        assert "User" in spec.components["schemas"]

    def test_parse_spec_with_security(self):
        """Test parsing specification with security."""
        service = SpecParserService()
        spec_data = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {},
            "security": [{"apiKey": []}]
        }

        spec = service.parse_data(spec_data)

        assert spec.security is not None
        assert len(spec.security) > 0

    def test_parse_spec_with_tags(self):
        """Test parsing specification with tags."""
        service = SpecParserService()
        spec_data = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {},
            "tags": [
                {"name": "users", "description": "User operations"}
            ]
        }

        spec = service.parse_data(spec_data)

        assert spec.tags is not None
        assert len(spec.tags) > 0
        assert spec.tags[0]["name"] == "users"


class TestSpecParserServiceSwagger2Conversion:
    """Tests for Swagger 2.0 to OpenAPI 3.0 conversion."""

    def test_convert_swagger_2_to_openapi_3(self, sample_openapi_v2_spec):
        """Test converting Swagger 2.0 to OpenAPI 3.0."""
        service = SpecParserService()

        spec = service.parse_data(sample_openapi_v2_spec)

        assert spec.openapi == "3.0.0"
        assert "swagger" not in spec.model_dump()

    def test_convert_swagger_servers(self, sample_openapi_v2_spec):
        """Test conversion of host/basePath to servers."""
        service = SpecParserService()

        spec = service.parse_data(sample_openapi_v2_spec)

        assert spec.servers is not None
        assert len(spec.servers) > 0
        assert "https://api.test.com/v1" in spec.servers[0].url

    def test_convert_swagger_definitions(self, sample_openapi_v2_spec):
        """Test conversion of definitions to components/schemas."""
        service = SpecParserService()

        spec = service.parse_data(sample_openapi_v2_spec)

        assert spec.components is not None
        assert "schemas" in spec.components
        assert "User" in spec.components["schemas"]

    def test_convert_swagger_path_operations(self):
        """Test conversion of Swagger 2.0 operations."""
        service = SpecParserService()
        swagger_spec = {
            "swagger": "2.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "host": "api.test.com",
            "basePath": "/",
            "paths": {
                "/users": {
                    "get": {
                        "summary": "List users",
                        "produces": ["application/json"],
                        "responses": {
                            "200": {
                                "description": "Success",
                                "schema": {"type": "array"}
                            }
                        }
                    }
                }
            }
        }

        spec = service.parse_data(swagger_spec)

        assert "/users" in spec.paths
        assert "get" in spec.paths["/users"]

    def test_convert_swagger_body_parameter(self):
        """Test conversion of body parameters to requestBody."""
        service = SpecParserService()
        swagger_spec = {
            "swagger": "2.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "host": "api.test.com",
            "basePath": "/",
            "paths": {
                "/users": {
                    "post": {
                        "parameters": [
                            {
                                "name": "body",
                                "in": "body",
                                "required": True,
                                "schema": {"type": "object"}
                            }
                        ],
                        "responses": {
                            "201": {"description": "Created"}
                        }
                    }
                }
            }
        }

        spec = service.parse_data(swagger_spec)

        post_op = spec.paths["/users"]["post"]
        assert "requestBody" in post_op

    def test_convert_swagger_formdata_parameter(self):
        """Test conversion of formData parameters."""
        service = SpecParserService()
        swagger_spec = {
            "swagger": "2.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "host": "api.test.com",
            "basePath": "/",
            "paths": {
                "/upload": {
                    "post": {
                        "consumes": ["multipart/form-data"],
                        "parameters": [
                            {
                                "name": "file",
                                "in": "formData",
                                "type": "file",
                                "required": True
                            }
                        ],
                        "responses": {
                            "200": {"description": "OK"}
                        }
                    }
                }
            }
        }

        spec = service.parse_data(swagger_spec)

        post_op = spec.paths["/upload"]["post"]
        assert "requestBody" in post_op

    def test_convert_swagger_query_parameter(self):
        """Test conversion of query parameters."""
        service = SpecParserService()
        swagger_spec = {
            "swagger": "2.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "host": "api.test.com",
            "basePath": "/",
            "paths": {
                "/users": {
                    "get": {
                        "parameters": [
                            {
                                "name": "limit",
                                "in": "query",
                                "type": "integer",
                                "required": False
                            }
                        ],
                        "responses": {
                            "200": {"description": "OK"}
                        }
                    }
                }
            }
        }

        spec = service.parse_data(swagger_spec)

        get_op = spec.paths["/users"]["get"]
        assert "parameters" in get_op
        assert len(get_op["parameters"]) > 0

    def test_convert_swagger_security_basic(self):
        """Test conversion of basic auth security definition."""
        service = SpecParserService()
        swagger_spec = {
            "swagger": "2.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "host": "api.test.com",
            "basePath": "/",
            "paths": {},
            "securityDefinitions": {
                "basicAuth": {
                    "type": "basic"
                }
            }
        }

        spec = service.parse_data(swagger_spec)

        assert spec.components is not None
        assert "securitySchemes" in spec.components
        assert "basicAuth" in spec.components["securitySchemes"]
        assert spec.components["securitySchemes"]["basicAuth"]["type"] == "http"

    def test_convert_swagger_security_apikey(self):
        """Test conversion of API key security definition."""
        service = SpecParserService()
        swagger_spec = {
            "swagger": "2.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "host": "api.test.com",
            "basePath": "/",
            "paths": {},
            "securityDefinitions": {
                "apiKey": {
                    "type": "apiKey",
                    "name": "X-API-Key",
                    "in": "header"
                }
            }
        }

        spec = service.parse_data(swagger_spec)

        api_key = spec.components["securitySchemes"]["apiKey"]
        assert api_key["type"] == "apiKey"
        assert api_key["name"] == "X-API-Key"

    def test_convert_swagger_security_oauth2(self):
        """Test conversion of OAuth2 security definition."""
        service = SpecParserService()
        swagger_spec = {
            "swagger": "2.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "host": "api.test.com",
            "basePath": "/",
            "paths": {},
            "securityDefinitions": {
                "oauth2": {
                    "type": "oauth2",
                    "flow": "implicit",
                    "authorizationUrl": "https://auth.test.com/authorize",
                    "scopes": {"read": "Read access"}
                }
            }
        }

        spec = service.parse_data(swagger_spec)

        oauth2 = spec.components["securitySchemes"]["oauth2"]
        assert oauth2["type"] == "oauth2"
        assert "flows" in oauth2
        assert "implicit" in oauth2["flows"]


class TestSpecParserServiceHelperMethods:
    """Tests for helper methods."""

    def test_get_paths(self, sample_openapi_v3_spec):
        """Test getting all paths from spec."""
        service = SpecParserService()
        spec = service.parse_data(sample_openapi_v3_spec)

        paths = service.get_paths(spec)

        assert isinstance(paths, list)
        assert "/users" in paths
        assert "/users/{userId}" in paths

    def test_get_operations(self, sample_openapi_v3_spec):
        """Test getting all operations from spec."""
        service = SpecParserService()
        spec = service.parse_data(sample_openapi_v3_spec)

        operations = service.get_operations(spec)

        assert isinstance(operations, list)
        assert len(operations) > 0
        # Check format is (method, path, operation)
        for op in operations:
            assert len(op) == 3
            method, path, operation = op
            assert method in ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD", "TRACE"]
            assert path.startswith("/")
            assert isinstance(operation, dict)

    def test_get_schemas(self, sample_openapi_v3_spec):
        """Test getting all schemas from spec."""
        service = SpecParserService()
        spec = service.parse_data(sample_openapi_v3_spec)

        schemas = service.get_schemas(spec)

        assert isinstance(schemas, dict)
        assert "User" in schemas
        assert schemas["User"]["type"] == "object"

    def test_get_schemas_no_components(self):
        """Test getting schemas when no components exist."""
        service = SpecParserService()
        spec_data = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {}
        }
        spec = service.parse_data(spec_data)

        schemas = service.get_schemas(spec)

        assert schemas == {}


class TestSpecParserServiceInfoExtraction:
    """Tests for info object extraction."""

    def test_parse_info_with_all_fields(self):
        """Test parsing info with all optional fields."""
        service = SpecParserService()
        spec_data = {
            "openapi": "3.1.0",
            "info": {
                "title": "Complete API",
                "version": "2.0.0",
                "description": "A complete API description",
                "termsOfService": "https://test.com/terms",
                "summary": "API Summary"
            },
            "paths": {}
        }

        spec = service.parse_data(spec_data)

        assert spec.info.title == "Complete API"
        assert spec.info.version == "2.0.0"
        assert spec.info.description == "A complete API description"
        assert spec.info.terms_of_service == "https://test.com/terms"
        assert spec.info.summary == "API Summary"

    def test_parse_info_minimal(self):
        """Test parsing info with only required fields."""
        service = SpecParserService()
        spec_data = {
            "openapi": "3.0.0",
            "info": {
                "title": "Minimal API",
                "version": "1.0.0"
            },
            "paths": {}
        }

        spec = service.parse_data(spec_data)

        assert spec.info.title == "Minimal API"
        assert spec.info.version == "1.0.0"
        assert spec.info.description is None

    def test_parse_info_default_values(self):
        """Test parsing info with missing fields uses defaults."""
        service = SpecParserService()
        spec_data = {
            "openapi": "3.0.0",
            "info": {},
            "paths": {}
        }

        spec = service.parse_data(spec_data)

        assert spec.info.title == "Untitled API"
        assert spec.info.version == "1.0.0"


class TestSpecParserServiceEdgeCases:
    """Tests for edge cases and error handling."""

    def test_parse_spec_with_references(self):
        """Test parsing spec with $ref references."""
        service = SpecParserService()
        spec_data = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {
                "/users": {
                    "get": {
                        "responses": {
                            "200": {
                                "description": "Success",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/User"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "components": {
                "schemas": {
                    "User": {"type": "object"}
                }
            }
        }

        spec = service.parse_data(spec_data)

        # Parser resolves $ref into the inlined component schema.
        assert spec.paths is not None
        assert "/users" in spec.paths

    def test_parse_spec_with_empty_paths(self):
        """Test parsing spec with empty paths."""
        service = SpecParserService()
        spec_data = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {}
        }

        spec = service.parse_data(spec_data)

        assert spec.path_count == 0
        assert spec.operation_count == 0

    def test_parse_spec_properties_calculation(self, sample_openapi_v3_spec):
        """Test spec property calculations."""
        service = SpecParserService()
        spec = service.parse_data(sample_openapi_v3_spec)

        assert spec.path_count == 2
        assert spec.operation_count == 3
        assert spec.version.value in ["3.0", "3.1"]


class TestSpecParserServiceMultipleSchemes:
    """Tests for handling multiple schemes in Swagger 2.0."""

    def test_convert_multiple_schemes(self):
        """Test conversion of multiple schemes."""
        service = SpecParserService()
        swagger_spec = {
            "swagger": "2.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "host": "api.test.com",
            "basePath": "/v1",
            "schemes": ["http", "https"],
            "paths": {}
        }

        spec = service.parse_data(swagger_spec)

        assert len(spec.servers) == 2
        urls = [s.url for s in spec.servers]
        assert "http://api.test.com/v1" in urls
        assert "https://api.test.com/v1" in urls
