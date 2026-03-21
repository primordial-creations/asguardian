"""
Schema Inference Service.

Infers JSON Schemas from sample data.
"""

import json
import yaml  # type: ignore[import-untyped]
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from Asgard.Forseti.JSONSchema.models.jsonschema_models import (
    JSONSchemaConfig,
    JSONSchemaInferenceResult,
)
from Asgard.Forseti.JSONSchema.services._schema_inference_helpers import (
    analyze_array_samples,
    analyze_object_samples,
    analyze_scalar_samples,
    generate_array_schema,
    generate_markdown_report,
    generate_object_schema,
    generate_scalar_schema,
    generate_text_report,
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

        analysis = self._analyze_samples(samples)

        schema = self._generate_schema(analysis)

        schema["$schema"] = self.config.schema_version
        if title:
            schema["title"] = title
        if description:
            schema["description"] = description

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

        first_type = type(samples[0])
        all_same_type = all(type(s) == first_type for s in samples)

        if not all_same_type:
            analysis["warnings"].append("Samples have mixed types")

        type_counts = Counter(type(s).__name__ for s in samples)
        analysis["types"] = type_counts
        analysis["statistics"]["type_distribution"] = dict(type_counts)

        if first_type is dict:
            analysis["properties"] = analyze_object_samples(
                [s for s in samples if isinstance(s, dict)],
                self._analyze_samples,
            )
        elif first_type is list:
            analysis["items"] = analyze_array_samples(
                [s for s in samples if isinstance(s, list)],
                self._analyze_samples,
            )
        else:
            analysis["value_analysis"] = analyze_scalar_samples(samples, self.config)

        return analysis

    def _generate_schema(self, analysis: dict[str, Any]) -> dict[str, Any]:
        """Generate schema from analysis."""
        if not analysis.get("types"):
            return {}

        type_counts = analysis["types"]
        primary_type = type_counts.most_common(1)[0][0]

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

        if json_type == "object" and "properties" in analysis:
            schema.update(generate_object_schema(analysis["properties"], self._generate_schema))
        elif json_type == "array" and "items" in analysis:
            schema.update(generate_array_schema(analysis["items"], self._generate_schema))
        elif "value_analysis" in analysis:
            schema.update(generate_scalar_schema(analysis["value_analysis"], json_type, self.config))

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

        if sample_count < 3:
            confidence *= 0.7
        elif sample_count < 10:
            confidence *= 0.9

        if analysis.get("warnings"):
            confidence *= 0.8

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
            return generate_markdown_report(result)
        else:
            return generate_text_report(result)
