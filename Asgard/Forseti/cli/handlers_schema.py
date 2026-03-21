import argparse
import json
from pathlib import Path

from Asgard.Forseti.OpenAPI import (
    SpecValidatorService,
    OpenAPIConfig,
    SpecGeneratorService,
    SpecConverterService,
)
from Asgard.Forseti.OpenAPI.utilities import compare_specs, save_spec_file
from Asgard.Forseti.GraphQL import (
    SchemaValidatorService as GraphQLSchemaValidatorService,
    GraphQLConfig,
    SchemaGeneratorService as GraphQLSchemaGeneratorService,
    IntrospectionService,
)
from Asgard.Forseti.Database import SchemaAnalyzerService, SchemaDiffService, MigrationGeneratorService
from Asgard.Forseti.Contracts import (
    ContractValidatorService,
    CompatibilityCheckerService,
    BreakingChangeDetectorService,
)
from Asgard.Forseti.JSONSchema import (
    SchemaValidatorService as JSONSchemaValidatorService,
    JSONSchemaConfig,
    SchemaGeneratorService as JSONSchemaGeneratorService,
    SchemaInferenceService,
)


def _handle_openapi(args: argparse.Namespace) -> int:
    """Handle OpenAPI commands."""
    if not args.command:
        print("Error: No command specified. Use 'forseti openapi --help' for options.")
        return 1

    if args.command == "validate":
        config = OpenAPIConfig(strict_mode=args.strict if hasattr(args, 'strict') else False)
        validator = SpecValidatorService(config)
        result = validator.validate(args.spec_file)
        print(validator.generate_report(result, args.format))
        return 0 if result.is_valid else 1

    elif args.command == "generate":
        generator = SpecGeneratorService()
        spec = generator.generate_from_fastapi(args.source_path)
        if args.output:
            save_spec_file(Path(args.output), generator.to_dict(spec))
            print(f"Specification saved to {args.output}")
        else:
            print(json.dumps(generator.to_dict(spec), indent=2))
        return 0

    elif args.command == "convert":
        converter = SpecConverterService()
        converted = converter.convert(args.spec_file, args.target_version)
        if args.output:
            with open(args.output, "w") as f:
                json.dump(converted, f, indent=2)
            print(f"Converted specification saved to {args.output}")
        else:
            print(json.dumps(converted, indent=2))
        return 0

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
        result = service.validate(args.schema_file)
        print(service.generate_report(result, args.format))
        return 0 if result.is_valid else 1

    elif args.command == "generate":
        service = GraphQLSchemaGeneratorService()
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
        analyzer = SchemaAnalyzerService()
        schema = analyzer.analyze_file(args.source)
        if args.output:
            with open(args.output, "w") as f:
                json.dump(schema.model_dump(), f, indent=2)
            print(f"Schema analysis saved to {args.output}")
        else:
            print(json.dumps(schema.model_dump(), indent=2, default=str))
        return 0

    elif args.command == "diff":
        differ = SchemaDiffService()
        result = differ.diff_schemas(args.schema1, args.schema2)
        print(differ.generate_report(result, args.format))
        return 0 if not result.has_changes else 1

    elif args.command == "migrate":
        service = MigrationGeneratorService()
        with open(args.diff_file) as f:
            diff_data = json.load(f)
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
