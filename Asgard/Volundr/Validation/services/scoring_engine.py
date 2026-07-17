"""
Composite Scoring Engine (plan 07 — DEEPTHINK_05 four-dimension model,
DEEPTHINK_01 anti-gaming defenses, RESEARCH_08 Polaris/Security-Hub prior art).

Scores are computed exclusively from Validation-engine findings on the
RENDERED artifact — never from generator config (the "Collusion Problem",
DEEPTHINK_05 §1A). Properties enforced by construction:

- Subtractive severity penalties per logical resource (CRITICAL -20,
  HIGH -10, MEDIUM -5, LOW -2, INFO 0; floor 0, base 100) — adding a
  finding can never raise any score.
- Security veto: any un-suppressed CRITICAL security finding caps the
  composite at 50; any HIGH security finding caps it at 70.
- Dilution defense: clean (zero-finding) resources carry near-zero
  weight in the artifact mean, so padding with trivially-secure
  resources does not raise the score.
- Suppressed findings score as passed but stay visible as receipts.
- Environment profiles change WEIGHTS only, never rule outcomes.
"""

from typing import Any, Dict, Iterable, List, Optional, Tuple

from Asgard.Volundr.Validation.models.rule_registry import (
    RuleRegistry,
    RuleSeverity,
    default_registry,
)
from Asgard.Volundr.Validation.models.score_models import (
    DimensionScore,
    RemediationHint,
    ResourceScore,
    ScoreDimension,
    ScoreReport,
    SuppressedReceipt,
    letter_grade,
)
from Asgard.Volundr.Validation.models.validation_models import (
    ValidationCategory,
    ValidationResult,
)
from Asgard.Volundr.Validation.services.scoring_profiles import profile_weights

#: Subtractive per-finding penalties (DEEPTHINK_05 §1B).
SEVERITY_PENALTY: Dict[RuleSeverity, float] = {
    RuleSeverity.CRITICAL: 20.0,
    RuleSeverity.HIGH: 10.0,
    RuleSeverity.MEDIUM: 5.0,
    RuleSeverity.LOW: 2.0,
    RuleSeverity.INFO: 0.0,
}

#: Category -> dimension mapping.
CATEGORY_DIMENSION: Dict[ValidationCategory, ScoreDimension] = {
    ValidationCategory.SECURITY: ScoreDimension.SECURITY,
    ValidationCategory.RELIABILITY: ScoreDimension.OPERABILITY,
    ValidationCategory.PERFORMANCE: ScoreDimension.OPERABILITY,
    ValidationCategory.SCHEMA: ScoreDimension.COMPLETENESS,
    ValidationCategory.SYNTAX: ScoreDimension.COMPLETENESS,
    ValidationCategory.BEST_PRACTICE: ScoreDimension.MAINTAINABILITY,
    ValidationCategory.MAINTAINABILITY: ScoreDimension.MAINTAINABILITY,
}

#: Rules that are completeness gaps regardless of their category
#: (the "nutrition label" — DEEPTHINK_05 §2 Phase 1).
COMPLETENESS_RULES = frozenset({
    "VOL-K8S-0013", "VOL-K8S-0014", "VOL-K8S-0015",
    "VOL-DOCKER-DIGEST",
})

#: Near-zero aggregate weight for zero-finding resources (dilution defense).
CLEAN_RESOURCE_WEIGHT = 0.05

#: Effort heuristics for remediation hints (SonarQube time-debt idiom).
_EFFORT_BY_SEVERITY: Dict[RuleSeverity, str] = {
    RuleSeverity.CRITICAL: "review + 1-3 edits",
    RuleSeverity.HIGH: "1-2 edits",
    RuleSeverity.MEDIUM: "1 edit",
    RuleSeverity.LOW: "1 edit",
    RuleSeverity.INFO: "optional",
}


