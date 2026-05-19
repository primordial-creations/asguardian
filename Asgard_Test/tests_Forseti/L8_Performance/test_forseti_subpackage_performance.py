"""
Forseti L8 Performance Benchmarks — Sub-package coverage

Benchmarks for every Forseti sub-package not covered by the existing
test_forseti_performance.py file:

  AsyncAPI · CodeGen (Python/Go/TypeScript) · Contracts
  Database · Documentation · GraphQL · MockServer · OpenAPI · Protobuf

Each class exercises one public entry-point method per service using
minimal but valid in-memory or tmp_path inputs.
"""

import json
import textwrap
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# AsyncAPI
# ---------------------------------------------------------------------------
from Asgard.Forseti.AsyncAPI.services.asyncapi_validator_service import AsyncAPIValidatorService
from Asgard.Forseti.AsyncAPI.services.asyncapi_parser_service import AsyncAPIParserService

ASYNCAPI_SPEC: dict = {
    "asyncapi": "2.6.0",
    "info": {"title": "Events API", "version": "1.0.0"},
    "channels": {
        "user/created": {
            "publish": {
                "message": {
                    "payload": {
                        "type": "object",
                        "properties": {
                            "userId": {"type": "string"},
                            "email": {"type": "string"},
                        },
                    }
                }
            }
        }
    },
}

ASYNCAPI_YAML = yaml.dump(ASYNCAPI_SPEC)


class TestAsyncAPIPerformance:
    """L8 benchmarks for AsyncAPI validator and parser."""

    def test_asyncapi_validate_spec_data(self, benchmark):
        """Benchmark in-memory AsyncAPI spec validation."""
        service = AsyncAPIValidatorService()
        result = benchmark(service.validate_spec_data, ASYNCAPI_SPEC)
        assert result is not None

    def test_asyncapi_parse_string(self, benchmark):
        """Benchmark parsing an AsyncAPI YAML string."""
        service = AsyncAPIParserService()
        result = benchmark(service.parse_string, ASYNCAPI_YAML)
        assert result is not None

    def test_asyncapi_validate_file(self, benchmark, tmp_path):
        """Benchmark validating an AsyncAPI spec from a file."""
        spec_file = tmp_path / "asyncapi.yaml"
        spec_file.write_text(ASYNCAPI_YAML)
        service = AsyncAPIValidatorService()
        result = benchmark(service.validate, spec_file)
        assert result is not None


# ---------------------------------------------------------------------------
# CodeGen — Python / Go / TypeScript generators
# ---------------------------------------------------------------------------
from Asgard.Forseti.CodeGen.services.python_generator import PythonGeneratorService
from Asgard.Forseti.CodeGen.services.golang_generator import GolangGeneratorService
from Asgard.Forseti.CodeGen.services.typescript_generator import TypeScriptGeneratorService

_OPENAPI_SPEC_DICT: dict = {
    "openapi": "3.0.0",
    "info": {"title": "Pet API", "version": "1.0.0"},
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "summary": "List all pets",
                "responses": {
                    "200": {
                        "description": "A list of pets",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {"$ref": "#/components/schemas/Pet"},
                                }
                            }
                        },
                    }
                },
            }
        }
    },
    "components": {
        "schemas": {
            "Pet": {
                "type": "object",
                "required": ["id", "name"],
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "tag": {"type": "string"},
                },
            }
        }
    },
}

_OPENAPI_YAML = yaml.dump(_OPENAPI_SPEC_DICT)


class TestCodeGenPerformance:
    """L8 benchmarks for Python, Go, and TypeScript code generators."""

    def test_python_generator(self, benchmark, tmp_path):
        """Benchmark Python client generation from an OpenAPI spec."""
        spec_file = tmp_path / "api.yaml"
        spec_file.write_text(_OPENAPI_YAML)
        service = PythonGeneratorService()
        result = benchmark(service.generate, spec_file)
        assert result is not None

    def test_golang_generator(self, benchmark, tmp_path):
        """Benchmark Go client generation from an OpenAPI spec."""
        spec_file = tmp_path / "api.yaml"
        spec_file.write_text(_OPENAPI_YAML)
        service = GolangGeneratorService()
        result = benchmark(service.generate, spec_file)
        assert result is not None

    def test_typescript_generator(self, benchmark, tmp_path):
        """Benchmark TypeScript client generation from an OpenAPI spec."""
        spec_file = tmp_path / "api.yaml"
        spec_file.write_text(_OPENAPI_YAML)
        service = TypeScriptGeneratorService()
        result = benchmark(service.generate, spec_file)
        assert result is not None


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------
from Asgard.Forseti.Contracts.services.contract_validator_service import ContractValidatorService
from Asgard.Forseti.Contracts.services.breaking_change_detector_service import BreakingChangeDetectorService

_CONTRACT_V1: dict = {
    "openapi": "3.0.0",
    "info": {"title": "Stable API", "version": "1.0.0"},
    "paths": {
        "/items": {
            "get": {
                "operationId": "listItems",
                "responses": {"200": {"description": "ok"}},
            }
        }
    },
}

