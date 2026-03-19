"""
Schema Inference Service.

Infers JSON Schemas from sample data.
"""

import json
import re
import yaml  # type: ignore[import-untyped]
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from Asgard.Forseti.JSONSchema.models.jsonschema_models import (
    JSONSchemaConfig,
    JSONSchemaInferenceResult,
)


class SchemaInferenceService:
    """
    Service for inferring JSON Schemas from sample data.

    Analyzes multiple samples to generate comprehensive schemas
    with format detection and enum inference.

    Usage:
        service = SchemaInferenceService()
        result = service.infer([sample1, sample2, sample3])
        schema = result.schema
    """

    def __init__(self, config: Optional[JSONSchemaConfig] = None):
        """
        Initialize the inference service.

        Args:
            config: Optional configuration for inference behavior.
        """
        self.config = config or JSONSchemaConfig()

    def infer(
        self,
        samples: list[Any],
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> JSONSchemaInferenceResult:
        """
        Infer JSON Schema from sample data.

        Args:
            samples: List of sample values to analyze.
            title: Optional schema title.
            description: Optional schema description.

        Returns:
            JSONSchemaInferenceResult with inferred schema.
        """
        if not samples:
            return JSONSchemaInferenceResult(
                schema={"$schema": self.config.schema_version},
                sample_count=0,
                confidence=0.0,
                warnings=["No samples provided"],
            )

        # Analyze samples
        analysis = self._analyze_samples(samples)

        # Generate schema from analysis
        schema = self._generate_schema(analysis)

        # Add metadata
        schema["$schema"] = self.config.schema_version
        if title:
            schema["title"] = title
        if description:
            schema["description"] = description

        # Calculate confidence
        confidence = self._calculate_confidence(analysis, len(samples))

        return JSONSchemaInferenceResult(
            schema=schema,
            sample_count=len(samples),
            confidence=confidence,
            warnings=analysis.get("warnings", []),
            statistics=analysis.get("statistics", {}),
        )

    def infer_from_file(
        self,
        file_path: str | Path,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> JSONSchemaInferenceResult:
        """
        Infer schema from a file containing samples.

        Args:
            file_path: Path to JSON or YAML file with samples.
            title: Optional schema title.
            description: Optional schema description.

        Returns:
            JSONSchemaInferenceResult with inferred schema.
        """
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")

        if path.suffix.lower() in [".yaml", ".yml"]:
            data = yaml.safe_load(content)
        else:
            data = json.loads(content)

        # Handle both array of samples and single sample
        if isinstance(data, list):
            samples = data
        else:
            samples = [data]

        return self.infer(samples, title, description)

    def _analyze_samples(self, samples: list[Any]) -> dict[str, Any]:
        """Analyze samples to extract type information."""
        analysis: dict[str, Any] = {
            "types": Counter(),
            "warnings": [],
            "statistics": {},
        }

        if not samples:
            return analysis

        # Check if all samples are same type
        first_type = type(samples[0])
        all_same_type = all(type(s) == first_type for s in samples)

        if not all_same_type:
            analysis["warnings"].append("Samples have mixed types")

        # Analyze based on primary type
        type_counts = Counter(type(s).__name__ for s in samples)
        analysis["types"] = type_counts
        analysis["statistics"]["type_distribution"] = dict(type_counts)

        # Deep analysis for objects
        if first_type is dict:
            analysis["properties"] = self._analyze_object_samples(
                [s for s in samples if isinstance(s, dict)]
            )
        elif first_type is list:
            analysis["items"] = self._analyze_array_samples(
                [s for s in samples if isinstance(s, list)]
            )
        else:
            analysis["value_analysis"] = self._analyze_scalar_samples(samples)

        return analysis

    def _analyze_object_samples(
        self,
        samples: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Analyze object samples to extract property information."""
        if not samples:
            return {}

        property_analysis: dict[str, dict[str, Any]] = {}
        all_keys: set[str] = set()
        required_keys: set[str] = set()

        # First pass: collect all keys
        for sample in samples:
            all_keys.update(sample.keys())

        # Check which keys appear in all samples
        required_keys = set(all_keys)
        for sample in samples:
            required_keys &= set(sample.keys())

        # Analyze each property
        for key in all_keys:
            values = [s[key] for s in samples if key in s]
            property_analysis[key] = {
                "presence_count": len(values),
                "total_samples": len(samples),
                "required": key in required_keys,
                "analysis": self._analyze_samples(values) if values else {},
            }

        return {
            "all_keys": list(all_keys),
            "required_keys": list(required_keys),
            "properties": property_analysis,
        }

    def _analyze_array_samples(
        self,
        samples: list[list[Any]]
    ) -> dict[str, Any]:
        """Analyze array samples to extract item information."""
        if not samples:
            return {}

        all_items = []
        for sample in samples:
            all_items.extend(sample)

        lengths = [len(s) for s in samples]

        return {
            "min_length": min(lengths) if lengths else 0,
            "max_length": max(lengths) if lengths else 0,
            "avg_length": sum(lengths) / len(lengths) if lengths else 0,
            "total_items": len(all_items),
            "item_analysis": self._analyze_samples(all_items) if all_items else {},
        }

    def _analyze_scalar_samples(self, samples: list[Any]) -> dict[str, Any]:
        """Analyze scalar samples for format and enum detection."""
        analysis: dict[str, Any] = {}

        if not samples:
            return analysis

        # Get types
        types = set(type(s).__name__ for s in samples)
        analysis["types"] = list(types)

        # String-specific analysis
        if all(isinstance(s, str) for s in samples):
            analysis["string_analysis"] = self._analyze_string_samples(samples)

        # Number-specific analysis
        if all(isinstance(s, (int, float)) for s in samples):
            numeric = [s for s in samples if isinstance(s, (int, float))]
            analysis["numeric_analysis"] = {
                "min": min(numeric),
                "max": max(numeric),
                "all_integers": all(isinstance(s, int) for s in samples),
            }

        # Enum detection
        if self.config.infer_enums:
            unique_values = set(str(s) for s in samples)
            if len(unique_values) <= self.config.enum_threshold:
                analysis["possible_enum"] = True
                analysis["enum_values"] = list(set(samples))

        return analysis

    def _analyze_string_samples(self, samples: list[str]) -> dict[str, Any]:
        """Analyze string samples for format detection."""
        analysis: dict[str, Any] = {}

        if not samples:
            return analysis

        # Length statistics
        lengths = [len(s) for s in samples]
        analysis["min_length"] = min(lengths)
        analysis["max_length"] = max(lengths)
        analysis["avg_length"] = sum(lengths) / len(lengths)

        # Format detection
        if self.config.infer_formats:
            format_counts: Counter[str] = Counter()

            for s in samples:
                fmt = self._detect_format(s)
                if fmt:
                    format_counts[fmt] += 1

            if format_counts:
                most_common_format, count = format_counts.most_common(1)[0]
                if count == len(samples):
                    analysis["detected_format"] = most_common_format
                elif count > len(samples) * 0.8:
                    analysis["likely_format"] = most_common_format
                    analysis["format_confidence"] = count / len(samples)

        # Pattern detection
        if all(samples):
            common_pattern = self._detect_common_pattern(samples)
            if common_pattern:
                analysis["possible_pattern"] = common_pattern

        return analysis

    def _detect_format(self, value: str) -> Optional[str]:
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

    def _detect_common_pattern(self, samples: list[str]) -> Optional[str]:
        """Detect common pattern in string samples."""
        if len(samples) < 2:
            return None

        # Check if all have same length
        lengths = set(len(s) for s in samples)
        if len(lengths) == 1:
            # Fixed length - try to detect pattern
            length = list(lengths)[0]

            # Check character positions
            pattern_chars = []
            for i in range(length):
                chars_at_pos = set(s[i] for s in samples)

                if len(chars_at_pos) == 1:
                    # Same character at this position
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

            # Verify pattern matches all samples
            regex = re.compile(pattern)
            if all(regex.match(s) for s in samples):
                return pattern

        return None

    def _generate_schema(self, analysis: dict[str, Any]) -> dict[str, Any]:
        """Generate schema from analysis."""
        if not analysis.get("types"):
            return {}

        # Determine primary type
        type_counts = analysis["types"]
        primary_type = type_counts.most_common(1)[0][0]

        # Map Python type names to JSON Schema types
        type_mapping = {
            "dict": "object",
            "list": "array",
            "str": "string",
            "int": "integer",
            "float": "number",
            "bool": "boolean",
            "NoneType": "null",
        }

        json_type = type_mapping.get(primary_type, "string")

        schema: dict[str, Any] = {"type": json_type}

        # Generate type-specific schema
        if json_type == "object" and "properties" in analysis:
            schema.update(self._generate_object_schema(analysis["properties"]))
        elif json_type == "array" and "items" in analysis:
            schema.update(self._generate_array_schema(analysis["items"]))
        elif "value_analysis" in analysis:
            schema.update(self._generate_scalar_schema(analysis["value_analysis"], json_type))

        return schema

    def _generate_object_schema(self, prop_analysis: dict[str, Any]) -> dict[str, Any]:
        """Generate object schema from property analysis."""
        schema: dict[str, Any] = {}
        properties: dict[str, Any] = {}

        for key, prop_info in prop_analysis.get("properties", {}).items():
            prop_schema = self._generate_schema(prop_info.get("analysis", {}))

            # Handle optional properties
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

    def _generate_array_schema(self, items_analysis: dict[str, Any]) -> dict[str, Any]:
        """Generate array schema from items analysis."""
        schema: dict[str, Any] = {}

        if "item_analysis" in items_analysis:
            items_schema = self._generate_schema(items_analysis["item_analysis"])
            if items_schema:
                schema["items"] = items_schema

        if items_analysis.get("min_length", 0) > 0:
            schema["minItems"] = items_analysis["min_length"]

        return schema

    def _generate_scalar_schema(
        self,
        value_analysis: dict[str, Any],
        json_type: str
    ) -> dict[str, Any]:
        """Generate scalar schema from value analysis."""
        schema: dict[str, Any] = {}

        # String format
        if json_type == "string":
            string_analysis = value_analysis.get("string_analysis", {})
            if "detected_format" in string_analysis:
                schema["format"] = string_analysis["detected_format"]
            if "possible_pattern" in string_analysis:
                schema["pattern"] = string_analysis["possible_pattern"]

        # Numeric constraints
        if json_type in ["integer", "number"]:
            numeric = value_analysis.get("numeric_analysis", {})
            if "min" in numeric:
                schema["minimum"] = numeric["min"]
            if "max" in numeric:
                schema["maximum"] = numeric["max"]

        # Enum
        if value_analysis.get("possible_enum") and self.config.infer_enums:
            schema["enum"] = value_analysis.get("enum_values", [])

        return schema

    def _calculate_confidence(
        self,
        analysis: dict[str, Any],
        sample_count: int
    ) -> float:
        """Calculate confidence score for inference."""
        if sample_count == 0:
            return 0.0

        confidence = 1.0

        # Reduce confidence for few samples
        if sample_count < 3:
            confidence *= 0.7
        elif sample_count < 10:
            confidence *= 0.9

        # Reduce confidence for mixed types
        if analysis.get("warnings"):
            confidence *= 0.8

        # Reduce confidence for sparse data
        if "properties" in analysis:
            prop_info = analysis["properties"]
            if prop_info.get("properties"):
                coverage_scores = []
                for prop in prop_info["properties"].values():
                    coverage = prop.get("presence_count", 0) / prop.get("total_samples", 1)
                    coverage_scores.append(coverage)
                if coverage_scores:
                    avg_coverage = sum(coverage_scores) / len(coverage_scores)
                    confidence *= avg_coverage

        return min(1.0, max(0.0, confidence))

    def generate_report(
        self,
        result: JSONSchemaInferenceResult,
        format: str = "text"
    ) -> str:
        """Generate an inference report."""
        if format == "json":
            return json.dumps(result.model_dump(), indent=2, default=str)
        elif format == "markdown":
            return self._generate_markdown_report(result)
        else:
            return self._generate_text_report(result)

    def _generate_text_report(self, result: JSONSchemaInferenceResult) -> str:
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

    def _generate_markdown_report(self, result: JSONSchemaInferenceResult) -> str:
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
