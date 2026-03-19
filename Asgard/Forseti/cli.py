"""
Forseti CLI - Command-line interface for API and schema specification tools.

Named after the Norse god of justice and reconciliation who presides over
contracts and agreements.
"""

import argparse
import json
import sys
import traceback
import yaml  # type: ignore[import-untyped]
from pathlib import Path
from typing import Optional

from Asgard.Forseti.AsyncAPI import AsyncAPIValidatorService, AsyncAPIParserService, AsyncAPIConfig
from Asgard.Forseti.Avro import AvroValidatorService, AvroConfig, AvroCompatibilityService, CompatibilityMode
from Asgard.Forseti.CodeGen import (
    TypeScriptGeneratorService,
    PythonGeneratorService,
    GolangGeneratorService,
    CodeGenConfig,
    HttpClientType,
)
from Asgard.Forseti.Contracts import (
    ContractValidatorService,
    CompatibilityCheckerService,
    BreakingChangeDetectorService,
)
from Asgard.Forseti.Database import SchemaAnalyzerService, SchemaDiffService, MigrationGeneratorService
from Asgard.Forseti.Documentation import DocsGeneratorService, APIDocConfig, DocumentationFormat
from Asgard.Forseti.GraphQL import (
    SchemaValidatorService as GraphQLSchemaValidatorService,
    GraphQLConfig,
    SchemaGeneratorService as GraphQLSchemaGeneratorService,
    IntrospectionService,
)
from Asgard.Forseti.JSONSchema import (
    SchemaValidatorService as JSONSchemaValidatorService,
    JSONSchemaConfig,
    SchemaGeneratorService as JSONSchemaGeneratorService,
    SchemaInferenceService,
)
from Asgard.Forseti.JSONSchema.utilities import load_schema_file, validate_schema_syntax
from Asgard.Forseti.MockServer import (
    MockServerGeneratorService,
    MockServerConfig,
    MockDataGeneratorService,
    MockDataConfig,
)
from Asgard.Forseti.OpenAPI import (
    SpecValidatorService,
    OpenAPIConfig,
    SpecGeneratorService,
    SpecConverterService,
)
from Asgard.Forseti.OpenAPI.utilities import compare_specs
from Asgard.Forseti.Protobuf import (
    ProtobufValidatorService,
    ProtobufConfig,
    ProtobufCompatibilityService,
)


