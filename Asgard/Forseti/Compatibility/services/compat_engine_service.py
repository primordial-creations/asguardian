"""
Compat Engine Service - orchestrator of the unified compatibility engine:
parse -> delta (format adapter) -> classify -> score -> report (plan 01).
"""

import json
import time
from pathlib import Path
from typing import Any, Optional

from Asgard.Forseti.Compatibility.models._compat_base_models import (
    CompatMode,
    CompatStatus,
    Direction,
)
from Asgard.Forseti.Compatibility.models.compat_models import (
    CompatReport,
    TelemetrySource,
    UnifiedChange,
    UsageStats,
)
from Asgard.Forseti.Compatibility.services._avro_adapter import diff_avro
from Asgard.Forseti.Compatibility.services._classification_helpers import (
    COMPAT_RULE_TABLE,
    make_change,
)
from Asgard.Forseti.Compatibility.services._openapi_adapter import diff_openapi
from Asgard.Forseti.Compatibility.services._protobuf_adapter import diff_protobuf
from Asgard.Forseti.Compatibility.services._scoring_helpers import (
    apply_telemetry,
    compute_score,
    compute_status,
)
from Asgard.Forseti.Compatibility.services._transitive_helpers import check_transitive
from Asgard.Forseti.Compatibility.utilities.compat_utils import (
    detect_format,
    diff_schema_pair,
    load_document,
    make_ref_resolver,
)
from Asgard.Forseti.Reporting.models.finding_models import Coordinates, Finding, Remediation
from Asgard.Forseti.Rules.models._rule_base_models import RuleCategory, SchemaFormat, Severity


