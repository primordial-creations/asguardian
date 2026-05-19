"""
Forseti L8 Performance Benchmarks

Benchmarks for Forseti schema validation and compatibility services.
Uses pytest-benchmark to measure throughput of core in-memory operations.
"""

import pytest

from Asgard.Forseti.Avro.services.avro_validator_service import AvroValidatorService
from Asgard.Forseti.Avro.services.avro_compatibility_service import AvroCompatibilityService
from Asgard.Forseti.JSONSchema.services.schema_validator_service import SchemaValidatorService


SIMPLE_AVRO_RECORD = {
    "type": "record",
    "name": "User",
    "namespace": "com.example",
    "fields": [
        {"name": "id", "type": "long"},
        {"name": "username", "type": "string"},
        {"name": "email", "type": "string"},
        {"name": "active", "type": "boolean", "default": True},
    ],
}

COMPLEX_AVRO_RECORD = {
    "type": "record",
    "name": "Order",
    "namespace": "com.example",
    "fields": [
        {"name": "orderId", "type": "long"},
        {"name": "customerId", "type": "long"},
        {"name": "status", "type": {"type": "enum", "name": "OrderStatus", "symbols": ["PENDING", "CONFIRMED", "SHIPPED", "DELIVERED", "CANCELLED"]}},
        {"name": "items", "type": {"type": "array", "items": {
            "type": "record",
            "name": "LineItem",
            "fields": [
                {"name": "productId", "type": "string"},
                {"name": "quantity", "type": "int"},
                {"name": "unitPrice", "type": "double"},
            ],
        }}},
        {"name": "metadata", "type": {"type": "map", "values": "string"}},
        {"name": "notes", "type": ["null", "string"], "default": None},
    ],
}

AVRO_RECORD_V2_COMPATIBLE = {
    "type": "record",
    "name": "User",
    "namespace": "com.example",
    "fields": [
        {"name": "id", "type": "long"},
        {"name": "username", "type": "string"},
        {"name": "email", "type": "string"},
        {"name": "active", "type": "boolean", "default": True},
        {"name": "displayName", "type": ["null", "string"], "default": None},
    ],
}

JSON_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Order",
    "type": "object",
    "required": ["orderId", "customerId", "items"],
    "properties": {
        "orderId": {"type": "integer", "minimum": 1},
        "customerId": {"type": "integer", "minimum": 1},
        "status": {"type": "string", "enum": ["pending", "confirmed", "shipped", "delivered"]},
        "items": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["productId", "quantity"],
                "properties": {
                    "productId": {"type": "string"},
                    "quantity": {"type": "integer", "minimum": 1},
                    "unitPrice": {"type": "number", "minimum": 0},
                },
                "additionalProperties": False,
            },
        },
        "notes": {"type": "string"},
    },
    "additionalProperties": False,
}


class TestForsetiPerformance:
    """L8 performance benchmarks for Forseti schema validation services."""

    def test_avro_validate_simple_record(self, benchmark):
        """Benchmark validation of a simple Avro record schema in memory."""
        service = AvroValidatorService()

        result = benchmark(service.validate_schema_data, SIMPLE_AVRO_RECORD)

        assert result is not None
        assert result.is_valid, f"Expected valid schema, errors: {result.errors}"

    def test_avro_validate_complex_record(self, benchmark):
        """Benchmark validation of a complex nested Avro record schema."""
        service = AvroValidatorService()

        result = benchmark(service.validate_schema_data, COMPLEX_AVRO_RECORD)

        assert result is not None
        assert result.is_valid, f"Expected valid schema, errors: {result.errors}"

    def test_avro_compatibility_check(self, benchmark):
        """Benchmark backward-compatibility check between two Avro schemas."""
        service = AvroCompatibilityService()

        result = benchmark(service.check_schemas, SIMPLE_AVRO_RECORD, AVRO_RECORD_V2_COMPATIBLE)

        assert result is not None
        assert result.is_compatible, f"Expected compatible schemas: {result.breaking_changes}"

    def test_json_schema_validate_data(self, benchmark):
        """Benchmark validating a data payload against a JSON Schema."""
        service = SchemaValidatorService()
        valid_data = {
            "orderId": 42,
            "customerId": 7,
            "status": "confirmed",
            "items": [
                {"productId": "SKU-001", "quantity": 2, "unitPrice": 9.99},
                {"productId": "SKU-002", "quantity": 1, "unitPrice": 49.99},
            ],
        }

        result = benchmark(service.validate, valid_data, JSON_SCHEMA)

        assert result is not None
        assert result.is_valid, f"Expected valid data, errors: {result.errors}"
