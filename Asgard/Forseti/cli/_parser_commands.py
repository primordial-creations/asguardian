import argparse

from Asgard.Forseti.cli._parser_flags import add_performance_flags


def _add_openapi_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add OpenAPI subparser."""
    openapi = subparsers.add_parser(
        "openapi",
        help="OpenAPI/Swagger specification tools",
    )
    openapi_sub = openapi.add_subparsers(dest="command")

    validate = openapi_sub.add_parser("validate", help="Validate OpenAPI specification")
    validate.add_argument("spec_file", help="Path to OpenAPI specification file")
    validate.add_argument("--strict", action="store_true", help="Enable strict validation")
    add_performance_flags(validate)

    generate = openapi_sub.add_parser("generate", help="Generate OpenAPI spec from source")
    generate.add_argument("source_path", help="Path to source code")
    generate.add_argument("--output", "-o", help="Output file path")
    generate.add_argument("--title", help="API title")
    generate.add_argument("--version", help="API version")

    convert = openapi_sub.add_parser("convert", help="Convert between OpenAPI versions")
    convert.add_argument("spec_file", help="Path to specification file")
    convert.add_argument("--target-version", choices=["2.0", "3.0", "3.1"], required=True)
    convert.add_argument("--output", "-o", help="Output file path")

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

    validate = graphql_sub.add_parser("validate", help="Validate GraphQL schema")
    validate.add_argument("schema_file", help="Path to GraphQL schema file")
    validate.add_argument("--strict", action="store_true", help="Enable strict validation")
    add_performance_flags(validate)

    generate = graphql_sub.add_parser("generate", help="Generate GraphQL schema")
    generate.add_argument("source_path", help="Path to source")
    generate.add_argument("--output", "-o", help="Output file path")

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

    analyze = database_sub.add_parser("analyze", help="Analyze database schema")
    analyze.add_argument("source", help="SQL file or connection string")
    analyze.add_argument("--output", "-o", help="Output file path")
    add_performance_flags(analyze)

    diff = database_sub.add_parser("diff", help="Compare two database schemas")
    diff.add_argument("schema1", help="First schema file")
    diff.add_argument("schema2", help="Second schema file")
    diff.add_argument("--output", "-o", help="Output file path")

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

    validate = contract_sub.add_parser("validate", help="Validate implementation against contract")
    validate.add_argument("contract_file", help="Contract/specification file")
    validate.add_argument("implementation", help="Implementation specification file")
    add_performance_flags(validate)

    compat = contract_sub.add_parser("check-compat", help="Check backward compatibility")
    compat.add_argument("old_spec", help="Old version specification")
    compat.add_argument("new_spec", help="New version specification")
    add_performance_flags(compat)

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

    validate = jsonschema_sub.add_parser("validate", help="Validate data against schema")
    validate.add_argument("schema_file", help="JSON Schema file")
    validate.add_argument("data_file", help="Data file to validate")
    validate.add_argument("--strict", action="store_true", help="Strict mode")
    add_performance_flags(validate)

    generate = jsonschema_sub.add_parser("generate", help="Generate JSON Schema from types")
    generate.add_argument("source", help="Python source file with type definitions")
    generate.add_argument("--output", "-o", help="Output file path")
    generate.add_argument("--class", dest="class_name", help="Class name to generate from")

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

    validate = asyncapi_sub.add_parser("validate", help="Validate AsyncAPI specification")
    validate.add_argument("spec_file", help="Path to AsyncAPI specification file")
    validate.add_argument("--strict", action="store_true", help="Enable strict validation")
    add_performance_flags(validate)

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

    generate = mock_sub.add_parser("generate", help="Generate mock server from specification")
    generate.add_argument("spec_file", help="Path to OpenAPI or AsyncAPI specification file")
    generate.add_argument("--output", "-o", help="Output directory for generated files")
    generate.add_argument("--framework", choices=["flask", "fastapi", "express"], default="flask",
                         help="Server framework to generate (default: flask)")
    generate.add_argument("--port", type=int, default=8080, help="Port for mock server (default: 8080)")

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

    typescript = codegen_sub.add_parser("typescript", help="Generate TypeScript client")
    typescript.add_argument("spec_file", help="Path to OpenAPI specification file")
    typescript.add_argument("--output", "-o", help="Output directory for generated files")
    typescript.add_argument("--http-client", choices=["fetch", "axios"], default="fetch",
                           help="HTTP client to use (default: fetch)")
    typescript.add_argument("--package-name", default="api-client", help="Package name (default: api-client)")

    python = codegen_sub.add_parser("python", help="Generate Python client")
    python.add_argument("spec_file", help="Path to OpenAPI specification file")
    python.add_argument("--output", "-o", help="Output directory for generated files")
    python.add_argument("--http-client", choices=["requests", "httpx", "aiohttp"], default="httpx",
                       help="HTTP client to use (default: httpx)")
    python.add_argument("--async", dest="use_async", action="store_true", help="Generate async client")
    python.add_argument("--package-name", default="api_client", help="Package name (default: api_client)")

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

    validate = protobuf_sub.add_parser("validate", help="Validate Protocol Buffer schema")
    validate.add_argument("proto_file", help="Path to proto file")
    validate.add_argument("--strict", action="store_true", help="Enable strict validation")
    validate.add_argument("--no-naming-check", action="store_true",
                         help="Disable naming convention checks")
    add_performance_flags(validate)

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

    validate = avro_sub.add_parser("validate", help="Validate Avro schema")
    validate.add_argument("schema_file", help="Path to Avro schema file (.avsc)")
    validate.add_argument("--strict", action="store_true", help="Enable strict validation")
    validate.add_argument("--require-doc", action="store_true",
                         help="Require documentation on all types")
    add_performance_flags(validate)

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