_CONTRACT_V2: dict = {
    "openapi": "3.0.0",
    "info": {"title": "Stable API", "version": "2.0.0"},
    "paths": {
        "/items": {
            "get": {
                "operationId": "listItems",
                "responses": {"200": {"description": "ok"}},
            }
        },
        "/items/{id}": {
            "get": {
                "operationId": "getItem",
                "responses": {"200": {"description": "ok"}},
            }
        },
    },
}


class TestContractsPerformance:
    """L8 benchmarks for Contracts validator and breaking-change detector."""

    def test_contract_validate(self, benchmark, tmp_path):
        """Benchmark validating an implementation against a contract."""
        v1_file = tmp_path / "contract.yaml"
        v2_file = tmp_path / "impl.yaml"
        v1_file.write_text(yaml.dump(_CONTRACT_V1))
        v2_file.write_text(yaml.dump(_CONTRACT_V2))
        service = ContractValidatorService()
        result = benchmark(service.validate, v1_file, v2_file)
        assert result is not None

    def test_breaking_change_detect(self, benchmark, tmp_path):
        """Benchmark detecting breaking changes between two spec versions."""
        v1_file = tmp_path / "v1.yaml"
        v2_file = tmp_path / "v2.yaml"
        v1_file.write_text(yaml.dump(_CONTRACT_V1))
        v2_file.write_text(yaml.dump(_CONTRACT_V2))
        service = BreakingChangeDetectorService()
        result = benchmark(service.detect, v1_file, v2_file)
        assert result is not None


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
from Asgard.Forseti.Database.services.schema_analyzer_service import SchemaAnalyzerService
from Asgard.Forseti.Database.services.schema_diff_service import SchemaDiffService

_SQL_V1 = textwrap.dedent("""\
    CREATE TABLE users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(255) NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT NOW()
    );
""")

_SQL_V2 = textwrap.dedent("""\
    CREATE TABLE users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(255) NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP
    );

    CREATE TABLE roles (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL
    );
""")


class TestDatabasePerformance:
    """L8 benchmarks for Database schema analysis and diff."""

    def test_schema_analyze_sql(self, benchmark):
        """Benchmark in-memory SQL schema analysis."""
        service = SchemaAnalyzerService()
        result = benchmark(service.analyze_sql, _SQL_V1)
        assert result is not None

    def test_schema_analyze_file(self, benchmark, tmp_path):
        """Benchmark schema analysis from a SQL file."""
        sql_file = tmp_path / "schema.sql"
        sql_file.write_text(_SQL_V1)
        service = SchemaAnalyzerService()
        result = benchmark(service.analyze_file, sql_file)
        assert result is not None

    def test_schema_diff(self, benchmark, tmp_path):
        """Benchmark diffing two SQL schema files."""
        v1_file = tmp_path / "v1.sql"
        v2_file = tmp_path / "v2.sql"
        v1_file.write_text(_SQL_V1)
        v2_file.write_text(_SQL_V2)
        service = SchemaDiffService()
        result = benchmark(service.diff, v1_file, v2_file)
        assert result is not None


# ---------------------------------------------------------------------------
# Documentation
# ---------------------------------------------------------------------------
from Asgard.Forseti.Documentation.services.docs_generator import DocsGeneratorService


class TestDocumentationPerformance:
    """L8 benchmarks for Documentation generator."""

    def test_docs_generate_from_spec_data(self, benchmark):
        """Benchmark documentation generation from in-memory OpenAPI spec."""
        service = DocsGeneratorService()
        result = benchmark(service.generate_from_spec_data, _OPENAPI_SPEC_DICT)
        assert result is not None

    def test_docs_generate_from_file(self, benchmark, tmp_path):
        """Benchmark documentation generation from an OpenAPI YAML file."""
        spec_file = tmp_path / "api.yaml"
        spec_file.write_text(_OPENAPI_YAML)
        service = DocsGeneratorService()
        result = benchmark(service.generate, spec_file)
        assert result is not None


# ---------------------------------------------------------------------------
# GraphQL
# ---------------------------------------------------------------------------
from Asgard.Forseti.GraphQL.services.schema_validator_service import SchemaValidatorService as GraphQLSchemaValidatorService

_GQL_SDL = textwrap.dedent("""\
    type Query {
      user(id: ID!): User
      users: [User!]!
    }

    type User {
      id: ID!
      name: String!
      email: String!
      posts: [Post!]!
    }

    type Post {
      id: ID!
      title: String!
      body: String!
      author: User!
    }
""")


class TestGraphQLPerformance:
    """L8 benchmarks for GraphQL schema validator."""

    def test_graphql_validate_sdl(self, benchmark):
        """Benchmark in-memory GraphQL SDL validation."""
        service = GraphQLSchemaValidatorService()
        result = benchmark(service.validate_sdl, _GQL_SDL)
        assert result is not None

    def test_graphql_validate_file(self, benchmark, tmp_path):
        """Benchmark validating a GraphQL schema from a file."""
        schema_file = tmp_path / "schema.graphql"
        schema_file.write_text(_GQL_SDL)
        service = GraphQLSchemaValidatorService()
        result = benchmark(service.validate, schema_file)
        assert result is not None


