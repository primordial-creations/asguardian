"""
The Volundr Validation Engine — four-tier, decoupled, adversarial.

Tier 1  Lexical parse    YAML -> typed docs with source line mapping.
Tier 2  Schema binding   version-pinned structural validation with
                         version-skew WARN downgrade + <tainted> marking.
Tier 3  Normalization    version-specific shapes -> Internal Canonical Model.
Tier 4  Semantic policy  default-deny rule packs over the ICM.

Generators NEVER grade their own intent: they hand rendered artifacts to
this engine. Suppressions are applied last (warning annihilation with
receipts), and the report reflects only surviving findings.
"""

import hashlib
import time
import warnings
from typing import Any, Dict, List, Optional, Tuple

import yaml  # type: ignore[import-untyped]

from Asgard.Volundr.Validation.models.rule_registry import (
    RuleRegistry,
    default_registry,
)
from Asgard.Volundr.Validation.models.suppression_models import SuppressionSet
from Asgard.Volundr.Validation.models.validation_models import (
    FileValidationSummary,
    ValidationCategory,
    ValidationContext,
    ValidationReport,
    ValidationResult,
    ValidationSeverity,
)
from Asgard.Volundr.Validation.services.normalizers import (
    has_obsolete_version_key,
    looks_like_azure_pipeline,
    looks_like_github_workflow,
    looks_like_gitlab_ci,
    normalize_azure_pipeline,
    normalize_compose,
    normalize_github_workflow,
    normalize_gitlab_ci,
    normalize_manifest,
)
from Asgard.Volundr.Validation.services.schema_binder import SchemaBinder
from Asgard.Volundr.Validation.services.semantic_policies import PolicyEngine
from Asgard.Volundr.Validation.services.suppression_engine import (
    SuppressionEngine,
    SuppressionOutcome,
)


def parse_yaml_with_lines(
    content: str,
) -> Tuple[List[Any], List[Dict[str, int]]]:
    """Tier 1: parse multi-doc YAML preserving 1-based line numbers per path.

    Returns (docs, line_maps) where line_maps[i] maps a dot path
    (e.g. 'spec.template.spec.containers[0]') to its source line.
    """
    docs: List[Any] = list(yaml.safe_load_all(content))
    line_maps: List[Dict[str, int]] = []

    for node in yaml.compose_all(content):
        line_map: Dict[str, int] = {}
        if node is not None:
            _walk_node(node, "", line_map)
            line_map[""] = node.start_mark.line + 1
        line_maps.append(line_map)

    while len(line_maps) < len(docs):
        line_maps.append({})
    return docs, line_maps


def _walk_node(node: Any, path: str, line_map: Dict[str, int]) -> None:
    if isinstance(node, yaml.MappingNode):
        for key_node, value_node in node.value:
            key = getattr(key_node, "value", "?")
            child = f"{path}.{key}" if path else str(key)
            line_map[child] = key_node.start_mark.line + 1
            _walk_node(value_node, child, line_map)
    elif isinstance(node, yaml.SequenceNode):
        for i, item in enumerate(node.value):
            child = f"{path}[{i}]"
            line_map[child] = item.start_mark.line + 1
            _walk_node(item, child, line_map)