class ScoringEngine:
    """Turns Validation findings into a composite ScoreReport."""

    def __init__(self, registry: Optional[RuleRegistry] = None):
        self.registry = registry or default_registry()

    # -- classification --------------------------------------------------

    def severity_of(self, result: ValidationResult) -> RuleSeverity:
        rule = self.registry.get(result.rule_id)
        if rule is not None:
            return rule.severity
        return RuleSeverity.from_validation_severity(result.severity)

    def dimension_of(self, result: ValidationResult) -> ScoreDimension:
        if result.rule_id in COMPLETENESS_RULES:
            return ScoreDimension.COMPLETENESS
        return CATEGORY_DIMENSION.get(
            result.category, ScoreDimension.MAINTAINABILITY
        )

    @staticmethod
    def resource_key(result: ValidationResult) -> str:
        for candidate in (
            result.resource_name,
            result.context.get("target") if result.context else None,
            result.file_path,
        ):
            if candidate:
                return str(candidate)
        return "artifact"

    # -- scoring ----------------------------------------------------------

    def score(
        self,
        findings: Iterable[ValidationResult],
        resources: Optional[Iterable[str]] = None,
        environment: str = "production",
        suppressed: Optional[Iterable[Tuple[Any, ValidationResult]]] = None,
    ) -> ScoreReport:
        """Compute the composite score.

        Args:
            findings: surviving (un-suppressed) findings from the
                Validation engine on the RENDERED artifact.
            resources: optional full universe of logical resource names
                (so clean resources appear, with near-zero weight).
            environment: weight-profile name.
            suppressed: (suppression, finding) pairs annihilated by the
                suppression engine — reported as receipts, never penalized.
        """
        findings = sorted(
            list(findings), key=lambda r: (r.rule_id, self.resource_key(r), r.message)
        )
        weights = profile_weights(environment)

        # Resource universe.
        universe: Dict[str, List[ValidationResult]] = {}
        for name in sorted(set(resources or [])):
            universe[str(name)] = []
        for result in findings:
            universe.setdefault(self.resource_key(result), []).append(result)
        if not universe:
            universe["artifact"] = []

        # Per-resource defect density (subtractive, floored at 0).
        resource_scores: List[ResourceScore] = []
        weighted_sum = 0.0
        weight_total = 0.0
        for name in sorted(universe):
            resource_findings = universe[name]
            penalty = sum(
                SEVERITY_PENALTY[self.severity_of(r)] for r in resource_findings
            )
            r_score = max(0.0, 100.0 - penalty)
            r_weight = 1.0 if resource_findings else CLEAN_RESOURCE_WEIGHT
            resource_scores.append(ResourceScore(
                resource=name, score=r_score,
                finding_count=len(resource_findings),
                aggregate_weight=r_weight,
            ))
            weighted_sum += r_weight * r_score
            weight_total += r_weight
        density = weighted_sum / weight_total if weight_total else 100.0

        # Dimension sub-scores: pure subtractive totals. Deliberately NOT
        # normalized by resource count — normalization would let a finding
        # on a previously-clean resource RAISE a dimension score (breaking
        # monotonicity) and would let resource padding dilute penalties
        # (DEEPTHINK_01 §1B). Size normalization lives in the per-resource
        # density table instead.
        dim_penalties: Dict[ScoreDimension, float] = {d: 0.0 for d in ScoreDimension}
        dim_counts: Dict[ScoreDimension, int] = {d: 0 for d in ScoreDimension}
        for result in findings:
            dim = self.dimension_of(result)
            dim_penalties[dim] += SEVERITY_PENALTY[self.severity_of(result)]
            dim_counts[dim] += 1
        dimensions: List[DimensionScore] = []
        composite = 0.0
        weight_sum = sum(weights.values()) or 1.0
        for dim in ScoreDimension:
            d_score = max(0.0, 100.0 - dim_penalties[dim])
            dimensions.append(DimensionScore(
                dimension=dim,
                score=round(d_score, 2),
                grade=letter_grade(d_score),
                weight=weights.get(dim, 0.0) / weight_sum,
                finding_count=dim_counts[dim],
            ))
            composite += (weights.get(dim, 0.0) / weight_sum) * d_score

        # Security veto (DEEPTHINK_05 §3): severity of the worst
        # un-suppressed SECURITY finding caps the composite.
        veto_applied: Optional[str] = None
        security_sevs = {
            self.severity_of(r) for r in findings
            if self.dimension_of(r) == ScoreDimension.SECURITY
        }
        if RuleSeverity.CRITICAL in security_sevs:
            if composite > 50.0:
                composite = 50.0
            veto_applied = "critical"
        elif RuleSeverity.HIGH in security_sevs:
            if composite > 70.0:
                composite = 70.0
            veto_applied = "high"

        # Remediation hints for the worst findings.
        ranked = sorted(
            findings,
            key=lambda r: (
                -SEVERITY_PENALTY[self.severity_of(r)], r.rule_id, r.message
            ),
        )
        remediation: List[RemediationHint] = []
        seen_rules = set()
        for result in ranked:
            if result.rule_id in seen_rules:
                continue
            seen_rules.add(result.rule_id)
            severity = self.severity_of(result)
            rule = self.registry.get(result.rule_id)
            remediation.append(RemediationHint(
                rule_id=result.rule_id,
                message=result.message,
                remediation=(
                    result.suggestion
                    or (rule.remediation if rule is not None else "")
                ),
                severity=severity.value,
                effort=_EFFORT_BY_SEVERITY[severity],
            ))
            if len(remediation) >= 10:
                break

        receipts = [
            SuppressedReceipt(
                rule_id=getattr(s, "rule", str(s)),
                target=getattr(s, "target", "*"),
                reason=getattr(s, "reason", ""),
            )
            for s, _finding in (suppressed or [])
        ]
        receipts.sort(key=lambda r: (r.rule_id, r.target))

        return ScoreReport(
            composite=round(composite, 2),
            grade=letter_grade(composite),
            environment=environment,
            dimensions=dimensions,
            resource_scores=resource_scores,
            resource_density_score=round(density, 2),
            veto_applied=veto_applied,
            remediation=remediation,
            suppressed_count=len(receipts),
            suppressed_receipts=receipts,
            total_findings=len(findings),
        )


def score_report_from_validation(
    report: Any,
    resources: Optional[Iterable[str]] = None,
    environment: str = "production",
    suppressed: Optional[Iterable[Tuple[Any, ValidationResult]]] = None,
    registry: Optional[RuleRegistry] = None,
) -> ScoreReport:
    """Convenience wrapper: score a ValidationReport's findings."""
    engine = ScoringEngine(registry=registry)
    return engine.score(
        report.results, resources=resources,
        environment=environment, suppressed=suppressed,
    )
