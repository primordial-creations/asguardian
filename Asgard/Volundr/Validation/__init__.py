"""
Volundr Validation Module

Provides validation services for infrastructure configurations:
- Kubernetes manifest validation (kubeconform-style)
- Terraform configuration validation
- Dockerfile best practices validation (hadolint-style)
"""

from Asgard.Volundr.Validation.models.validation_models import (
    ValidationResult,
    ValidationReport,
    ValidationSeverity,
    ValidationRule,
    ValidationContext,
)
from Asgard.Volundr.Validation.models.rule_registry import (
    RegisteredRule,
    RuleRegistry,
    RuleSeverity,
    UnknownValueBehavior,
    default_registry,
)
from Asgard.Volundr.Validation.models.suppression_models import (
    Suppression,
    SuppressionSet,
)
from Asgard.Volundr.Validation.models.canonical_models import (
    COMPUTED,
    TAINTED,
    is_computed,
    is_tainted,
    is_unknown,
)
from Asgard.Volundr.Validation.services.kubernetes_validator import KubernetesValidator
from Asgard.Volundr.Validation.services.terraform_validator import TerraformValidator
from Asgard.Volundr.Validation.services.dockerfile_validator import DockerfileValidator
from Asgard.Volundr.Validation.services.suppression_engine import (
    SuppressionEngine,
    annotate_k8s_manifest,
    append_comment_receipts,
    k8s_receipt_annotations,
)
from Asgard.Volundr.Validation.services.validation_engine import ValidationEngine
from Asgard.Volundr.Validation.services.report_emitters import to_junit_xml, to_sarif
from Asgard.Volundr.Validation.models.score_models import (
    DimensionScore,
    PostureIndex,
    RemediationHint,
    ResourceScore,
    ScoreDimension,
    ScoreReport,
    SuppressedReceipt,
    letter_grade,
)
from Asgard.Volundr.Validation.services.scoring_engine import (
    ScoringEngine,
    score_report_from_validation,
)
from Asgard.Volundr.Validation.services.scoring_profiles import (
    ENVIRONMENT_PROFILES,
    profile_weights,
)
from Asgard.Volundr.Validation.services.posture_index import compute_posture_index

__all__ = [
    "ValidationResult",
    "ValidationReport",
    "ValidationSeverity",
    "ValidationRule",
    "ValidationContext",
    "KubernetesValidator",
    "TerraformValidator",
    "DockerfileValidator",
    "RegisteredRule",
    "RuleRegistry",
    "RuleSeverity",
    "UnknownValueBehavior",
    "default_registry",
    "Suppression",
    "SuppressionSet",
    "SuppressionEngine",
    "ValidationEngine",
    "COMPUTED",
    "TAINTED",
    "is_computed",
    "is_tainted",
    "is_unknown",
    "annotate_k8s_manifest",
    "append_comment_receipts",
    "k8s_receipt_annotations",
    "to_sarif",
    "to_junit_xml",
    "DimensionScore",
    "PostureIndex",
    "RemediationHint",
    "ResourceScore",
    "ScoreDimension",
    "ScoreReport",
    "SuppressedReceipt",
    "letter_grade",
    "ScoringEngine",
    "score_report_from_validation",
    "ENVIRONMENT_PROFILES",
    "profile_weights",
    "compute_posture_index",
]
