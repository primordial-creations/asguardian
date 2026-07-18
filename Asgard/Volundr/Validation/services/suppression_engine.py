"""
Suppression Engine — warning annihilation with machine-readable receipts.

Contract (DEEPTHINK_02 §4):
- A finding matched by a valid suppression is REMOVED entirely (zero
  warnings), and the rendered artifact carries a receipt.
- A suppression whose rule never fired -> WARN (stale suppression hygiene).
- An expired suppression -> hard ERROR.
- A suppression referencing an unknown rule ID -> hard ERROR.

Receipts:
- K8s manifests: ``volundr.asgard/suppress-<rule>: "true"`` and
  ``volundr.asgard/rationale`` annotations.
- Dockerfile/HCL: trailing ``# volundr:suppress=<rule> <reason>`` comment.
- Pipeline YAML: the same comment above/next to the offending key.
"""

from datetime import date
from fnmatch import fnmatchcase
from typing import Any, Dict, List, Optional, Tuple

from Asgard.Volundr.Validation.models.rule_registry import (
    RuleRegistry,
    default_registry,
)
from Asgard.Volundr.Validation.models.suppression_models import (
    Suppression,
    SuppressionSet,
)
from Asgard.Volundr.Validation.models.validation_models import (
    ValidationCategory,
    ValidationResult,
    ValidationSeverity,
)


class SuppressionOutcome:
    """Result of applying suppressions to a list of findings."""

    def __init__(
        self,
        results: List[ValidationResult],
        applied: List[Tuple[Suppression, ValidationResult]],
        hygiene: List[ValidationResult],
    ):
        #: Findings that survived (suppressed ones are annihilated).
        self.results = results
        #: (suppression, original finding) pairs that were annihilated.
        self.applied = applied
        #: Hygiene findings (stale/expired/unknown-rule suppressions).
        self.hygiene = hygiene

    @property
    def all_results(self) -> List[ValidationResult]:
        return self.results + self.hygiene


def _targets_of(result: ValidationResult) -> List[str]:
    """Candidate target names a suppression may match against."""
    targets = []
    for value in (
        result.context.get("target"),
        result.resource_name,
        result.context.get("container"),
        result.file_path,
    ):
        if value:
            targets.append(str(value))
    return targets or ["*"]


class SuppressionEngine:
    """Matches reified suppressions against findings and applies the contract."""

    def __init__(
        self,
        suppressions: Optional[SuppressionSet] = None,
        registry: Optional[RuleRegistry] = None,
        today: Optional[date] = None,
    ):
        self.suppressions = suppressions or SuppressionSet()
        self.registry = registry or default_registry()
        self.today = today

    def _matches(self, suppression: Suppression, result: ValidationResult) -> bool:
        if suppression.rule != result.rule_id:
            return False
        return any(
            fnmatchcase(target, suppression.target)
            for target in _targets_of(result)
        )

    def apply(self, results: List[ValidationResult]) -> SuppressionOutcome:
        """Apply the warning-annihilation contract to a set of findings."""
        hygiene: List[ValidationResult] = []
        valid: List[Suppression] = []

        for suppression in self.suppressions:
            if suppression.rule not in self.registry:
                hygiene.append(ValidationResult(
                    rule_id="VOL-SUPPRESS-UNKNOWN-RULE",
                    message=(
                        f"Suppression references unknown rule "
                        f"'{suppression.rule}' (target '{suppression.target}')"
                    ),
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.BEST_PRACTICE,
                ))
                continue
            if suppression.is_expired(self.today):
                hygiene.append(ValidationResult(
                    rule_id="VOL-SUPPRESS-EXPIRED",
                    message=(
                        f"Suppression of '{suppression.rule}' for "
                        f"'{suppression.target}' expired on "
                        f"{suppression.expires} — reason was: {suppression.reason}"
                    ),
                    severity=ValidationSeverity.ERROR,
                    category=ValidationCategory.SECURITY,
                ))
                continue
            valid.append(suppression)

        kept: List[ValidationResult] = []
        applied: List[Tuple[Suppression, ValidationResult]] = []
        fired: Dict[int, bool] = {i: False for i in range(len(valid))}

        for result in results:
            annihilated = False
            for i, suppression in enumerate(valid):
                if self._matches(suppression, result):
                    fired[i] = True
                    applied.append((suppression, result))
                    annihilated = True
                    break
            if not annihilated:
                kept.append(result)

        for i, suppression in enumerate(valid):
            if not fired[i]:
                hygiene.append(ValidationResult(
                    rule_id="VOL-SUPPRESS-STALE",
                    message=(
                        f"Stale suppression: rule '{suppression.rule}' did not "
                        f"fire for target '{suppression.target}' — remove it"
                    ),
                    severity=ValidationSeverity.WARNING,
                    category=ValidationCategory.BEST_PRACTICE,
                    suggestion="Delete the suppression; the violation no longer exists.",
                ))

        return SuppressionOutcome(kept, applied, hygiene)


# ---------------------------------------------------------------------------
# Receipt emission helpers
# ---------------------------------------------------------------------------

def k8s_receipt_annotations(suppressions: List[Suppression]) -> Dict[str, str]:
    """Build the K8s annotation receipts for a set of applied suppressions."""
    annotations: Dict[str, str] = {}
    rationales: List[str] = []
    seen = set()
    for suppression in suppressions:
        if suppression.rule in seen:
            continue
        seen.add(suppression.rule)
        annotations[suppression.receipt_annotation_key()] = "true"
        rationales.append(f"{suppression.rule}: {suppression.reason}")
    if rationales:
        annotations["volundr.asgard/rationale"] = "; ".join(rationales)
    return annotations


def annotate_k8s_manifest(
    manifest: Dict[str, Any], suppressions: List[Suppression]
) -> Dict[str, Any]:
    """Attach suppression receipt annotations to a manifest dict (in place)."""
    if not suppressions:
        return manifest
    metadata = manifest.setdefault("metadata", {})
    annotations = metadata.setdefault("annotations", {})
    annotations.update(k8s_receipt_annotations(suppressions))
    return manifest


def comment_receipt(suppression: Suppression) -> str:
    """Trailing-comment receipt for Dockerfile / HCL / pipeline YAML."""
    return suppression.receipt_comment()


def append_comment_receipts(text: str, suppressions: List[Suppression]) -> str:
    """Append comment receipts to a rendered text artifact."""
    if not suppressions:
        return text
    lines = [text.rstrip("\n")]
    for suppression in suppressions:
        lines.append(suppression.receipt_comment())
    return "\n".join(lines) + "\n"
