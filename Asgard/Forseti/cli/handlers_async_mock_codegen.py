import argparse
import json
from pathlib import Path

from Asgard.Forseti.AsyncAPI import AsyncAPIValidatorService, AsyncAPIParserService, AsyncAPIConfig
from Asgard.Forseti.MockServer import (
    MockServerGeneratorService,
    MockServerConfig,
    MockDataGeneratorService,
    MockDataConfig,
)
from Asgard.Forseti.CodeGen import (
    TypeScriptGeneratorService,
    PythonGeneratorService,
    GolangGeneratorService,
    CodeGenConfig,
    HttpClientType,
)


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