def add_performance_flags(parser: argparse.ArgumentParser) -> None:
    """Add performance-related flags to a parser (parallel, incremental, cache)."""
    parser.add_argument(
        "--parallel",
        "-P",
        action="store_true",
        help="Enable parallel processing for faster analysis",
    )
    parser.add_argument(
        "--workers",
        "-W",
        type=int,
        default=None,
        help="Number of worker processes (default: CPU count - 1)",
    )
    parser.add_argument(
        "--incremental",
        "-I",
        action="store_true",
        help="Enable incremental scanning (skip unchanged files)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable caching even if incremental mode is enabled",
    )
    parser.add_argument(
        "--baseline",
        "-B",
        type=str,
        default=None,
        help="Path to baseline file for filtering known issues",
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

    # Create subparsers for each module
    subparsers = parser.add_subparsers(dest="module", help="Available modules")

    # OpenAPI subparser
    _add_openapi_parser(subparsers)

    # GraphQL subparser
    _add_graphql_parser(subparsers)

    # Database subparser
    _add_database_parser(subparsers)

    # Contract subparser
    _add_contract_parser(subparsers)

    # JSONSchema subparser
    _add_jsonschema_parser(subparsers)

    # AsyncAPI subparser (new)
    _add_asyncapi_parser(subparsers)

    # Mock server subparser (new)
    _add_mock_parser(subparsers)

    # Code generation subparser (new)
    _add_codegen_parser(subparsers)

    # Documentation subparser (new)
    _add_docs_parser(subparsers)

    # Protobuf subparser (new)
    _add_protobuf_parser(subparsers)

    # Avro subparser (new)
    _add_avro_parser(subparsers)

    # Audit command (runs all applicable checks)
    _add_audit_parser(subparsers)

    return parser


def _add_openapi_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add OpenAPI subparser."""
    openapi = subparsers.add_parser(
        "openapi",
        help="OpenAPI/Swagger specification tools",
    )
    openapi_sub = openapi.add_subparsers(dest="command")

    # validate
    validate = openapi_sub.add_parser("validate", help="Validate OpenAPI specification")
    validate.add_argument("spec_file", help="Path to OpenAPI specification file")
    validate.add_argument("--strict", action="store_true", help="Enable strict validation")
    add_performance_flags(validate)

    # generate
    generate = openapi_sub.add_parser("generate", help="Generate OpenAPI spec from source")
    generate.add_argument("source_path", help="Path to source code")
    generate.add_argument("--output", "-o", help="Output file path")
    generate.add_argument("--title", help="API title")
    generate.add_argument("--version", help="API version")

    # convert
    convert = openapi_sub.add_parser("convert", help="Convert between OpenAPI versions")
    convert.add_argument("spec_file", help="Path to specification file")
    convert.add_argument("--target-version", choices=["2.0", "3.0", "3.1"], required=True)
    convert.add_argument("--output", "-o", help="Output file path")

    # diff
    diff = openapi_sub.add_parser("diff", help="Compare two OpenAPI specifications")
    diff.add_argument("spec1", help="First specification file")
    diff.add_argument("spec2", help="Second specification file")


def _add_graphql_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add GraphQL subparser."""
    graphql = subparsers.add_parser(
        "graphql",
        help="GraphQL schema tools",
    )
    graphql_sub = graphql.add_subparsers(dest="command")

    # validate
    validate = graphql_sub.add_parser("validate", help="Validate GraphQL schema")
    validate.add_argument("schema_file", help="Path to GraphQL schema file")
    validate.add_argument("--strict", action="store_true", help="Enable strict validation")
    add_performance_flags(validate)

    # generate
    generate = graphql_sub.add_parser("generate", help="Generate GraphQL schema")
    generate.add_argument("source_path", help="Path to source")
    generate.add_argument("--output", "-o", help="Output file path")

    # introspect
    introspect = graphql_sub.add_parser("introspect", help="Introspect GraphQL endpoint")
    introspect.add_argument("endpoint", help="GraphQL endpoint URL")
    introspect.add_argument("--output", "-o", help="Output file path")
    introspect.add_argument("--header", "-H", action="append", help="HTTP headers")


def _add_database_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add Database subparser."""
    database = subparsers.add_parser(
        "database",
        help="Database schema tools",
    )
    database_sub = database.add_subparsers(dest="command")

    # analyze
    analyze = database_sub.add_parser("analyze", help="Analyze database schema")
    analyze.add_argument("source", help="SQL file or connection string")
    analyze.add_argument("--output", "-o", help="Output file path")
    add_performance_flags(analyze)

    # diff
    diff = database_sub.add_parser("diff", help="Compare two database schemas")
    diff.add_argument("schema1", help="First schema file")
    diff.add_argument("schema2", help="Second schema file")
    diff.add_argument("--output", "-o", help="Output file path")

    # migrate
    migrate = database_sub.add_parser("migrate", help="Generate migration script")
    migrate.add_argument("diff_file", help="Schema diff file")
    migrate.add_argument("--output", "-o", help="Output file path")
    migrate.add_argument("--dialect", choices=["mysql", "postgresql", "sqlite"], default="mysql")


def _add_contract_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add Contract subparser."""
    contract = subparsers.add_parser(
        "contract",
        help="API contract testing tools",
    )
    contract_sub = contract.add_subparsers(dest="command")

    # validate
    validate = contract_sub.add_parser("validate", help="Validate implementation against contract")
    validate.add_argument("contract_file", help="Contract/specification file")
    validate.add_argument("implementation", help="Implementation specification file")
    add_performance_flags(validate)

    # check-compat
    compat = contract_sub.add_parser("check-compat", help="Check backward compatibility")
    compat.add_argument("old_spec", help="Old version specification")
    compat.add_argument("new_spec", help="New version specification")
    add_performance_flags(compat)

    # breaking-changes
    breaking = contract_sub.add_parser("breaking-changes", help="Detect breaking changes")
    breaking.add_argument("old_spec", help="Old version specification")
    breaking.add_argument("new_spec", help="New version specification")
    breaking.add_argument("--version", help="Version string for changelog")
    add_performance_flags(breaking)


def _add_jsonschema_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add JSONSchema subparser."""
    jsonschema = subparsers.add_parser(
        "jsonschema",
        help="JSON Schema tools",
    )
    jsonschema_sub = jsonschema.add_subparsers(dest="command")

    # validate
    validate = jsonschema_sub.add_parser("validate", help="Validate data against schema")
    validate.add_argument("schema_file", help="JSON Schema file")
    validate.add_argument("data_file", help="Data file to validate")
    validate.add_argument("--strict", action="store_true", help="Strict mode")
    add_performance_flags(validate)

    # generate
    generate = jsonschema_sub.add_parser("generate", help="Generate JSON Schema from types")
    generate.add_argument("source", help="Python source file with type definitions")
    generate.add_argument("--output", "-o", help="Output file path")
    generate.add_argument("--class", dest="class_name", help="Class name to generate from")

    # infer
    infer = jsonschema_sub.add_parser("infer", help="Infer schema from sample data")
    infer.add_argument("samples_file", help="File with sample data (JSON array)")
    infer.add_argument("--output", "-o", help="Output file path")
    infer.add_argument("--title", help="Schema title")


def _add_asyncapi_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add AsyncAPI subparser."""
    asyncapi = subparsers.add_parser(
        "asyncapi",
        help="AsyncAPI specification tools",
    )
    asyncapi_sub = asyncapi.add_subparsers(dest="command")

    # validate
    validate = asyncapi_sub.add_parser("validate", help="Validate AsyncAPI specification")
    validate.add_argument("spec_file", help="Path to AsyncAPI specification file")
    validate.add_argument("--strict", action="store_true", help="Enable strict validation")
    add_performance_flags(validate)

    # parse
    parse = asyncapi_sub.add_parser("parse", help="Parse and analyze AsyncAPI specification")
    parse.add_argument("spec_file", help="Path to AsyncAPI specification file")
    parse.add_argument("--output", "-o", help="Output file path")


def _add_mock_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add Mock server subparser."""
    mock = subparsers.add_parser(
        "mock",
        help="Mock server generation tools",
    )
    mock_sub = mock.add_subparsers(dest="command")

    # generate
    generate = mock_sub.add_parser("generate", help="Generate mock server from specification")
    generate.add_argument("spec_file", help="Path to OpenAPI or AsyncAPI specification file")
    generate.add_argument("--output", "-o", help="Output directory for generated files")
    generate.add_argument("--framework", choices=["flask", "fastapi", "express"], default="flask",
                         help="Server framework to generate (default: flask)")
    generate.add_argument("--port", type=int, default=8080, help="Port for mock server (default: 8080)")

    # data
    data = mock_sub.add_parser("data", help="Generate mock data from schema")
    data.add_argument("schema_file", help="Path to JSON Schema file")
    data.add_argument("--count", type=int, default=1, help="Number of items to generate (default: 1)")
    data.add_argument("--output", "-o", help="Output file path")
    data.add_argument("--seed", type=int, help="Random seed for reproducible generation")


def _add_codegen_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add Code generation subparser."""
    codegen = subparsers.add_parser(
        "codegen",
        help="API client code generation tools",
    )
    codegen_sub = codegen.add_subparsers(dest="command")

    # typescript
    typescript = codegen_sub.add_parser("typescript", help="Generate TypeScript client")
    typescript.add_argument("spec_file", help="Path to OpenAPI specification file")
    typescript.add_argument("--output", "-o", help="Output directory for generated files")
    typescript.add_argument("--http-client", choices=["fetch", "axios"], default="fetch",
                           help="HTTP client to use (default: fetch)")
    typescript.add_argument("--package-name", default="api-client", help="Package name (default: api-client)")

    # python
    python = codegen_sub.add_parser("python", help="Generate Python client")
    python.add_argument("spec_file", help="Path to OpenAPI specification file")
    python.add_argument("--output", "-o", help="Output directory for generated files")
    python.add_argument("--http-client", choices=["requests", "httpx", "aiohttp"], default="httpx",
                       help="HTTP client to use (default: httpx)")
    python.add_argument("--async", dest="use_async", action="store_true", help="Generate async client")
    python.add_argument("--package-name", default="api_client", help="Package name (default: api_client)")

    # golang
    golang = codegen_sub.add_parser("golang", help="Generate Go client")
    golang.add_argument("spec_file", help="Path to OpenAPI specification file")
    golang.add_argument("--output", "-o", help="Output directory for generated files")
    golang.add_argument("--package-name", default="apiclient", help="Package name (default: apiclient)")


def _add_docs_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add Documentation subparser."""
    docs = subparsers.add_parser(
        "docs",
        help="API documentation generation tools",
    )
    docs_sub = docs.add_subparsers(dest="command")

    # generate
    generate = docs_sub.add_parser("generate", help="Generate API documentation from specification")
    generate.add_argument("spec_file", help="Path to OpenAPI specification file")
    generate.add_argument("--output", "-o", help="Output directory for documentation")
    generate.add_argument("--format", dest="doc_format", choices=["html", "markdown"], default="html",
                         help="Documentation format (default: html)")
    generate.add_argument("--title", help="Override API title")
    generate.add_argument("--theme", choices=["default", "modern", "minimal", "dark"], default="default",
                         help="Documentation theme (default: default)")


def _add_protobuf_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add Protobuf subparser."""
    protobuf = subparsers.add_parser(
        "protobuf",
        help="Protocol Buffer schema tools",
    )
    protobuf_sub = protobuf.add_subparsers(dest="command")

    # validate
    validate = protobuf_sub.add_parser("validate", help="Validate Protocol Buffer schema")
    validate.add_argument("proto_file", help="Path to proto file")
    validate.add_argument("--strict", action="store_true", help="Enable strict validation")
    validate.add_argument("--no-naming-check", action="store_true",
                         help="Disable naming convention checks")
    add_performance_flags(validate)

    # check-compat
    compat = protobuf_sub.add_parser("check-compat", help="Check backward compatibility")
    compat.add_argument("old_proto", help="Old version proto file")
    compat.add_argument("new_proto", help="New version proto file")
    add_performance_flags(compat)


def _add_avro_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add Avro subparser."""
    avro = subparsers.add_parser(
        "avro",
        help="Apache Avro schema tools",
    )
    avro_sub = avro.add_subparsers(dest="command")

    # validate
    validate = avro_sub.add_parser("validate", help="Validate Avro schema")
    validate.add_argument("schema_file", help="Path to Avro schema file (.avsc)")
    validate.add_argument("--strict", action="store_true", help="Enable strict validation")
    validate.add_argument("--require-doc", action="store_true",
                         help="Require documentation on all types")
    add_performance_flags(validate)

    # check-compat
    compat = avro_sub.add_parser("check-compat", help="Check schema compatibility")
    compat.add_argument("old_schema", help="Old version schema file")
    compat.add_argument("new_schema", help="New version schema file")
    compat.add_argument("--mode", choices=["backward", "forward", "full"], default="backward",
                       help="Compatibility mode (default: backward)")
    add_performance_flags(compat)


def _add_audit_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add audit subparser."""
    audit = subparsers.add_parser(
        "audit",
        help="Run all applicable checks on a path",
    )
    audit.add_argument("path", help="Path to audit")
    audit.add_argument("--output", "-o", help="Output report path")
    add_performance_flags(audit)


def main(args: Optional[list[str]] = None) -> int:
    """Main entry point for the CLI."""
    parser = create_parser()
    parsed = parser.parse_args(args)

    if not parsed.module:
        parser.print_help()
        return 0

    try:
        if parsed.module == "openapi":
            return _handle_openapi(parsed)
        elif parsed.module == "graphql":
            return _handle_graphql(parsed)
        elif parsed.module == "database":
            return _handle_database(parsed)
        elif parsed.module == "contract":
            return _handle_contract(parsed)
        elif parsed.module == "jsonschema":
            return _handle_jsonschema(parsed)
        elif parsed.module == "asyncapi":
            return _handle_asyncapi(parsed)
        elif parsed.module == "mock":
            return _handle_mock(parsed)
        elif parsed.module == "codegen":
            return _handle_codegen(parsed)
        elif parsed.module == "docs":
            return _handle_docs(parsed)
        elif parsed.module == "protobuf":
            return _handle_protobuf(parsed)
        elif parsed.module == "avro":
            return _handle_avro(parsed)
        elif parsed.module == "audit":
            return _handle_audit(parsed)
        else:
            parser.print_help()
            return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if parsed.verbose:
            traceback.print_exc()
        return 1


def _handle_openapi(args: argparse.Namespace) -> int:
    """Handle OpenAPI commands."""
    if not args.command:
        print("Error: No command specified. Use 'forseti openapi --help' for options.")
        return 1

    if args.command == "validate":
        config = OpenAPIConfig(strict_mode=args.strict if hasattr(args, 'strict') else False)
        service = SpecValidatorService(config)
        result = service.validate_file(args.spec_file)
        print(service.generate_report(result, args.format))
        return 0 if result.is_valid else 1

    elif args.command == "generate":
        service = SpecGeneratorService()
        spec = service.from_fastapi_app(args.source_path)
        if args.output:
            service.save_spec(spec, args.output)
            print(f"Specification saved to {args.output}")
        else:
            print(json.dumps(spec, indent=2))
        return 0

    elif args.command == "convert":
        service = SpecConverterService()
        version_map = {"2.0": "2.0", "3.0": "3.0.0", "3.1": "3.1.0"}
        result = service.convert(args.spec_file, version_map[args.target_version])
        if args.output:
            with open(args.output, "w") as f:
                json.dump(result.converted_spec, f, indent=2)
            print(f"Converted specification saved to {args.output}")
        else:
            print(json.dumps(result.converted_spec, indent=2))
        return 0 if result.success else 1

    elif args.command == "diff":
        diff = compare_specs(args.spec1, args.spec2)
        print(json.dumps(diff, indent=2))
        return 0

    return 1


def _handle_graphql(args: argparse.Namespace) -> int:
    """Handle GraphQL commands."""
    if not args.command:
        print("Error: No command specified. Use 'forseti graphql --help' for options.")
        return 1

    if args.command == "validate":
        config = GraphQLConfig(strict_mode=args.strict if hasattr(args, 'strict') else False)
        service = GraphQLSchemaValidatorService(config)
        result = service.validate_file(args.schema_file)
        print(service.generate_report(result, args.format))
        return 0 if result.is_valid else 1

    elif args.command == "generate":
        service = GraphQLSchemaGeneratorService()
        # This would require loading Python modules
        print("Note: Generation from source requires importable Python modules")
        return 0

    elif args.command == "introspect":
        service = IntrospectionService()
        headers = {}
        if args.header:
            for h in args.header:
                key, value = h.split(":", 1)
                headers[key.strip()] = value.strip()
        result = service.introspect(args.endpoint, headers=headers if headers else None)
        if args.output:
            Path(args.output).write_text(result.sdl, encoding="utf-8")
            print(f"Schema saved to {args.output}")
        else:
            print(result.sdl)
        return 0

    return 1


def _handle_database(args: argparse.Namespace) -> int:
    """Handle Database commands."""
    if not args.command:
        print("Error: No command specified. Use 'forseti database --help' for options.")
        return 1

    if args.command == "analyze":
        service = SchemaAnalyzerService()
        schema = service.analyze_sql_file(args.source)
        if args.output:
            with open(args.output, "w") as f:
                json.dump(schema.model_dump(), f, indent=2)
            print(f"Schema analysis saved to {args.output}")
        else:
            print(json.dumps(schema.model_dump(), indent=2, default=str))
        return 0

    elif args.command == "diff":
        service = SchemaDiffService()
        result = service.diff_sql_files(args.schema1, args.schema2)
        print(service.generate_report(result, args.format))
        return 0 if not result.has_changes else 1

    elif args.command == "migrate":
        service = MigrationGeneratorService()
        # Load diff from file
        with open(args.diff_file) as f:
            diff_data = json.load(f)
        # This would need proper SchemaDiffResult conversion
        print("Migration generation from diff file not yet implemented")
        return 0

    return 1


def _handle_contract(args: argparse.Namespace) -> int:
    """Handle Contract commands."""
    if not args.command:
        print("Error: No command specified. Use 'forseti contract --help' for options.")
        return 1

    if args.command == "validate":
        service = ContractValidatorService()
        result = service.validate(args.contract_file, args.implementation)
        print(service.generate_report(result, args.format))
        return 0 if result.is_valid else 1

    elif args.command == "check-compat":
        service = CompatibilityCheckerService()
        result = service.check(args.old_spec, args.new_spec)
        print(service.generate_report(result, args.format))
        return 0 if result.is_compatible else 1

    elif args.command == "breaking-changes":
        service = BreakingChangeDetectorService()
        changes = service.detect(args.old_spec, args.new_spec)
        version = getattr(args, 'version', 'unknown')
        changelog = service.generate_changelog(changes, version)
        print(changelog)
        return 0 if not changes else 1

    return 1


def _handle_jsonschema(args: argparse.Namespace) -> int:
    """Handle JSONSchema commands."""
    if not args.command:
        print("Error: No command specified. Use 'forseti jsonschema --help' for options.")
        return 1

    if args.command == "validate":
        config = JSONSchemaConfig(strict_mode=args.strict if hasattr(args, 'strict') else True)
        service = JSONSchemaValidatorService(config)
        result = service.validate_file(args.data_file, args.schema_file)
        print(service.generate_report(result, args.format))
        return 0 if result.is_valid else 1

    elif args.command == "generate":
        service = JSONSchemaGeneratorService()
        # This would require loading Python modules
        print("Note: Generation requires importable Python modules")
        print("Use Python API: SchemaGeneratorService().from_pydantic(YourModel)")
        return 0

    elif args.command == "infer":
        service = SchemaInferenceService()
        result = service.infer_from_file(args.samples_file, title=args.title)
        if args.output:
            with open(args.output, "w") as f:
                json.dump(result.schema, f, indent=2)
            print(f"Inferred schema saved to {args.output}")
            print(f"Confidence: {result.confidence:.1%}")
        else:
            print(service.generate_report(result, args.format))
        return 0

    return 1


def _handle_audit(args: argparse.Namespace) -> int:
    """Handle audit command."""
    path = Path(args.path)

    if not path.exists():
        print(f"Error: Path not found: {path}")
        return 1

    results = []

    # Find and validate OpenAPI specs
    for spec_file in path.rglob("*.yaml"):
        if _looks_like_openapi(spec_file):
            service = SpecValidatorService()
            result = service.validate_file(str(spec_file))
            results.append({
                "file": str(spec_file),
                "type": "openapi",
                "valid": result.is_valid,
                "errors": result.error_count,
            })

    # Find and validate JSON Schemas
    for schema_file in path.rglob("*.schema.json"):
        try:
            schema = load_schema_file(schema_file)
            errors = validate_schema_syntax(schema)
            results.append({
                "file": str(schema_file),
                "type": "jsonschema",
                "valid": len(errors) == 0,
                "errors": len(errors),
            })
        except Exception as e:
            results.append({
                "file": str(schema_file),
                "type": "jsonschema",
                "valid": False,
                "errors": 1,
                "message": str(e),
            })

    # Find and validate Protobuf schemas
    for proto_file in path.rglob("*.proto"):
        try:
            service = ProtobufValidatorService()
            result = service.validate(str(proto_file))
            results.append({
                "file": str(proto_file),
                "type": "protobuf",
                "valid": result.is_valid,
                "errors": result.error_count,
            })
        except Exception as e:
            results.append({
                "file": str(proto_file),
                "type": "protobuf",
                "valid": False,
                "errors": 1,
                "message": str(e),
            })

    # Find and validate Avro schemas
    for avro_file in path.rglob("*.avsc"):
        try:
            service = AvroValidatorService()
            result = service.validate(str(avro_file))
            results.append({
                "file": str(avro_file),
                "type": "avro",
                "valid": result.is_valid,
                "errors": result.error_count,
            })
        except Exception as e:
            results.append({
                "file": str(avro_file),
                "type": "avro",
                "valid": False,
                "errors": 1,
                "message": str(e),
            })

    # Print summary
    print("=" * 60)
    print("Forseti Audit Report")
    print("=" * 60)
    print(f"Path: {path}")
    print(f"Files checked: {len(results)}")
    print("-" * 60)

    valid_count = sum(1 for r in results if r["valid"])
    print(f"Valid: {valid_count}/{len(results)}")

    if args.format == "json":
        print(json.dumps(results, indent=2))
    else:
        for result in results:
            status = "PASS" if result["valid"] else "FAIL"
            print(f"[{status}] {result['file']} ({result['type']})")

    print("=" * 60)

    return 0 if valid_count == len(results) else 1


def _handle_asyncapi(args: argparse.Namespace) -> int:
    """Handle AsyncAPI commands."""
    if not args.command:
        print("Error: No command specified. Use 'forseti asyncapi --help' for options.")
        return 1

    if args.command == "validate":
        config = AsyncAPIConfig(strict_mode=args.strict if hasattr(args, 'strict') else False)
        service = AsyncAPIValidatorService(config)
        result = service.validate(args.spec_file)
        print(service.generate_report(result, args.format))
        return 0 if result.is_valid else 1

    elif args.command == "parse":
        parser_service = AsyncAPIParserService()
        spec = parser_service.parse(args.spec_file)
        report = parser_service.generate_report()

        if hasattr(args, 'output') and args.output:
            with open(args.output, "w") as f:
                json.dump(report.model_dump(), f, indent=2, default=str)
            print(f"Report saved to {args.output}")
        else:
            print(f"Title: {spec.info.title}")
            print(f"Version: {spec.info.version}")
            print(f"Channels: {spec.channel_count}")
            print(f"Servers: {spec.server_count}")
            print(f"Messages: {report.message_count}")
        return 0

    return 1


def _handle_mock(args: argparse.Namespace) -> int:
    """Handle Mock server commands."""
    if not args.command:
        print("Error: No command specified. Use 'forseti mock --help' for options.")
        return 1

    if args.command == "generate":
        config = MockServerConfig(
            server_framework=args.framework if hasattr(args, 'framework') else "flask",
            port=args.port if hasattr(args, 'port') else 8080,
        )
        service = MockServerGeneratorService(config)

        output_dir = args.output if hasattr(args, 'output') and args.output else None
        result = service.generate_from_openapi(args.spec_file, output_dir)

        if args.format == "json":
            print(json.dumps({
                "success": result.success,
                "files": [f.path for f in result.generated_files],
                "warnings": result.warnings,
                "errors": result.errors,
            }, indent=2))
        else:
            if result.success:
                print(f"Mock server generated successfully!")
                print(f"Framework: {config.server_framework}")
                print(f"Files generated:")
                for f in result.generated_files:
                    print(f"  - {f.path}")
                if output_dir:
                    print(f"\nTo run the server:")
                    if config.server_framework == "flask":
                        print(f"  cd {output_dir} && pip install -r requirements.txt && python server.py")
                    elif config.server_framework == "fastapi":
                        print(f"  cd {output_dir} && pip install -r requirements.txt && python server.py")
                    else:
                        print(f"  cd {output_dir} && npm install && npm start")
            else:
                print("Error generating mock server:")
                for err in result.errors:
                    print(f"  - {err}")
                return 1

        return 0

    elif args.command == "data":
        config = MockDataConfig()
        service = MockDataGeneratorService(config)

        if hasattr(args, 'seed') and args.seed:
            service.set_seed(args.seed)

        # Load schema
        schema_path = Path(args.schema_file)
        if not schema_path.exists():
            print(f"Error: Schema file not found: {schema_path}")
            return 1

        with open(schema_path) as f:
            schema = json.load(f)

        count = args.count if hasattr(args, 'count') else 1
        results = []
        for _ in range(count):
            result = service.generate_from_schema(schema)
            results.append(result.data)

        output_data = results[0] if count == 1 else results

        if hasattr(args, 'output') and args.output:
            with open(args.output, "w") as f:
                json.dump(output_data, f, indent=2)
            print(f"Mock data saved to {args.output}")
        else:
            print(json.dumps(output_data, indent=2))

        return 0

    return 1


def _handle_codegen(args: argparse.Namespace) -> int:
    """Handle Code generation commands."""
    if not args.command:
        print("Error: No command specified. Use 'forseti codegen --help' for options.")
        return 1

    output_dir = args.output if hasattr(args, 'output') and args.output else None

    if args.command == "typescript":
        http_client = HttpClientType.AXIOS if getattr(args, 'http_client', 'fetch') == 'axios' else HttpClientType.FETCH
        config = CodeGenConfig(
            http_client=http_client,
            package_name=getattr(args, 'package_name', 'api-client'),
        )
        service = TypeScriptGeneratorService(config)
        result = service.generate(args.spec_file, output_dir)

        if args.format == "json":
            print(json.dumps({
                "success": result.success,
                "files": [f.path for f in result.generated_files],
                "types_generated": result.types_generated,
                "methods_generated": result.methods_generated,
                "total_lines": result.total_lines,
                "warnings": result.warnings,
            }, indent=2))
        else:
            print(f"TypeScript client generated!")
            print(f"Types: {result.types_generated}")
            print(f"Methods: {result.methods_generated}")
            print(f"Files:")
            for f in result.generated_files:
                print(f"  - {f.path} ({f.line_count} lines)")

        return 0 if result.success else 1

    elif args.command == "python":
        http_client_map = {
            "requests": HttpClientType.REQUESTS,
            "httpx": HttpClientType.HTTPX,
            "aiohttp": HttpClientType.AIOHTTP,
        }
        http_client = http_client_map.get(getattr(args, 'http_client', 'httpx'), HttpClientType.HTTPX)
        config = CodeGenConfig(
            http_client=http_client,
            package_name=getattr(args, 'package_name', 'api_client'),
            use_async=getattr(args, 'use_async', False),
        )
        service = PythonGeneratorService(config)
        result = service.generate(args.spec_file, output_dir)

        if args.format == "json":
            print(json.dumps({
                "success": result.success,
                "files": [f.path for f in result.generated_files],
                "types_generated": result.types_generated,
                "methods_generated": result.methods_generated,
                "total_lines": result.total_lines,
                "warnings": result.warnings,
            }, indent=2))
        else:
            print(f"Python client generated!")
            print(f"Types: {result.types_generated}")
            print(f"Methods: {result.methods_generated}")
            print(f"Files:")
            for f in result.generated_files:
                print(f"  - {f.path} ({f.line_count} lines)")

        return 0 if result.success else 1

    elif args.command == "golang":
        config = CodeGenConfig(
            package_name=getattr(args, 'package_name', 'apiclient'),
        )
        service = GolangGeneratorService(config)
        result = service.generate(args.spec_file, output_dir)

        if args.format == "json":
            print(json.dumps({
                "success": result.success,
                "files": [f.path for f in result.generated_files],
                "types_generated": result.types_generated,
                "methods_generated": result.methods_generated,
                "total_lines": result.total_lines,
                "warnings": result.warnings,
            }, indent=2))
        else:
            print(f"Go client generated!")
            print(f"Types: {result.types_generated}")
            print(f"Methods: {result.methods_generated}")
            print(f"Files:")
            for f in result.generated_files:
                print(f"  - {f.path} ({f.line_count} lines)")

        return 0 if result.success else 1

    return 1


def _handle_docs(args: argparse.Namespace) -> int:
    """Handle Documentation commands."""
    if not args.command:
        print("Error: No command specified. Use 'forseti docs --help' for options.")
        return 1

    if args.command == "generate":
        format_map = {
            "html": DocumentationFormat.HTML,
            "markdown": DocumentationFormat.MARKDOWN,
        }
        doc_format = format_map.get(getattr(args, 'doc_format', 'html'), DocumentationFormat.HTML)

        config = APIDocConfig(
            output_format=doc_format,
            title=getattr(args, 'title', None),
        )
        service = DocsGeneratorService(config)

        output_dir = args.output if hasattr(args, 'output') and args.output else None
        result = service.generate(args.spec_file, output_dir)

        if args.format == "json":
            print(json.dumps({
                "success": result.success,
                "api_title": result.api_title,
                "api_version": result.api_version,
                "endpoints": result.endpoint_count,
                "schemas": result.schema_count,
                "files": [d.path for d in result.generated_documents],
                "warnings": result.warnings,
            }, indent=2))
        else:
            if result.success:
                print(f"Documentation generated for {result.api_title} v{result.api_version}")
                print(f"Endpoints documented: {result.endpoint_count}")
                print(f"Schemas documented: {result.schema_count}")
                print(f"Files generated:")
                for doc in result.generated_documents:
                    print(f"  - {doc.path} ({doc.size_bytes} bytes)")
            else:
                print("Error generating documentation:")
                for err in result.errors:
                    print(f"  - {err}")
                return 1

        return 0

    return 1


def _handle_protobuf(args: argparse.Namespace) -> int:
    """Handle Protobuf commands."""
    if not args.command:
        print("Error: No command specified. Use 'forseti protobuf --help' for options.")
        return 1

    if args.command == "validate":
        config = ProtobufConfig(
            strict_mode=args.strict if hasattr(args, 'strict') else False,
            check_naming_conventions=not (args.no_naming_check if hasattr(args, 'no_naming_check') else False),
        )
        service = ProtobufValidatorService(config)
        result = service.validate(args.proto_file)
        print(service.generate_report(result, args.format))
        return 0 if result.is_valid else 1

    elif args.command == "check-compat":
        service = ProtobufCompatibilityService()
        result = service.check(args.old_proto, args.new_proto)
        print(service.generate_report(result, args.format))
        return 0 if result.is_compatible else 1

    return 1


def _handle_avro(args: argparse.Namespace) -> int:
    """Handle Avro commands."""
    if not args.command:
        print("Error: No command specified. Use 'forseti avro --help' for options.")
        return 1

    if args.command == "validate":
        config = AvroConfig(
            strict_mode=args.strict if hasattr(args, 'strict') else False,
            require_doc=args.require_doc if hasattr(args, 'require_doc') else False,
        )
        service = AvroValidatorService(config)
        result = service.validate(args.schema_file)
        print(service.generate_report(result, args.format))
        return 0 if result.is_valid else 1

    elif args.command == "check-compat":
        mode_map = {
            "backward": CompatibilityMode.BACKWARD,
            "forward": CompatibilityMode.FORWARD,
            "full": CompatibilityMode.FULL,
        }
        mode = mode_map.get(getattr(args, 'mode', 'backward'), CompatibilityMode.BACKWARD)

        service = AvroCompatibilityService()
        result = service.check(args.old_schema, args.new_schema, mode)
        print(service.generate_report(result, args.format))
        return 0 if result.is_compatible else 1

    return 1


def _looks_like_openapi(file_path: Path) -> bool:
    """Check if a file looks like an OpenAPI specification."""
    try:
        content = file_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        if isinstance(data, dict):
            return "openapi" in data or "swagger" in data
    except Exception:
        pass
    return False


def _looks_like_asyncapi(file_path: Path) -> bool:
    """Check if a file looks like an AsyncAPI specification."""
    try:
        content = file_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        if isinstance(data, dict):
            return "asyncapi" in data
    except Exception:
        pass
    return False


if __name__ == "__main__":
    sys.exit(main())
