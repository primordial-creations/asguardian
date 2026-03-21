"""
Schema Inference Helpers.

Helper functions for SchemaInferenceService.
"""

import json
import re
from collections import Counter
from typing import Any, Optional

from Asgard.Forseti.JSONSchema.models.jsonschema_models import (
    JSONSchemaConfig,
    JSONSchemaInferenceResult,
)


def generate_text_report(result: JSONSchemaInferenceResult) -> str:
    """Generate a text format report."""
    lines = []
    lines.append("=" * 60)
    lines.append("JSON Schema Inference Report")
    lines.append("=" * 60)
    lines.append(f"Samples Analyzed: {result.sample_count}")
    lines.append(f"Confidence: {result.confidence:.1%}")
    lines.append("-" * 60)

    if result.warnings:
        lines.append("\nWarnings:")
        for warning in result.warnings:
            lines.append(f"  - {warning}")

    lines.append("\nInferred Schema:")
    lines.append(json.dumps(result.schema, indent=2))

    lines.append("=" * 60)
    return "\n".join(lines)


def generate_markdown_report(result: JSONSchemaInferenceResult) -> str:
    """Generate a markdown format report."""
    lines = []
    lines.append("# JSON Schema Inference Report\n")
    lines.append(f"- **Samples Analyzed**: {result.sample_count}")
    lines.append(f"- **Confidence**: {result.confidence:.1%}\n")

    if result.warnings:
        lines.append("## Warnings\n")
        for warning in result.warnings:
            lines.append(f"- {warning}")
        lines.append("")

    lines.append("## Inferred Schema\n")
    lines.append("```json")
    lines.append(json.dumps(result.schema, indent=2))
    lines.append("```")

    return "\n".join(lines)


