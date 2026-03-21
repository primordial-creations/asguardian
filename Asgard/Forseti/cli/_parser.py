import argparse

from Asgard.Forseti.cli._parser_flags import add_performance_flags
from Asgard.Forseti.cli._parser_commands import (
    _add_openapi_parser,
    _add_graphql_parser,
    _add_database_parser,
    _add_contract_parser,
    _add_jsonschema_parser,
    _add_asyncapi_parser,
    _add_mock_parser,
    _add_codegen_parser,
    _add_docs_parser,
    _add_protobuf_parser,
    _add_avro_parser,
    _add_audit_parser,
)


def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser."""
    parser = argparse.ArgumentParser(
        prog="forseti",
        description="Forseti - API and Schema Specification Tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate OpenAPI specification
  forseti openapi validate api.yaml

  # Validate AsyncAPI specification
  forseti asyncapi validate asyncapi.yaml

  # Check API compatibility
  forseti contract check-compat old.yaml new.yaml

  # Validate data against JSON Schema
  forseti jsonschema validate schema.json data.json

  # Generate mock server from OpenAPI spec
  forseti mock generate api.yaml --output ./mock-server

  # Generate TypeScript client from OpenAPI spec
  forseti codegen typescript api.yaml --output ./client

  # Generate API documentation
  forseti docs generate api.yaml --output ./docs

  # Validate Protobuf schema
  forseti protobuf validate schema.proto

  # Check Protobuf compatibility
  forseti protobuf check-compat old.proto new.proto

  # Validate Avro schema
  forseti avro validate schema.avsc

  # Check Avro compatibility
  forseti avro check-compat old.avsc new.avsc
        """,
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    parser.add_argument(
        "--format",
        choices=["text", "json", "markdown", "github"],
        default="text",
        help="Output format (default: text)",
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict validation mode",
    )

    parser.add_argument(
        "--output", "-o",
        help="Output directory or file",
    )

    subparsers = parser.add_subparsers(dest="module", help="Available modules")

    _add_openapi_parser(subparsers)
    _add_graphql_parser(subparsers)
    _add_database_parser(subparsers)
    _add_contract_parser(subparsers)
    _add_jsonschema_parser(subparsers)
    _add_asyncapi_parser(subparsers)
    _add_mock_parser(subparsers)
    _add_codegen_parser(subparsers)
    _add_docs_parser(subparsers)
    _add_protobuf_parser(subparsers)
    _add_avro_parser(subparsers)
    _add_audit_parser(subparsers)

    return parser
