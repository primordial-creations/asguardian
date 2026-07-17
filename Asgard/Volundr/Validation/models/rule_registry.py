"""
Rule Registry for the Volundr Validation Engine.

Every semantic check is a registered rule with a stable ID, a five-level
severity taxonomy (CRITICAL/HIGH/MEDIUM/LOW/INFO), remediation markdown,
framework mappings (CIS / NSA-CISA / hadolint / SLSA), and declared
behavior for ``<computed>`` and ``<tainted>`` values.

Rule ID namespaces:
    VOL-K8S-*      Kubernetes manifests
    VOL-TF-*       Terraform
    VOL-CICD-*     CI/CD pipeline YAML
    VOL-GITOPS-*   ArgoCD / Flux
    VOL-HELM-*     Helm charts
    VOL-KUST-*     Kustomize
    VOL-COMPOSE-*  Docker Compose
    DL3xxx/DL4xxx  Dockerfile (hadolint-compatible IDs)
"""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from Asgard.Volundr.Validation.models.validation_models import (
    ValidationCategory,
    ValidationSeverity,
)


class RuleSeverity(str, Enum):
    """Five-level severity taxonomy required by composite scoring."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

    def to_validation_severity(self) -> ValidationSeverity:
        """Map to the legacy four-level ValidationSeverity."""
        return _SEVERITY_TO_LEGACY[self]

    @classmethod
    def from_validation_severity(cls, severity: ValidationSeverity) -> "RuleSeverity":
        """Map a legacy four-level severity into the five-level taxonomy."""
        return _LEGACY_TO_SEVERITY[severity]


_SEVERITY_TO_LEGACY: Dict[RuleSeverity, ValidationSeverity] = {
    RuleSeverity.CRITICAL: ValidationSeverity.ERROR,
    RuleSeverity.HIGH: ValidationSeverity.ERROR,
    RuleSeverity.MEDIUM: ValidationSeverity.WARNING,
    RuleSeverity.LOW: ValidationSeverity.INFO,
    RuleSeverity.INFO: ValidationSeverity.HINT,
}

_LEGACY_TO_SEVERITY: Dict[ValidationSeverity, RuleSeverity] = {
    ValidationSeverity.ERROR: RuleSeverity.HIGH,
    ValidationSeverity.WARNING: RuleSeverity.MEDIUM,
    ValidationSeverity.INFO: RuleSeverity.LOW,
    ValidationSeverity.HINT: RuleSeverity.INFO,
}


class UnknownValueBehavior(str, Enum):
    """Declared rule behavior when a value is <computed> or <tainted>.

    Default-deny principle: a rule may *soften* to WARN on unknown data,
    but it never silently passes unless it explicitly declares SKIP.
    """

    SKIP = "skip"
    WARN = "warn"
    CONDITIONAL_ASSERT = "conditional-assert"


class RegisteredRule(BaseModel):
    """A validation rule with full metadata for SARIF emission."""

    id: str = Field(description="Stable rule identifier (e.g. VOL-K8S-0001)")
    name: str = Field(description="Short rule name")
    description: str = Field(description="What the rule asserts (presence of safety)")
    severity: RuleSeverity = Field(description="Five-level severity")
    category: ValidationCategory = Field(description="Rule category")
    documentation_url: Optional[str] = Field(default=None, description="Docs URL")
    remediation: str = Field(default="", description="Remediation guidance (markdown)")
    framework_mappings: Dict[str, str] = Field(
        default_factory=dict,
        description="Compliance mappings, e.g. {'cis': '5.2.6', 'nsa-cisa': '...'}",
    )
    on_computed: UnknownValueBehavior = Field(
        default=UnknownValueBehavior.WARN,
        description="Behavior when the checked value is <computed>",
    )
    on_tainted: UnknownValueBehavior = Field(
        default=UnknownValueBehavior.WARN,
        description="Behavior when the checked node is <tainted>",
    )
    enabled: bool = Field(default=True, description="Is rule enabled")


class RuleRegistry:
    """Registry of all known validation rules, keyed by stable ID."""

    def __init__(self) -> None:
        self._rules: Dict[str, RegisteredRule] = {}

    def register(self, rule: RegisteredRule) -> RegisteredRule:
        self._rules[rule.id] = rule
        return rule

    def get(self, rule_id: str) -> Optional[RegisteredRule]:
        return self._rules.get(rule_id)

    def __contains__(self, rule_id: str) -> bool:
        return rule_id in self._rules

    def all_rules(self) -> List[RegisteredRule]:
        return sorted(self._rules.values(), key=lambda r: r.id)

    def ids(self) -> List[str]:
        return sorted(self._rules.keys())


def _build_default_registry() -> RuleRegistry:
    registry = RuleRegistry()
    sec = ValidationCategory.SECURITY
    bp = ValidationCategory.BEST_PRACTICE
    rel = ValidationCategory.RELIABILITY
    schema = ValidationCategory.SCHEMA

    defaults = [
        # --- Kubernetes (presence-of-safety, default-deny) ---
        RegisteredRule(
            id="VOL-K8S-0001", name="run-as-non-root",
            description="Container securityContext must explicitly set runAsNonRoot: true.",
            severity=RuleSeverity.HIGH, category=sec,
            remediation="Set `securityContext.runAsNonRoot: true` on the container.",
            framework_mappings={"cis": "5.2.6", "nsa-cisa": "non-root containers"},
        ),
        RegisteredRule(
            id="VOL-K8S-0002", name="no-privilege-escalation",
            description="Container must explicitly set allowPrivilegeEscalation: false.",
            severity=RuleSeverity.HIGH, category=sec,
            remediation="Set `securityContext.allowPrivilegeEscalation: false`.",
            framework_mappings={"cis": "5.2.5"},
        ),
        RegisteredRule(
            id="VOL-K8S-0003", name="drop-all-capabilities",
            description="Container must drop ALL Linux capabilities.",
            severity=RuleSeverity.MEDIUM, category=sec,
            remediation="Set `securityContext.capabilities.drop: [ALL]`.",
            framework_mappings={"cis": "5.2.9"},
        ),
        RegisteredRule(
            id="VOL-K8S-0004", name="read-only-root-filesystem",
            description="Container must set readOnlyRootFilesystem: true.",
            severity=RuleSeverity.MEDIUM, category=sec,
            remediation="Set `securityContext.readOnlyRootFilesystem: true` and mount an emptyDir for writable paths.",
        ),
        RegisteredRule(
            id="VOL-K8S-0005", name="pinned-image",
            description="Container image must be pinned to a specific tag or digest (not :latest / untagged).",
            severity=RuleSeverity.MEDIUM, category=bp,
            remediation="Pin the image to an immutable tag or, preferably, a digest (`image@sha256:...`).",
        ),
        RegisteredRule(
            id="VOL-K8S-0006", name="resource-limits-and-requests",
            description="Container must declare both resources.limits and resources.requests.",
            severity=RuleSeverity.MEDIUM, category=rel,
            remediation="Add `resources.requests` and `resources.limits` for cpu and memory.",
        ),
        RegisteredRule(
            id="VOL-K8S-0007", name="seccomp-runtime-default",
            description="Pod or container must set seccompProfile.type: RuntimeDefault (or Localhost).",
            severity=RuleSeverity.MEDIUM, category=sec,
            remediation="Set `securityContext.seccompProfile.type: RuntimeDefault`.",
            framework_mappings={"nsa-cisa": "seccomp"},
        ),
        RegisteredRule(
            id="VOL-K8S-0008", name="no-automount-service-account-token",
            description="Pod must explicitly set automountServiceAccountToken: false unless the workload needs the API.",
            severity=RuleSeverity.MEDIUM, category=sec,
            remediation="Set `automountServiceAccountToken: false` on the pod spec.",
            framework_mappings={"cis": "5.1.6"},
        ),
        RegisteredRule(
            id="VOL-K8S-0009", name="not-privileged",
            description="Container must not run privileged; privileged must be absent or explicitly false.",
            severity=RuleSeverity.CRITICAL, category=sec,
            remediation="Remove `securityContext.privileged: true`.",
            framework_mappings={"cis": "5.2.1"},
        ),
        RegisteredRule(
            id="VOL-K8S-0010", name="no-host-namespaces",
            description="Pod must not share host network, PID, or IPC namespaces.",
            severity=RuleSeverity.CRITICAL, category=sec,
            remediation="Remove `hostNetwork`, `hostPID`, and `hostIPC` from the pod spec.",
            framework_mappings={"cis": "5.2.2-5.2.4"},
        ),
        RegisteredRule(
            id="VOL-K8S-0011", name="known-schema",
            description="Manifest fields must be present in the bound Kubernetes schema for the target version.",
            severity=RuleSeverity.HIGH, category=schema,
            remediation="Remove or correct unknown fields; check the apiVersion for the target cluster version.",
        ),
        RegisteredRule(
            id="VOL-K8S-0012", name="supported-api-version",
            description="apiVersion must be a supported (non-deprecated) group/version for the kind.",
            severity=RuleSeverity.HIGH, category=schema,
            remediation="Migrate to the current stable apiVersion (e.g. batch/v1 for CronJob).",
        ),
        RegisteredRule(
            id="VOL-K8S-0013", name="image-digest-pinning",
            description=(
                "Container image should be pinned to an immutable digest "
                "(image@sha256:...) — a mutable tag is a completeness gap the "
                "generator cannot resolve on its own."
            ),
            severity=RuleSeverity.MEDIUM, category=bp,
            remediation=(
                "Provide `image_digest` (sha256:...) so the image renders as "
                "`repo@sha256:...`, or suppress with a justified reason."
            ),
            framework_mappings={"nsa-cisa": "supply chain / image integrity"},
        ),
        RegisteredRule(
            id="VOL-K8S-0014", name="secret-data-completeness",
            description=(
                "Generated Secret has no stringData — the generator cannot know "
                "secret material and will not fabricate it."
            ),
            severity=RuleSeverity.LOW, category=bp,
            remediation=(
                "Populate the Secret out-of-band (ExternalSecrets, SealedSecrets, "
                "CI injection) or pass `secret_string_data` explicitly."
            ),
        ),
        RegisteredRule(
            id="VOL-K8S-0015", name="pdb-completeness",
            description=(
                "PodDisruptionBudget minAvailable strategy was defaulted — the "
                "generator cannot know the workload's real availability requirement."
            ),
            severity=RuleSeverity.INFO, category=rel,
            remediation="Set `pdb.min_available` or `pdb.max_unavailable` explicitly.",
        ),
        # --- Dockerfile (Volundr generation-time rules) ---
        RegisteredRule(
            id="VOL-DOCKER-DIGEST", name="base-image-digest-pinning",
            description=(
                "FROM should be pinned to an immutable digest "
                "(image:tag@sha256:...) — a mutable tag is a completeness gap. "
                "Pair digest pinning with Renovate so updates stay automated."
            ),
            severity=RuleSeverity.MEDIUM, category=bp,
            remediation=(
                "Set `base_image_digest` (sha256:...) on the build stage, and "
                "adopt the generated renovate.json so Renovate keeps the digest "
                "fresh; or suppress with a justified reason."
            ),
            framework_mappings={"hadolint": "DL3006/DL3007"},
        ),
        RegisteredRule(
            id="VOL-DOCKER-SECRET-ENV", name="no-plaintext-secret-env",
            description=(
                "ENV/ARG values that look like secrets bake credentials into "
                "image layers. Use BuildKit `--mount=type=secret` instead."
            ),
            severity=RuleSeverity.CRITICAL, category=sec,
            remediation=(
                "Move the secret to a BuildKit secret mount "
                "(`RUN --mount=type=secret,id=...`) and drop the ENV/ARG."
            ),
            framework_mappings={"cis-docker": "4.10"},
        ),
        RegisteredRule(
            id="VOL-DOCKER-COPY-CONTEXT", name="copy-whole-context",
            description=(
                "`COPY . .` copies the whole build context; without a "
                ".dockerignore this leaks VCS metadata and secrets and "
                "defeats layer caching."
            ),
            severity=RuleSeverity.LOW, category=bp,
            remediation="Ship the generated .dockerignore next to the Dockerfile.",
        ),
        RegisteredRule(
            id="VOL-DOCKER-UNPINNED-PKG", name="unpinned-package-install",
            description=(
                "Package installs without pinned versions are not "
                "reproducible (hadolint DL3008/DL3013/DL3016/DL3018 family)."
            ),
            severity=RuleSeverity.LOW, category=bp,
            remediation="Pin package versions (pkg=1.2.*, pkg==1.2.3, pkg@1.2.3).",
            framework_mappings={"hadolint": "DL3008"},
        ),
        # --- Compose ---
        RegisteredRule(
            id="VOL-COMPOSE-0001", name="no-obsolete-version-key",
            description="The top-level `version:` key is obsolete under the Compose Specification.",
            severity=RuleSeverity.LOW, category=bp,
            remediation="Delete the top-level `version:` key; the Compose Specification ignores it.",
        ),
        RegisteredRule(
            id="VOL-COMPOSE-0002", name="not-privileged",
            description="Compose service must not set privileged: true.",
            severity=RuleSeverity.CRITICAL, category=sec,
            remediation="Remove `privileged: true` from the service.",
        ),
        RegisteredRule(
            id="VOL-COMPOSE-0003", name="no-host-network",
            description="Compose service must not use network_mode: host.",
            severity=RuleSeverity.HIGH, category=sec,
            remediation="Use a named bridge network instead of `network_mode: host`.",
        ),
        RegisteredRule(
            id="VOL-COMPOSE-0004", name="pinned-image",
            description="Compose service image must be pinned (not :latest / untagged).",
            severity=RuleSeverity.MEDIUM, category=bp,
            remediation="Pin the image to an immutable tag or digest.",
        ),
        RegisteredRule(
            id="VOL-COMPOSE-0005", name="loopback-port-binding",
            description="Published ports should bind loopback (127.0.0.1) unless external exposure is intended.",
            severity=RuleSeverity.MEDIUM, category=sec,
            remediation="Bind ports as `127.0.0.1:HOST:CONTAINER` unless the service must be reachable externally.",
        ),
        RegisteredRule(
            id="VOL-COMPOSE-EXPOSED", name="datastore-host-port-exposed",
            description=(
                "A datastore service publishes a host port on all "
                "interfaces; datastores should be internal-network-only or "
                "loopback-bound (RESEARCH_10 §5.4)."
            ),
            severity=RuleSeverity.HIGH, category=sec,
            remediation=(
                "Remove the published port (use an internal network) or bind "
                "it as `127.0.0.1:HOST:CONTAINER`."
            ),
        ),
        RegisteredRule(
            id="VOL-COMPOSE-0006", name="prefer-named-volumes",
            description="Bind mounts are host-coupled; prefer named volumes for data.",
            severity=RuleSeverity.LOW, category=bp,
            remediation="Declare a named volume and mount it instead of a host path.",
        ),
        RegisteredRule(
            id="VOL-COMPOSE-0007", name="volume-permission-bootstrap",
            description=(
                "A non-root service mounting a fresh named volume usually "
                "needs a permission bootstrap (the volume is created "
                "root-owned)."
            ),
            severity=RuleSeverity.INFO, category=rel,
            remediation=(
                "chown the mount path in the image, or run a one-shot init "
                "service/entrypoint to fix ownership before first use."
            ),
        ),
        RegisteredRule(
            id="VOL-COMPOSE-0008", name="healthcheck-gated-dependency",
            description=(
                "depends_on without `condition: service_healthy` only waits "
                "for container start, not readiness (RESEARCH_10 §5.1)."
            ),
            severity=RuleSeverity.LOW, category=rel,
            remediation=(
                "Give the dependency a healthcheck and use the long-form "
                "`depends_on: {svc: {condition: service_healthy}}`."
            ),
        ),
        # --- CI/CD pipeline YAML (GitHub Actions first) ---
        RegisteredRule(
            id="VOL-CICD-0001", name="explicit-permissions",
            description="Workflow (or every job) must declare an explicit least-privilege permissions block.",
            severity=RuleSeverity.CRITICAL, category=sec,
            remediation="Add `permissions: {}` at workflow level and grant per-job scopes explicitly.",
            framework_mappings={"slsa": "provenance/least-privilege"},
        ),
        RegisteredRule(
            id="VOL-CICD-0002", name="sha-pinned-actions",
            description="Third-party actions must be pinned to a full commit SHA, not a mutable tag.",
            severity=RuleSeverity.HIGH, category=sec,
            remediation="Pin `uses:` references to a 40-char commit SHA with a trailing version comment.",
            framework_mappings={"slsa": "dependency pinning"},
        ),
        RegisteredRule(
            id="VOL-CICD-0003", name="job-timeout",
            description="Every job must declare timeout-minutes.",
            severity=RuleSeverity.LOW, category=rel,
            remediation="Add `timeout-minutes:` to each job.",
        ),
        RegisteredRule(
            id="VOL-CICD-0004", name="untrusted-interpolation",
            description=(
                "run: scripts must not inline-interpolate ${{ }} expressions "
                "referencing attacker-controllable contexts (script injection)."
            ),
            severity=RuleSeverity.CRITICAL, category=sec,
            remediation=(
                "Route the expression through an `env:` variable and reference "
                "it as \"$VAR\" in the script — never inline `${{ ... }}`."
            ),
            framework_mappings={"slsa": "build integrity"},
        ),
        RegisteredRule(
            id="VOL-CICD-0005", name="static-cloud-secret",
            description=(
                "Workflows must use OIDC token exchange, not long-lived static "
                "cloud credentials passed via secrets."
            ),
            severity=RuleSeverity.HIGH, category=sec,
            remediation=(
                "Replace static cloud keys with OIDC federation "
                "(e.g. aws-actions/configure-aws-credentials with role-to-assume "
                "and `permissions: id-token: write`)."
            ),
            framework_mappings={"slsa": "secrets hygiene"},
        ),
        RegisteredRule(
            id="VOL-CICD-0006", name="provenance-attestation",
            description=(
                "Release pipelines should attest build provenance "
                "(SLSA build track)."
            ),
            severity=RuleSeverity.INFO, category=bp,
            remediation=(
                "Add an actions/attest-build-provenance job with "
                "`permissions: {id-token: write, attestations: write}`."
            ),
            framework_mappings={"slsa": "provenance"},
        ),
        # --- GitOps ---
        RegisteredRule(
            id="VOL-GITOPS-0001", name="pinned-target-revision",
            description="ArgoCD Application targetRevision must be pinned (not HEAD).",
            severity=RuleSeverity.HIGH, category=sec,
            remediation="Set `spec.source.targetRevision` to a branch, tag, or commit SHA — never HEAD.",
        ),
        RegisteredRule(
            id="VOL-GITOPS-0002", name="non-default-project",
            description="ArgoCD Application must use a scoped AppProject, not the unrestricted 'default' project.",
            severity=RuleSeverity.HIGH, category=sec,
            remediation="Create a scoped AppProject with repo/destination allowlists and reference it in `spec.project`.",
        ),
    ]
    for rule in defaults:
        registry.register(rule)

    # Legacy rule IDs emitted by the existing per-format validators are
    # registered 1:1 so suppressions and SARIF emission cover them too.
    legacy = {
        # Kubernetes (legacy KubernetesValidator IDs)
        "missing-selector": (RuleSeverity.HIGH, schema, "Add spec.selector."),
        "no-containers": (RuleSeverity.HIGH, schema, "Define at least one container."),
        "missing-image": (RuleSeverity.HIGH, schema, "Set the container image."),
        "unpinned-image": (RuleSeverity.MEDIUM, bp, "Pin the image tag or digest."),
        "missing-resource-limits": (RuleSeverity.MEDIUM, rel, "Add resources.limits."),
        "missing-resource-requests": (RuleSeverity.MEDIUM, rel, "Add resources.requests."),
        "missing-security-context": (RuleSeverity.MEDIUM, sec, "Add a securityContext."),
        "not-running-as-non-root": (RuleSeverity.HIGH, sec, "Set runAsNonRoot: true."),
        "privileged-container": (RuleSeverity.CRITICAL, sec, "Remove privileged: true."),
        "privilege-escalation-allowed": (
            RuleSeverity.HIGH, sec, "Set allowPrivilegeEscalation: false."),
        "missing-liveness-probe": (RuleSeverity.MEDIUM, rel, "Add a livenessProbe."),
        "missing-readiness-probe": (RuleSeverity.MEDIUM, rel, "Add a readinessProbe."),
        "missing-labels": (RuleSeverity.LOW, bp, "Add metadata.labels."),
        "ingress-no-tls": (RuleSeverity.MEDIUM, sec, "Configure TLS on the Ingress."),
        "ingress-no-rules": (RuleSeverity.MEDIUM, schema, "Add Ingress rules."),
        "service-no-selector": (RuleSeverity.MEDIUM, bp, "Add a Service selector."),
        "service-no-ports": (RuleSeverity.MEDIUM, schema, "Add Service ports."),
        "unknown-api-version": (RuleSeverity.MEDIUM, schema, "Use a supported apiVersion."),
        # Terraform (legacy TerraformValidator IDs)
        "hardcoded-credential": (RuleSeverity.CRITICAL, sec, "Move secrets to variables/Vault."),
        "iam-wildcard-action": (RuleSeverity.HIGH, sec, "Scope IAM actions explicitly."),
        "iam-wildcard-resource": (RuleSeverity.HIGH, sec, "Scope IAM resources explicitly."),
        "sg-open-ingress": (RuleSeverity.HIGH, sec, "Restrict the ingress CIDR."),
        "sg-all-ports": (RuleSeverity.HIGH, sec, "Restrict the port range."),
        "s3-no-encryption": (RuleSeverity.HIGH, sec, "Enable server-side encryption."),
        "s3-no-versioning": (RuleSeverity.MEDIUM, rel, "Enable bucket versioning."),
        "module-no-version": (RuleSeverity.MEDIUM, bp, "Pin the module version."),
        "variable-no-description": (RuleSeverity.LOW, bp, "Describe the variable."),
        "variable-no-type": (RuleSeverity.LOW, bp, "Type the variable."),
        "variable-not-sensitive": (RuleSeverity.MEDIUM, sec, "Mark as sensitive = true."),
        "output-not-sensitive": (RuleSeverity.MEDIUM, sec, "Mark as sensitive = true."),
    }
    for rule_id, (severity, category, remediation) in legacy.items():
        registry.register(RegisteredRule(
            id=rule_id, name=rule_id,
            description=f"Legacy rule {rule_id}",
            severity=severity, category=category, remediation=remediation,
        ))

    # hadolint-compatible Dockerfile rule IDs (kept verbatim).
    hadolint_ids = {
        "DL3000": "Use absolute WORKDIR.",
        "DL3001": "Avoid irrelevant shell commands in RUN.",
        "DL3002": "Do not switch to root (USER root) last.",
        "DL3004": "Do not use sudo.",
        "DL3007": "Do not use :latest tag; pin the version.",
        "DL3008": "Pin versions in apt-get install.",
        "DL3009": "Delete apt lists after install.",
        "DL3011": "Use a valid UNIX port range.",
        "DL3014": "Use apt-get -y.",
        "DL3013": "Pin versions in pip install.",
        "DL3016": "Pin versions in npm install.",
        "DL3018": "Pin versions in apk add.",
        "DL3020": "Use COPY instead of ADD.",
        "DL3025": "Use JSON notation for CMD/ENTRYPOINT.",
        "DL3032": "yum clean all after install.",
        "DL3042": "Use pip --no-cache-dir.",
        "DL3045": "COPY to a relative destination needs WORKDIR.",
        "DL3046": "useradd without -l and high UID.",
        "DL3055": "Pin image digests.",
        "DL3059": "Consolidate consecutive RUN instructions.",
        "DL4001": "Do not use both wget and curl.",
        "DL4006": "Set SHELL -o pipefail before RUNs with pipes.",
        "DL4002": "Use HEALTHCHECK.",
        "DL0001": "Dockerfile parse issue.",
        "DL0002": "Dockerfile structure issue.",
    }
    for rule_id, remediation in hadolint_ids.items():
        registry.register(RegisteredRule(
            id=rule_id, name=rule_id,
            description=f"hadolint {rule_id}",
            severity=RuleSeverity.MEDIUM, category=bp, remediation=remediation,
            framework_mappings={"hadolint": rule_id},
        ))

    return registry


_DEFAULT_REGISTRY: Optional[RuleRegistry] = None


def default_registry() -> RuleRegistry:
    """Return the process-wide default rule registry (lazily built)."""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = _build_default_registry()
    return _DEFAULT_REGISTRY