# ---------------------------------------------------------------------------
# MockServer
# ---------------------------------------------------------------------------
from Asgard.Forseti.MockServer.services.mock_data_generator import MockDataGeneratorService
from Asgard.Forseti.MockServer.services.mock_server_generator import MockServerGeneratorService

_MOCK_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "name": {"type": "string"},
        "email": {"type": "string", "format": "email"},
        "active": {"type": "boolean"},
    },
    "required": ["id", "name", "email"],
}


class TestMockServerPerformance:
    """L8 benchmarks for MockServer data and server generators."""

    def test_mock_data_generate_from_schema(self, benchmark):
        """Benchmark mock data generation from a JSON schema."""
        service = MockDataGeneratorService()
        service.set_seed(42)
        result = benchmark(service.generate_from_schema, _MOCK_SCHEMA)
        assert result is not None

    def test_mock_server_generate_definition(self, benchmark, tmp_path):
        """Benchmark mock server definition generation from an OpenAPI spec file."""
        spec_file = tmp_path / "api.yaml"
        spec_file.write_text(_OPENAPI_YAML)
        service = MockServerGeneratorService()
        result = benchmark(service.generate_definition, spec_file)
        assert result is not None


# ---------------------------------------------------------------------------
# OpenAPI
# ---------------------------------------------------------------------------
from Asgard.Forseti.OpenAPI.services.spec_validator_service import SpecValidatorService
from Asgard.Forseti.OpenAPI.services.spec_parser_service import SpecParserService


class TestOpenAPIPerformance:
    """L8 benchmarks for OpenAPI spec validator and parser."""

    def test_openapi_validate_spec_data(self, benchmark):
        """Benchmark in-memory OpenAPI spec validation."""
        service = SpecValidatorService()
        result = benchmark(service.validate_spec_data, _OPENAPI_SPEC_DICT)
        assert result is not None

    def test_openapi_validate_file(self, benchmark, tmp_path):
        """Benchmark OpenAPI spec validation from a YAML file."""
        spec_file = tmp_path / "api.yaml"
        spec_file.write_text(_OPENAPI_YAML)
        service = SpecValidatorService()
        result = benchmark(service.validate, spec_file)
        assert result is not None

    def test_openapi_parse_data(self, benchmark):
        """Benchmark parsing an in-memory OpenAPI spec dict."""
        service = SpecParserService()
        result = benchmark(service.parse_data, _OPENAPI_SPEC_DICT)
        assert result is not None

    def test_openapi_parse_file(self, benchmark, tmp_path):
        """Benchmark parsing an OpenAPI YAML file."""
        spec_file = tmp_path / "api.yaml"
        spec_file.write_text(_OPENAPI_YAML)
        service = SpecParserService()
        result = benchmark(service.parse, spec_file)
        assert result is not None


# ---------------------------------------------------------------------------
# Protobuf
# ---------------------------------------------------------------------------
from Asgard.Forseti.Protobuf.services.protobuf_validator_service import ProtobufValidatorService
from Asgard.Forseti.Protobuf.services.protobuf_compatibility_service import ProtobufCompatibilityService

_PROTO_V1 = textwrap.dedent("""\
    syntax = "proto3";

    package example;

    message User {
      int64 id = 1;
      string username = 2;
      string email = 3;
    }

    service UserService {
      rpc GetUser (User) returns (User);
    }
""")

_PROTO_V2 = textwrap.dedent("""\
    syntax = "proto3";

    package example;

    message User {
      int64 id = 1;
      string username = 2;
      string email = 3;
      string display_name = 4;
    }

    service UserService {
      rpc GetUser (User) returns (User);
      rpc ListUsers (User) returns (User);
    }
""")


class TestProtobufPerformance:
    """L8 benchmarks for Protobuf validator and compatibility checker."""

    def test_protobuf_validate_content(self, benchmark):
        """Benchmark in-memory Protobuf schema validation."""
        service = ProtobufValidatorService()
        result = benchmark(service.validate_content, _PROTO_V1)
        assert result is not None

    def test_protobuf_validate_file(self, benchmark, tmp_path):
        """Benchmark validating a .proto file from disk."""
        proto_file = tmp_path / "user.proto"
        proto_file.write_text(_PROTO_V1)
        service = ProtobufValidatorService()
        result = benchmark(service.validate, proto_file)
        assert result is not None

    def test_protobuf_compatibility_check(self, benchmark, tmp_path):
        """Benchmark compatibility check between two proto file versions."""
        v1_file = tmp_path / "v1.proto"
        v2_file = tmp_path / "v2.proto"
        v1_file.write_text(_PROTO_V1)
        v2_file.write_text(_PROTO_V2)
        service = ProtobufCompatibilityService()
        result = benchmark(service.check, v1_file, v2_file)
        assert result is not None