class JsonFileTelemetrySource:
    """Telemetry provider backed by a JSON usage report (phase 4).

    Expected shape: {"window_days": 45, "usage": {"<location>": <call_count>}}
    """

    def __init__(self, path: str | Path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self._window_days = int(data.get("window_days", 0))
        self._usage: dict[str, int] = {
            str(k): int(v) for k, v in (data.get("usage") or {}).items()
        }

    def get_usage(self, location: str) -> Optional[UsageStats]:
        """Longest-prefix lookup so nested locations inherit parent usage."""
        best: Optional[str] = None
        for key in self._usage:
            if location == key or location.startswith(key):
                if best is None or len(key) > len(best):
                    best = key
        if best is None:
            return None
        return UsageStats(
            location=best,
            call_count=self._usage[best],
            window_days=self._window_days,
        )


class CompatEngineService:
    """
    Unified compatibility engine over all Forseti schema formats.

    Usage:
        engine = CompatEngineService()
        report = engine.check("old.yaml", "new.yaml", mode=CompatMode.BACKWARD)
        print(report.score, report.status)
    """

    def __init__(self, telemetry: Optional[TelemetrySource] = None):
        self.telemetry = telemetry

    def check(
        self,
        old_path: str | Path,
        new_path: str | Path,
        *,
        format_hint: str = "auto",
        mode: CompatMode = CompatMode.BACKWARD,
    ) -> CompatReport:
        """Check compatibility between two schema files."""
        start = time.time()
        fmt = self._resolve_format(old_path, format_hint)
        if fmt is None:
            return self._error_report(
                old_path, new_path, mode,
                f"Could not detect schema format of '{old_path}' "
                "(use --format-hint)",
            )
        try:
            changes = self._diff(fmt, old_path, new_path, mode)
        except Exception as exc:  # parse failures become findings, not crashes
            return self._error_report(old_path, new_path, mode,
                                      f"Failed to diff specifications: {exc}",
                                      fmt=fmt)
        confidence = apply_telemetry(changes, self.telemetry)
        score, receipt = compute_score(changes)
        return CompatReport(
            mode=mode,
            status=compute_status(changes),
            format=fmt,
            source=str(old_path),
            target=str(new_path),
            score=score,
            score_receipt=receipt,
            changes=changes,
            structural_breaks=sum(1 for c in changes if c.is_breaking),
            semantic_hazards=sum(1 for c in changes if c.is_hazard),
            confidence=confidence,
            check_time_ms=(time.time() - start) * 1000,
        )

    def check_history(
        self,
        history: list[str | Path],
        *,
        format_hint: str = "auto",
        mode: CompatMode = CompatMode.BACKWARD_TRANSITIVE,
    ) -> CompatReport:
        """Check an ordered version history (oldest first) transitively."""

        def pairwise(old: str, new: str, base: CompatMode) -> CompatReport:
            return self.check(old, new, format_hint=format_hint, mode=base)

        return check_transitive([str(p) for p in history], mode, pairwise)

    def to_findings(self, report: CompatReport) -> list[Finding]:
        """Project a CompatReport onto the canonical Finding model."""
        findings: list[Finding] = []
        for change in report.changes:
            severity = Severity.ERROR if change.is_breaking else (
                Severity.WARNING if change.is_hazard else Severity.INFO
            )
            from Asgard.Forseti.Compatibility.services._rule_registration import (
                registry_rule_id,
            )
            findings.append(Finding(
                rule_id=registry_rule_id(change.rule_id),
                severity=severity,
                message=change.message,
                coordinates=Coordinates(file=report.target, json_path=change.location),
                rationale=(
                    f"{change.abstract_violation.value} "
                    f"({change.direction.value}, structural="
                    f"{change.impact.structural.value}, semantic="
                    f"{change.impact.semantic.value})"
                ),
                remediation=(
                    Remediation(description=change.mitigation)
                    if change.mitigation else None
                ),
                suppressed=change.waived,
                category=RuleCategory.COMPATIBILITY,
                format=report.format,
            ))
        return findings

    # ------------------------------------------------------------------

    def _resolve_format(self, path: str | Path,
                        format_hint: str) -> Optional[SchemaFormat]:
        hints = {
            "openapi": SchemaFormat.OPENAPI,
            "asyncapi": SchemaFormat.ASYNCAPI,
            "avro": SchemaFormat.AVRO,
            "proto": SchemaFormat.PROTOBUF,
            "protobuf": SchemaFormat.PROTOBUF,
            "graphql": SchemaFormat.GRAPHQL,
            "jsonschema": SchemaFormat.JSONSCHEMA,
        }
        if format_hint != "auto":
            return hints.get(format_hint)
        return detect_format(path)

    def _diff(self, fmt: SchemaFormat, old_path: str | Path,
              new_path: str | Path, mode: CompatMode) -> list[UnifiedChange]:
        base = mode.pairwise
        if fmt == SchemaFormat.OPENAPI:
            old_spec = load_document(old_path) or {}
            new_spec = load_document(new_path) or {}
            if base == CompatMode.FORWARD:
                return diff_openapi(new_spec, old_spec)
            changes = diff_openapi(old_spec, new_spec)
            if base == CompatMode.FULL:
                changes = changes + diff_openapi(new_spec, old_spec)
            return changes
        if fmt == SchemaFormat.ASYNCAPI:
            from Asgard.Forseti.AsyncAPI.services.asyncapi_diff_service import (
                AsyncAPIDiffService,
            )
            service = AsyncAPIDiffService()
            if base == CompatMode.FORWARD:
                return service.diff(new_path, old_path)
            changes = service.diff(old_path, new_path)
            if base == CompatMode.FULL:
                changes = changes + service.diff(new_path, old_path)
            return changes
        if fmt == SchemaFormat.AVRO:
            old_schema = load_document(old_path)
            new_schema = load_document(new_path)
            return diff_avro(old_schema, new_schema, base)
        if fmt == SchemaFormat.PROTOBUF:
            from Asgard.Forseti.Protobuf.services.protobuf_validator_service import (
                ProtobufValidatorService,
            )
            validator = ProtobufValidatorService()
            old_result = validator.validate_file(old_path)
            new_result = validator.validate_file(new_path)
            if not old_result.parsed_schema or not new_result.parsed_schema:
                raise ValueError("Failed to parse proto file")
            return diff_protobuf(old_result.parsed_schema, new_result.parsed_schema)
        if fmt == SchemaFormat.GRAPHQL:
            from Asgard.Forseti.GraphQL.services.schema_diff_service import (
                GraphQLSchemaDiffService,
            )
            return GraphQLSchemaDiffService().diff(old_path, new_path)
        if fmt == SchemaFormat.JSONSCHEMA:
            old_schema = load_document(old_path) or {}
            new_schema = load_document(new_path) or {}
            direction = (Direction.INPUT if base == CompatMode.FORWARD
                         else Direction.OUTPUT)
            return diff_schema_pair(
                "/", old_schema, new_schema, direction, SchemaFormat.JSONSCHEMA,
                old_resolver=make_ref_resolver(old_schema),
                new_resolver=make_ref_resolver(new_schema),
            )
        raise ValueError(f"Unsupported format: {fmt}")

    def _error_report(self, old_path: Any, new_path: Any, mode: CompatMode,
                      message: str,
                      fmt: SchemaFormat = SchemaFormat.OPENAPI) -> CompatReport:
        change = make_change(
            "COMPAT-PARSE-ERROR", fmt, Direction.INPUT, "/", message,
        )
        score, receipt = compute_score([change])
        return CompatReport(
            mode=mode,
            status=CompatStatus.FAILED,
            format=fmt,
            source=str(old_path),
            target=str(new_path),
            score=score,
            score_receipt=receipt,
            changes=[change],
            structural_breaks=1,
        )


# Ensure the compat rule table is registered on import of the engine.
def _register_compat_rules() -> None:
    from Asgard.Forseti.Compatibility.services import _rule_registration  # noqa: F401


_register_compat_rules()

__all__ = [
    "COMPAT_RULE_TABLE",
    "CompatEngineService",
    "JsonFileTelemetrySource",
]
