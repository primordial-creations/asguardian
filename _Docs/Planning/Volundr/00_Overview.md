# Volundr Upgrade Plan — 00 Overview

**Status:** Planning | **Date:** 2026-07-16
**Scope:** `Asgard/Volundr/` (Kubernetes, Terraform, Docker, CICD, plus the undocumented Helm, Kustomize, Compose, GitOps, Validation, Scaffold subpackages)
**Research corpus:** `_Docs/Research/Volundr/Completed/` — DEEPTHINK_01..05 and RESEARCH_01..10, all substantive as of 2026-07-17. (An earlier draft of this overview noted RESEARCH_01/02/04/06/07/08 as empty placeholders; they have since been completed: 01 = IaC static-analysis tool comparison (Checkov/tfsec/KICS/Terrascan), 02 = infrastructure drift detection, 04 = container image vulnerability scanners (Trivy/Grype/Snyk/Scout, VEX/SBOM), 06 = SLSA framework and CI/CD supply-chain attacks, 07 = Helm chart engineering, 08 = unified validation-framework architecture (plan-JSON traversal, Polaris scoring, SARIF). RESEARCH_11..15 also exist in the same directory but cover observability/SRE/performance topics belonging to another module (Heimdall/Verdandi scope) and are deliberately out of scope for Volundr planning.)
**Intended-behavior docs:** `_Docs/Asgard/Volundr/{Overview,Kubernetes-Module,Terraform-Module,Docker-Module,CICD-Module,CLI-Reference}.md`

---

## Executive Summary

Volundr today is a competent *template emitter*: every subdomain (K8s, Terraform, Docker, CI/CD, Helm, Kustomize, GitOps, Compose) produces syntactically valid output with a handful of hardcoded good practices and a naive additive "best practice score." The research corpus describes something categorically different: an **opinionated infrastructure compiler** with