def detect_format(value: str) -> Optional[str]:
    """Detect format of a string value."""
    patterns = [
        (r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", "date-time"),
        (r"^\d{4}-\d{2}-\d{2}$", "date"),
        (r"^\d{2}:\d{2}:\d{2}$", "time"),
        (r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", "email"),
        (r"^https?://", "uri"),
        (r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", "uuid"),
        (r"^(\d{1,3}\.){3}\d{1,3}$", "ipv4"),
    ]

    for pattern, fmt in patterns:
        if re.match(pattern, value, re.IGNORECASE):
            return fmt

    return None


def detect_common_pattern(samples: list[str]) -> Optional[str]:
    """Detect common pattern in string samples."""
    if len(samples) < 2:
        return None

    lengths = set(len(s) for s in samples)
    if len(lengths) == 1:
        length = list(lengths)[0]

        pattern_chars = []
        for i in range(length):
            chars_at_pos = set(s[i] for s in samples)

            if len(chars_at_pos) == 1:
                pattern_chars.append(re.escape(list(chars_at_pos)[0]))
            elif all(c.isdigit() for c in chars_at_pos):
                pattern_chars.append(r"\d")
            elif all(c.isalpha() for c in chars_at_pos):
                if all(c.isupper() for c in chars_at_pos):
                    pattern_chars.append("[A-Z]")
                elif all(c.islower() for c in chars_at_pos):
                    pattern_chars.append("[a-z]")
                else:
                    pattern_chars.append("[a-zA-Z]")
            else:
                pattern_chars.append(".")

        pattern = "^" + "".join(pattern_chars) + "$"

        regex = re.compile(pattern)
        if all(regex.match(s) for s in samples):
            return pattern

    return None


def analyze_array_samples(samples: list[list[Any]], analyze_samples_fn: Any) -> dict[str, Any]:
    """Analyze array samples to extract item information."""
    if not samples:
        return {}

    all_items: list[Any] = []
    for sample in samples:
        all_items.extend(sample)

    lengths = [len(s) for s in samples]

    return {
        "min_length": min(lengths) if lengths else 0,
        "max_length": max(lengths) if lengths else 0,
        "avg_length": sum(lengths) / len(lengths) if lengths else 0,
        "total_items": len(all_items),
        "item_analysis": analyze_samples_fn(all_items) if all_items else {},
    }


def analyze_object_samples(samples: list[dict[str, Any]], analyze_samples_fn: Any) -> dict[str, Any]:
    """Analyze object samples to extract property information."""
    if not samples:
        return {}

    property_analysis: dict[str, dict[str, Any]] = {}
    all_keys: set[str] = set()

    for sample in samples:
        all_keys.update(sample.keys())

    required_keys: set[str] = set(all_keys)
    for sample in samples:
        required_keys &= set(sample.keys())

    for key in all_keys:
        values = [s[key] for s in samples if key in s]
        property_analysis[key] = {
            "presence_count": len(values),
            "total_samples": len(samples),
            "required": key in required_keys,
            "analysis": analyze_samples_fn(values) if values else {},
        }

    return {
        "all_keys": list(all_keys),
        "required_keys": list(required_keys),
        "properties": property_analysis,
    }


def analyze_string_samples(samples: list[str], config: JSONSchemaConfig) -> dict[str, Any]:
    """Analyze string samples for format detection."""
    analysis: dict[str, Any] = {}

    if not samples:
        return analysis

    lengths = [len(s) for s in samples]
    analysis["min_length"] = min(lengths)
    analysis["max_length"] = max(lengths)
    analysis["avg_length"] = sum(lengths) / len(lengths)

    if config.infer_formats:
        format_counts: Counter[str] = Counter()

        for s in samples:
            fmt = detect_format(s)
            if fmt:
                format_counts[fmt] += 1

        if format_counts:
            most_common_format, count = format_counts.most_common(1)[0]
            if count == len(samples):
                analysis["detected_format"] = most_common_format
            elif count > len(samples) * 0.8:
                analysis["likely_format"] = most_common_format
                analysis["format_confidence"] = count / len(samples)

    if all(samples):
        common_pattern = detect_common_pattern(samples)
        if common_pattern:
            analysis["possible_pattern"] = common_pattern

    return analysis


def analyze_scalar_samples(samples: list[Any], config: JSONSchemaConfig) -> dict[str, Any]:
    """Analyze scalar samples for format and enum detection."""
    analysis: dict[str, Any] = {}

    if not samples:
        return analysis

    types = set(type(s).__name__ for s in samples)
    analysis["types"] = list(types)

    if all(isinstance(s, str) for s in samples):
        analysis["string_analysis"] = analyze_string_samples(samples, config)

    if all(isinstance(s, (int, float)) for s in samples):
        numeric = [s for s in samples if isinstance(s, (int, float))]
        analysis["numeric_analysis"] = {
            "min": min(numeric),
            "max": max(numeric),
            "all_integers": all(isinstance(s, int) for s in samples),
        }

    if config.infer_enums:
        unique_values = set(str(s) for s in samples)
        if len(unique_values) <= config.enum_threshold:
            analysis["possible_enum"] = True
            analysis["enum_values"] = list(set(samples))

    return analysis


def generate_scalar_schema(value_analysis: dict[str, Any], json_type: str, config: JSONSchemaConfig) -> dict[str, Any]:
    """Generate scalar schema from value analysis."""
    schema: dict[str, Any] = {}

    if json_type == "string":
        string_analysis = value_analysis.get("string_analysis", {})
        if "detected_format" in string_analysis:
            schema["format"] = string_analysis["detected_format"]
        if "possible_pattern" in string_analysis:
            schema["pattern"] = string_analysis["possible_pattern"]

    if json_type in ["integer", "number"]:
        numeric = value_analysis.get("numeric_analysis", {})
        if "min" in numeric:
            schema["minimum"] = numeric["min"]
        if "max" in numeric:
            schema["maximum"] = numeric["max"]

    if value_analysis.get("possible_enum") and config.infer_enums:
        schema["enum"] = value_analysis.get("enum_values", [])

    return schema


def generate_array_schema(items_analysis: dict[str, Any], generate_schema_fn: Any) -> dict[str, Any]:
    """Generate array schema from items analysis."""
    schema: dict[str, Any] = {}

    if "item_analysis" in items_analysis:
        items_schema = generate_schema_fn(items_analysis["item_analysis"])
        if items_schema:
            schema["items"] = items_schema

    if items_analysis.get("min_length", 0) > 0:
        schema["minItems"] = items_analysis["min_length"]

    return schema


def generate_object_schema(prop_analysis: dict[str, Any], generate_schema_fn: Any) -> dict[str, Any]:
    """Generate object schema from property analysis."""
    schema: dict[str, Any] = {}
    properties: dict[str, Any] = {}

    for key, prop_info in prop_analysis.get("properties", {}).items():
        prop_schema = generate_schema_fn(prop_info.get("analysis", {}))

        if not prop_info.get("required", True):
            if "type" in prop_schema:
                if isinstance(prop_schema["type"], list):
                    if "null" not in prop_schema["type"]:
                        prop_schema["type"].append("null")
                else:
                    prop_schema["type"] = [prop_schema["type"], "null"]

        properties[key] = prop_schema if prop_schema else {"type": "string"}

    if properties:
        schema["properties"] = properties

    required = prop_analysis.get("required_keys", [])
    if required:
        schema["required"] = required

    return schema
