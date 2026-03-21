import sys
import traceback
from typing import Optional

from Asgard.Forseti.cli._parser import create_parser
from Asgard.Forseti.cli.handlers_schema import (
    _handle_openapi,
    _handle_graphql,
    _handle_database,
    _handle_contract,
    _handle_jsonschema,
)
from Asgard.Forseti.cli.handlers_async_mock_codegen import (
    _handle_asyncapi,
    _handle_mock,
    _handle_codegen,
)
from Asgard.Forseti.cli.handlers_docs_proto_avro_audit import (
    _handle_docs,
    _handle_protobuf,
    _handle_avro,
    _handle_audit,
)


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


if __name__ == "__main__":
    sys.exit(main())