1. **Unforgiving secure-by-default generation** with scoped, justified, machine-readable suppressions instead of profile toggles (DEEPTHINK_02 "Intent-Driven Generation with Reified Suppressions");
2. **A decoupled, adversarial validation engine** — canonical internal model, versioned schema binding, default-deny semantic policies (DEEPTHINK_03's four-tier architecture; RESEARCH_05's kubeconform/conftest/pluto pipeline);
3. **A principled composite scoring system** — severity-weighted, security-veto-capped, per-logical-resource defect density, environment profiles, L3-norm aggregation for the posture roll-up (DEEPTHINK_01 GWPI, DEEPTHINK_05 four-dimension model);
4. **Zero-trust CI/CD generation** — `permissions: {}`, SHA pinning, OIDC-only, env-var interpolation immunity, build/deploy split (DEEPTHINK_04);
5. **Full CIS/NSA-CISA control coverage** for K8s manifests (RESEARCH_03's control matrix) and hadolint/CIS-Docker coverage for Dockerfiles/Compose (RESEARCH_10).

The gap is wide but tractable because Volundr's structure (Pydantic models + service generators + a separate `Validation/` package) already matches the target architecture's separation of concerns. The upgrade is mostly *deepening* each layer, not restructuring.

A second, cheaper class of gap is **documentation drift**: the intended docs describe model fields and CLI flags that do not exist (e.g. `SecurityProfile.RESTRICTED/BASELINE/PRIVILEGED` in docs vs `BASIC/ENHANCED/STRICT/ZERO_TRUST` in `Kubernetes/models/kubernetes_models.py`; `create_service`/`tolerations`/`affinity` documented but absent), and six shipped subpackages (Helm, Kustomize, Compose, GitOps, Validation, Scaffold) are entirely undocumented. Each plan file ends with the doc reconciliation items for its domain.

---

## Gap Analysis (Current vs Intended/Research Target)

| Area | Current state (file evidence) | Intended docs say | Research target | Gap severity |
|---|---|---|---|---|
| K8s security controls | runAsNonRoot, drop ALL caps, RO rootfs, seccomp RuntimeDefault at pod level (`Kubernetes/services/manifest_generator.py:106-153`). Missing: `automountServiceAccountToken: false`, `imagePullPolicy: Always`, digest pinning, container-level seccomp, AppArmor, fsGroup configurability, auto emptyDir for `/tmp` with RO rootfs, dedicated ServiceAccount | Security profiles + probes + NetPol + PDB | Full NSA/CISA + CIS 5.x static matrix (RESEARCH_03) | **High** |
| K8s conditional hardening | NetworkPolicy only for ENHANCED+ profiles; PDB only in production (`manifest_generator.py:67-71`) | NetPol/PDB as flags | Max-secure always; deviations via reified suppressions, not profiles (DEEPTHINK_02) | **High** |
| Suppression/exception model | None — profiles silently relax security | N/A | Scoped pragmas + mandated justification + output-annotation receipts, zero warnings when suppressed (DEEPTHINK_02 §4) | **High** |
| Scoring | Linear additive percentage in each `*_helpers.py` (`calculate_best_practice_score`) | Weight tables per module | Composite 4-dimension score, security veto ceiling, per-resource defect density, environment profiles, letter grades, remediation hints (DEEPTHINK_05); portfolio-level GWPI (DEEPTHINK_01) | **High** |
| Validation engine | Regex/dict-walk rules in `Validation/services/*` (good rule IDs: DL30xx for Docker, ad-hoc for K8s/TF) | Not documented at all | Four-tier: lexical AST → versioned schema binding → canonical model → default-deny policies; `<computed>`/`<tainted>` primitives; version-skew WARN downgrade (DEEPTHINK_03) | **High** |
| CI/CD security | No `permissions:` block, no SHA pinning, mutable `@v4` refs, no OIDC scaffolding, no default `timeout-minutes`, no injection-immunity check (`CICD/services/pipeline_generator_helpers.py`) | Trigger/stage/caching scoring only | Zero-Trust Orchestration: `permissions: {}` default, SHA-pinned actions, OIDC over static secrets, env-var interpolation, build/deploy split, SLSA provenance, egress hardening (DEEPTHINK_04) | **Critical** |
| GitOps defaults | `target_revision` defaults to `"HEAD"`, `project` defaults to `"default"` (`GitOps/models/gitops_models.py:99,117`, `GitOps/services/argocd_generator.py:61-62`) | Not documented | Both are explicitly named severe anti-patterns; enforce pinned revisions, non-default AppProject, repoURL allowlists (RESEARCH_05 App-of-Apps section) | **Critical** |
| Dockerfile generation | Multi-stage, USER, HEALTHCHECK, label support (`Docker/services/dockerfile_generator.py`). Missing: BuildKit `# syntax` directive, `--mount=type=secret`, digest pinning, `SHELL pipefail`, `useradd -l`, apt list cleanup, cache-ordering guarantees | Multi-stage + non-root + healthcheck | Full hadolint/CIS alignment incl. BuildKit secret mounts, digest pinning + Renovate pairing (RESEARCH_10 §3) | **High** |
| Compose generation | Two overlapping implementations (`Docker/services/compose_generator.py` and `Compose/`); emits obsolete `version:` key per docs; `depends_on` without `condition: service_healthy`; host-interface port bindings | `version: "3.8"` shown in docs | compose-spec (no version key), healthcheck-gated depends_on, loopback/internal-network isolation, named volumes (RESEARCH_10 §4-5) | **Medium** |
| Kustomize | Base/overlay/patch generators exist (`Kustomize/services/*`) | Not documented | v5.x semantics: `labels`+`includeSelectors` over `commonLabels`, `replacements` not `vars`, unified `patches`, components, openapi field for CRD merge keys (RESEARCH_09) | **Medium** |
| Helm/GitOps validation | No rendered-output validation | Not documented | Render → kubeconform (version-pinned schemas, CRD catalogs) → conftest/policy → pluto deprecation scan (RESEARCH_05 pipeline) | **Medium** |
| Terraform | Keyword-matched canned resource blocks (`Terraform/services/_module_builder_blocks.py`); S3 gets versioning+SSE but no public-access block; no checkov-class policies; no per-resource scoring | Rich VariableConfig/OutputConfig API (partially real) | Schema-aware scoring of evaluated state, essential-vs-accidental complexity, no verbosity farming (DEEPTHINK_05 §1); graph centrality for portfolio scoring (DEEPTHINK_01) | **Medium** |
| Docs accuracy | Six subpackages undocumented; documented model fields/enums don't match code; CLI docs show `--cpu-limit` etc. that don't exist (`cli/_parser_commands_1.py`) | — | — | **Medium** (cheap to fix, high confusion cost) |

---

## Plan Files & Priorities

| File | Domain | Priority | Depends on |
|---|---|---|---|
| `01_Kubernetes.md` | K8s manifest generator: NSA/CISA control matrix, suppression model, companion resources | **P0** | 06 (suppression schema), 07 (scoring) |
| `02_Terraform.md` | Module builder: security baselines, schema-aware scoring, structure | P2 | 07 |
| `03_Docker.md` | Dockerfile + Compose: BuildKit, digest pinning, compose-spec, dedup | **P1** | 06, 07 |
| `04_CICD.md` | Zero-trust pipeline generation: permissions, pinning, OIDC, split-trust | **P0** | 06 |
| `05_GitOps_Kustomize_Helm.md` | ArgoCD/Flux safe defaults, Kustomize v5.x, render-and-validate pipeline | **P1** | 06 |
| `06_Validation_Engine.md` | Cross-cutting: four-tier validation architecture, suppression schema, canonical model | **P0** (foundational) | — |
| `07_Scoring.md` | Cross-cutting: composite scoring, security veto, environment profiles, posture index | **P1** | 06 |

Recommended execution order: **06 → 07 → 01 & 04 (parallel) → 03 → 05 → 02**, with doc reconciliation continuous.

Rationale for P0 choices:
- 06 is foundational — the suppression schema and rule/severity model are consumed by every generator.
- 04 is the highest-blast-radius security gap (generated pipelines currently inherit GitHub's `write-all` default token permissions — DEEPTHINK_04 Domain A calls this out explicitly).
- 01 is the flagship module and the one the intended docs promise most about.
- The GitOps `HEAD`/`default`-project fix inside 05 is a one-line-severity item; do it immediately even though the rest of 05 is P1.

---

## Cross-Cutting Principles (apply to every plan)

1. **Generate maximally secure; never emit a profile-degraded artifact silently** (DEEPTHINK_02). `SecurityProfile` enums become *presets of suppressions*, not alternate templates.
2. **Suppressions are reified**: input requires `rule`, `target`, `reason`; output carries `volundr.asgard/suppress-<rule>` + `volundr.asgard/rationale` annotations (K8s), `# volundr:suppress` trailing comments (Dockerfile/HCL/pipeline YAML). Suppressed rules emit **zero warnings** (warning-annihilation contract, DEEPTHINK_02 §4C).
3. **Scoring is decoupled and adversarial** — generators never grade their own intent, only the rendered artifact, via the shared `Validation/` engine (DEEPTHINK_05 §1A "Collusion Problem").
4. **Security is a veto dimension**: any Critical finding caps the composite score at 50 regardless of other dimensions (DEEPTHINK_05 §3).
5. **Default-deny policy style**: policies assert the *presence of safety*, never the absence of danger, so unknown fields fail closed (DEEPTHINK_03 §4).
6. **No source-code changes under `Asgard/` are part of this planning pass** — these documents are the specification for a subsequent implementation pass.

## Testing Strategy (shared)

- Extend `Asgard_Test/tests_Volundr/` (currently `test_kubernetes.py`, `test_terraform.py`, `test_docker.py`, `test_cicd.py` + `L0_Mocked`, `L3_Contract`, `L8_Performance`, `L14_Industry` tiers).
- **L3_Contract**: every generated artifact must pass the corresponding external industry tool in CI when available (`kubeconform -strict`, `hadolint`, `checkov`, `actionlint`, `kustomize build`, `helm lint`) — this operationalizes DEEPTHINK_05's decoupled-engine requirement. Mark tool-dependent tests skip-if-unavailable.
- **Golden files**: snapshot the full rendered output per (workload × environment × suppression-set) matrix; diffs reviewed like code.
- **Adversarial tests**: attempt to game the score (dilution, verbosity farming, sea-of-lows) and assert the score does not improve — direct translations of DEEPTHINK_01 §1B/E and DEEPTHINK_05 §1B/D.
