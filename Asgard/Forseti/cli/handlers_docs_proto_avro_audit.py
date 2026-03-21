import argparse
import json
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from Asgard.Forseti.Documentation import DocsGeneratorService, APIDocConfig, DocumentationFormat
from Asgard.Forseti.Protobuf import (
    ProtobufValidatorService,
    ProtobufConfig,
    ProtobufCompatibilityService,
)
from Asgard.Forseti.Avro import AvroValidatorService, AvroConfig, AvroCompatibilityService, CompatibilityMode
from Asgard.Forseti.OpenAPI import SpecValidatorService
from Asgard.Forseti.JSONSchema.utilities import load_schema_file, validate_schema_syntax


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


def _handle_audit(args: argparse.Namespace) -> int:
    """Handle audit command."""
    path = Path(args.path)

    if not path.exists():
        print(f"Error: Path not found: {path}")
        return 1

    results = []

    for spec_file in path.rglob("*.yaml"):
        if _looks_like_openapi(spec_file):
            service = SpecValidatorService()
            result = service.validate(str(spec_file))
            results.append({
                "file": str(spec_file),
                "type": "openapi",
                "valid": result.is_valid,
                "errors": result.error_count,
            })

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
