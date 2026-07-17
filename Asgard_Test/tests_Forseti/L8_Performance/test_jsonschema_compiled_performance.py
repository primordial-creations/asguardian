"""
Performance smoke tests for the compiled JSON Schema validation engine.

Plan 05 bar: repeat validation through the compilation cache must be much
faster than re-processing the schema on every call.
"""

import time

from Asgard.Forseti.JSONSchema.models.jsonschema_models import JSONSchemaConfig
from Asgard.Forseti.JSONSchema.services.schema_compiler_service import SchemaCompilerService
from Asgard.Forseti.JSONSchema.services.schema_validator_service import SchemaValidatorService

MID_SIZE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["id", "user", "items"],
    "properties": {
        "id": {"type": "string", "minLength": 8},
        "user": {
            "type": "object",
            "required": ["name", "email"],
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "email": {"type": "string"},
                "age": {"type": "integer", "minimum": 0, "maximum": 150},
                "roles": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            },
            "additionalProperties": False,
        },
        "items": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["sku", "qty"],
                "properties": {
                    "sku": {"type": "string", "pattern": "^[A-Z0-9-]+$"},
                    "qty": {"type": "integer", "minimum": 1},
                    "price": {"type": "number", "exclusiveMinimum": 0},
                },
            },
        },
        "status": {"enum": ["new", "paid", "shipped"]},
    },
}

SAMPLE = {
    "id": "ORDER-001",
    "user": {"name": "Ada", "email": "ada@example.com", "age": 36, "roles": ["admin", "buyer"]},
    "items": [{"sku": "AB-1", "qty": 2, "price": 9.5}, {"sku": "CD-2", "qty": 1, "price": 3.25}],
    "status": "paid",
}

ITERATIONS = 2000


class TestCompiledValidationPerformance:
    def test_precompiled_run_bulk_throughput(self):
        """10k-equivalent loop: 2000 validations must finish well under a second-scale budget."""
        compiled = SchemaCompilerService().compile(MID_SIZE_SCHEMA)
        start = time.perf_counter()
        for _ in range(ITERATIONS):
            assert compiled.is_valid(SAMPLE)
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"compiled validation too slow: {elapsed:.2f}s for {ITERATIONS} runs"

    def test_compile_cache_speedup_over_recompilation(self):
        """Cached compile+run must beat per-call recompilation by a wide margin."""
        service = SchemaCompilerService(JSONSchemaConfig())
        SchemaCompilerService.clear_cache()

        loops = 300
        start = time.perf_counter()
        for _ in range(loops):
            compiled = service.compile(MID_SIZE_SCHEMA, use_cache=False)
            compiled.validate(SAMPLE)
        uncached = time.perf_counter() - start

        SchemaCompilerService.clear_cache()
        start = time.perf_counter()
        for _ in range(loops):
            compiled = service.compile(MID_SIZE_SCHEMA)  # cache hit after first
            compiled.validate(SAMPLE)
        cached = time.perf_counter() - start

        assert cached < uncached / 2, (
            f"expected >=2x speedup from compilation cache; cached={cached:.4f}s uncached={uncached:.4f}s"
        )

    def test_validator_service_repeat_validation_uses_cache(self):
        service = SchemaValidatorService()
        # warm
        assert service.validate(SAMPLE, MID_SIZE_SCHEMA).is_valid
        start = time.perf_counter()
        for _ in range(500):
            service.validate(SAMPLE, MID_SIZE_SCHEMA)
        elapsed = time.perf_counter() - start
        assert elapsed < 3.0, f"repeat validation too slow: {elapsed:.2f}s"