class ValidationEngine:
    """Four-tier validation engine with reified suppressions."""

    def __init__(
        self,
        context: Optional[ValidationContext] = None,
        suppressions: Optional[SuppressionSet] = None,
        registry: Optional[RuleRegistry] = None,
    ):
        self.context = context or ValidationContext()
        self.registry = registry or default_registry()
        self.suppressions = suppressions or SuppressionSet()
        self.schema_binder = SchemaBinder(self.context)
        self.policy_engine = PolicyEngine(self.registry)
        if self.context.ignore_rules:
            warnings.warn(
                "ValidationContext.ignore_rules is deprecated: use reified "
                "suppressions (rule, target, reason) instead.",
                DeprecationWarning,
                stacklevel=2,
            )

    # ------------------------------------------------------------------

    def _parse(
        self, content: str, source: str
    ) -> Tuple[List[Any], List[Dict[str, int]], List[ValidationResult]]:
        try:
            docs, line_maps = parse_yaml_with_lines(content)
        except yaml.YAMLError as e:
            return [], [], [ValidationResult(
                rule_id="yaml-syntax",
                message=f"Invalid YAML syntax: {e}",
                severity=ValidationSeverity.ERROR,
                category=ValidationCategory.SYNTAX,
                file_path=source,
            )]
        return docs, line_maps, []

    def validate_kubernetes(
        self, content: str, source: str = "manifest"
    ) -> ValidationReport:
        """Validate rendered K8s YAML through all four tiers."""
        start = time.time()
        docs, line_maps, results = self._parse(content, source)

        for doc, line_map in zip(docs, line_maps):
            if not isinstance(doc, dict):
                continue
            outcome = self.schema_binder.bind(doc, source)
            results.extend(outcome.results)
            workload = normalize_manifest(
                doc, source, tainted=outcome.tainted, line_map=line_map
            )
            if workload is not None:
                results.extend(self.policy_engine.check_workload(workload))

        return self._finish("kubernetes", [source], results, start)

    def validate_compose(
        self, content: str, source: str = "compose"
    ) -> ValidationReport:
        """Validate rendered Compose YAML."""
        start = time.time()
        docs, _line_maps, results = self._parse(content, source)

        for doc in docs:
            if not isinstance(doc, dict):
                continue
            if has_obsolete_version_key(doc):
                rule = self.registry.get("VOL-COMPOSE-0001")
                if rule is not None:
                    results.append(ValidationResult(
                        rule_id="VOL-COMPOSE-0001",
                        message="Top-level 'version:' key is obsolete under the Compose Specification",
                        severity=rule.severity.to_validation_severity(),
                        category=rule.category,
                        file_path=source,
                        suggestion=rule.remediation,
                        context={"target": source},
                    ))
            for service in normalize_compose(doc, source):
                results.extend(
                    self.policy_engine.check_compose_service(service, source)
                )

        return self._finish("compose", [source], results, start)

    def validate_pipeline(
        self, content: str, source: str = "pipeline"
    ) -> ValidationReport:
        """Validate rendered CI pipeline YAML.

        GitHub Actions is normalized with full fidelity (permissions,
        SHA-pin, injection, static-secret, provenance rules). GitLab CI and
        Azure DevOps are normalized onto the same canonical pipeline-job
        model so the platform-agnostic rules (timeout, injection,
        static-secret) apply identically; those platforms have no
        per-job token-permissions concept, so the permissions rule is
        deliberately not evaluated for them (see normalizer docstrings).
        """
        start = time.time()
        docs, _line_maps, results = self._parse(content, source)

        for doc in docs:
            if not isinstance(doc, dict):
                continue
            if looks_like_github_workflow(doc):
                jobs = normalize_github_workflow(doc, source)
            elif looks_like_gitlab_ci(doc):
                jobs = normalize_gitlab_ci(doc, source)
            elif looks_like_azure_pipeline(doc):
                jobs = normalize_azure_pipeline(doc, source)
            else:
                continue
            for job in jobs:
                results.extend(self.policy_engine.check_pipeline_job(job, source))
            results.extend(
                self.policy_engine.check_pipeline_workflow(jobs, source)
            )

        return self._finish("pipeline", [source], results, start)

    # ------------------------------------------------------------------

    def apply_suppressions(
        self, results: List[ValidationResult]
    ) -> SuppressionOutcome:
        engine = SuppressionEngine(self.suppressions, self.registry)
        return engine.apply(results)

    def _finish(
        self,
        artifact_type: str,
        files: List[str],
        results: List[ValidationResult],
        start: float,
    ) -> ValidationReport:
        # Legacy deprecated ignore_rules (kept one minor version).
        if self.context.ignore_rules:
            ignored = set(self.context.ignore_rules)
            results = [r for r in results if r.rule_id not in ignored]

        outcome = self.apply_suppressions(results)
        final = outcome.all_results

        duration_ms = int((time.time() - start) * 1000)
        errors = sum(1 for r in final if r.severity == ValidationSeverity.ERROR)
        warns = sum(1 for r in final if r.severity == ValidationSeverity.WARNING)
        infos = sum(1 for r in final if r.severity == ValidationSeverity.INFO)
        score = max(0.0, 100.0 - errors * 10 - warns * 3 - infos * 1)

        summaries = []
        for fp in files:
            file_results = [r for r in final if (r.file_path or files[0]) == fp]
            file_errors = sum(
                1 for r in file_results if r.severity == ValidationSeverity.ERROR
            )
            summaries.append(FileValidationSummary(
                file_path=fp,
                error_count=file_errors,
                warning_count=sum(
                    1 for r in file_results
                    if r.severity == ValidationSeverity.WARNING
                ),
                info_count=sum(
                    1 for r in file_results
                    if r.severity == ValidationSeverity.INFO
                ),
                passed=file_errors == 0,
            ))

        report_id = hashlib.sha256(
            (artifact_type + str(final)).encode()
        ).hexdigest()[:16]
        return ValidationReport(
            id=f"volundr-{artifact_type}-{report_id}",
            title=f"Volundr {artifact_type.title()} Validation",
            validator="ValidationEngine",
            results=final,
            file_summaries=summaries,
            total_files=len(files),
            total_errors=errors,
            total_warnings=warns,
            total_info=infos,
            passed=errors == 0,
            score=score,
            duration_ms=duration_ms,
            context=self.context,
        )
