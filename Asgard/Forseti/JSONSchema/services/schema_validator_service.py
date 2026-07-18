"""
Schema Validator Service.

Validates data against JSON Schemas.

Since the compile-then-run uplift, this service is a thin compatibility layer
over SchemaCompilerService: schemas are compiled once (cached by content
hash) into checker-closure trees supporting draft-04/06/07, 2019-09 and
2020-12 dialects, $defs / anchors / cyclic $refs, and dialect-aware keyword
semantics. The public API (validate / validate_file / generate_report) is
unchanged; results additionally carry the detected `dialect`.
"""

import json
import time
import yaml  # type: ignore[import-untyped]
from pathlib import Path
from typing import Any, Optional

from Asgard.Forseti.JSONSchema.models.jsonschema_models import (
    JSONSchemaConfig,
    JSONSchemaValidationResult,
    JSONSchemaValidationError,
)
from Asgard.Forseti.JSONSchema.utilities.jsonschema_utils import load_schema_file
from Asgard.Forseti.JSONSchema.services.schema_compiler_service import (
    DEFAULT_FORMAT_PATTERNS,
    SchemaCompilerService,
)
from Asgard.Forseti.JSONSchema.services._compiler_keyword_helpers import check_json_type
from Asgard.Forseti.JSONSchema.services._schema_validator_service_helpers import (
    generate_markdown_report,
    generate_text_report,
)


class SchemaValidatorService:
    """
    Service for validating data against JSON Schemas.

    Provides comprehensive validation with detailed error reporting.

    Usage:
        service = SchemaValidatorService()
        result = service.validate(data, schema)
        if not result.is_valid:
            for error in result.errors:
                print(f"Error at {error.path}: {error.message}")
    """

    # Kept for backwards compatibility; the engine shares the same patterns.
    FORMAT_PATTERNS = DEFAULT_FORMAT_PATTERNS

    def __init__(self, config: Optional[JSONSchemaConfig] = None):
        self.config = config or JSONSchemaConfig()
        self._compiler = SchemaCompilerService(self.config)

    def validate(
        self,
        data: Any,
        schema: dict[str, Any] | str | Path,
        dialect: Optional[str] = None,
    ) -> JSONSchemaValidationResult:
        """
        Validate data against a schema (dict or path to a schema file).

        Args:
            data: Instance to validate.
            schema: Schema dict, or path to a JSON/YAML schema file.
            dialect: Optional dialect override (e.g. "draft-07", "2020-12").

        Returns:
            JSONSchemaValidationResult with errors and detected dialect.
        """
        start_time = time.time()
        schema_path = None
        if isinstance(schema, (str, Path)):
            schema_path = str(schema)
            try:
                schema = load_schema_file(Path(schema))
            except Exception as e:
                return JSONSchemaValidationResult(
                    is_valid=False,
                    errors=[JSONSchemaValidationError(path="$", message=f"Failed to load schema: {str(e)}", constraint="schema_load")],
                    schema_path=schema_path,
                    validation_time_ms=(time.time() - start_time) * 1000,
                )
        compiled = self._compiler.compile(schema, dialect=dialect, schema_path=schema_path)
        errors = compiled.validate(data)
        return JSONSchemaValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            schema_path=schema_path,
            dialect=compiled.dialect.value,
            validation_time_ms=(time.time() - start_time) * 1000,
        )

    def validate_file(self, data_path: str | Path, schema_path: str | Path) -> JSONSchemaValidationResult:
        start_time = time.time()
        try:
            data_file = Path(data_path)
            content = data_file.read_text(encoding="utf-8")
            if data_file.suffix.lower() in [".yaml", ".yml"]:
                data = yaml.safe_load(content)
            else:
                data = json.loads(content)
        except Exception as e:
            return JSONSchemaValidationResult(
                is_valid=False,
                errors=[JSONSchemaValidationError(path="$", message=f"Failed to load data file: {str(e)}", constraint="data_load")],
                data_path=str(data_path),
                schema_path=str(schema_path),
                validation_time_ms=(time.time() - start_time) * 1000,
            )
        result = self.validate(data, schema_path)
        result.data_path = str(data_path)
        return result

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Backwards-compatible type check (delegates to the engine's semantics)."""
        return check_json_type(value, expected_type)

    def generate_report(self, result: JSONSchemaValidationResult, format: str = "text") -> str:
        if format == "json":
            return json.dumps(result.model_dump(), indent=2, default=str)
        elif format == "markdown":
            return generate_markdown_report(result)
        else:
            return generate_text_report(result)
