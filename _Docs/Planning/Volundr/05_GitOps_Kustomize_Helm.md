# Volundr Upgrade Plan — 05 GitOps, Kustomize & Helm (P1, one item P0-immediate)

**Scope:** `Asgard/Volundr/GitOps/`, `Asgard/Volundr/Kustomize/`, `Asgard/Volundr/Helm/`.
**Depends on:** 06 (suppressions/rules).
**Research basis:** RESEARCH_05 (App-of-Apps field constraints, pre-merge render-and-validate pipeline), RESEARCH_02 (drift/reconciliation: SSA, ignoreDifferences), RESEARCH_09 (Kustomize v5.x semantics), RESEARCH_07 (Helm chart engineering: schema, CPU limits, hooks, immutable fields).

---

## 1. GitOps (`GitOps/`)

### Why
RESEARCH_05's App-of-Apps section names four Application fields whose misuse is a direct security hole, and Volundr currently **defaults into two of them**:
- `ArgoSource.target_revision: str = Field(default="HEAD")` (`gitops_models.py:99`) — "widely considered a severe anti-pattern for production" (unreviewed-branch deployment vector);
- `ArgoApplication.project: str = Field(default="default")` (`:117`) — bypasses AppProject RBAC boundaries.
Also `ArgoSourceHelm.target_revision: "*"` (`:79`) is an unpinned chart range (RESEARCH_07 dependency-pinning: ranges are non-deterministic).
RESEARCH_02/05 additionally: mutating-webhook drift needs `ServerSideDiff=true` / `ignoreDifferences` support surfaced (model has `ignore_differences` — good), and pruning (`prune: True` default) is documented as catastrophic when paths are refactored (RESEARCH_09 pruning hazards) — needs guard rails.

### Target & changes
| Change | File |
|---|---|
| **P0-immediate:** remove insecure defaults — `target_revision` becomes required (or defaults to a sentinel that fails generation with "pin a tag/commit"; `HEAD` only accepted with suppression `VOL-GITOPS-HEAD`); `project` required-non-`default` (suppressible `VOL-GITOPS-DEFAULT-PROJECT`); Helm `target_revision` must be exact version (range → finding) | `GitOps/models/gitops_models.py`, `GitOps/services/argocd_generator*.py` |
| `repo_url` allowlist: optional `allowed_repo_patterns` in a new `GitOpsPolicy` model; violation → HIGH finding (RESEARCH_05 repoURL hijack) | models + validators |
| `destination.server` allowlist analogous | same |
| Emit `argocd.argoproj.io/compare-options: ServerSideDiff=true` annotation by default; first-class `ignore_differences` presets for HPA `/spec/replicas` and Istio injections (RESEARCH_02 §9) | `argocd_generator.py` |
| Prune guard: when `prune=True`, generated app carries `Prune=confirm`-style sync option comment + finding INFO documenting blast radius; Flux Kustomization with `prune: true` + non-empty `depends_on` unaffected | generators |
| AppProject generation: new `ArgoAppProject` model (source repos, destinations, cluster-resource whitelist) so users can actually satisfy the non-default-project rule | new model + `argocd_generator.py` |
| Flux: `FluxKustomization` health checks encouraged (finding when absent); `postBuild.substitute` keys cross-checked against placeholders in referenced path when available (`flux envsubst --strict` semantics, RESEARCH_05) — static best-effort | `flux_generator*.py` |
| Render-and-validate hook: optional `volundr gitops validate` that renders referenced kustomize/helm sources (when local) → kubeconform → policy rules → pluto, mirroring RESEARCH_05's four-phase pipeline; external tools via plan-06 bridge | `cli/handlers_gitops.py`, `Validation/services/external_tools.py` |

## 2. Kustomize (`Kustomize/`)

### Why
RESEARCH_09: v5.x deprecated/removed `vars` and legacy patch fields; `commonLabels` mutates immutable `spec.selector.matchLabels` on live workloads (API server rejects updates). Current code emits `commonLabels` in both base and overlay generators (`base_generator_helpers.py:180`, `overlay_generator_helpers.py:53`); patches already use unified `patches` (good).

### Target & changes
| Change | File |
|---|---|
| Replace `commonLabels` emission with v5 `labels: [{pairs: ..., includeSelectors: false}]`; selector labels set once at base creation and locked (RESEARCH_09 immutable-selector guidance) | `base_generator_helpers.py`, `overlay_generator_helpers.py` |
| `replacements` support (source/target fieldPath model) — never `vars`; targeting arrays by semantic key (`[name=app]`) not index | new model + `patch_generator*.py` |
| Components support (`kind: Component`, `components:` field) for cross-cutting mix-ins | new `component_generator.py`, models |
| Images transformer: digest field alongside tag (`digest: sha256:...`) for supply-chain pinning | models + generators |
| `openapi: {path: ...}` passthrough so CRD strategic-merge patches don't clobber arrays (RESEARCH_09 CRD merge-key dilemma); JSON6902 recommended for `x-kubernetes-preserve-unknown-fields` payloads (e.g. HelmRelease values) — encode as rule guidance | models + docs |
| `configMapGenerator/secretGenerator` with `generatorOptions` (hash suffix default on; `disableNameSuffixHash` documented trade-off; `immutable: true` option) | `base_generator*.py` |
| Rules: `VOL-KUST-COMMONLABELS` (HIGH — selector mutation risk), `VOL-KUST-VARS` (ERROR if user supplies), `VOL-KUST-REMOTE-BASE` (INFO perf, RESEARCH_09 performance section) | plan-06 registry |

## 3. Helm (`Helm/`)

### Why
RESEARCH_07: charts must default to restrictive securityContexts (runAsNonRoot, high UID 65532, drop ALL, `allowPrivilegeEscalation: false`), avoid default **CPU limits** in production profiles (CFS throttling latency), pin dependencies exactly, garbage-collect hooks, guard immutable fields, and ship `values.schema.json` with `additionalProperties: false` only on nested objects (never root — breaks `global:`/subchart toggles). Current `values_generator.py` sets CPU limits in all environment presets (200m/500m/1000m) and there is no schema generation, hook policy, or NOTES.txt hygiene enforcement.

### Target & changes
| Change | File |
|---|---|
| `values.schema.json` generation from the chart's values model: types, enums, k8s-name regexes; `additionalProperties: false` on nested config objects only (RESEARCH_07 schema table); note that `default` in schema is documentation-only | new `Helm/services/schema_generator.py` |
| Security defaults in generated values/templates: `runAsNonRoot: true`, `runAsUser/Group: 65532`, `capabilities.drop: [ALL]`, `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, seccomp RuntimeDefault | `values_generator.py`, `_chart_generator_templates.py` |
| CPU limits: production preset defines requests, leaves `limits.cpu` unset (memory limits kept); staging/dev keep CPU limits for profiling (RESEARCH_07 "CPU limits conundrum") | `values_generator.py:33-55` |
| Hook hygiene: any generated hook template carries `helm.sh/hook-delete-policy: before-hook-creation,hook-succeeded` (orphaned-Job accumulation) | `_chart_generator_extras*.py` |
| Immutable-field lockdown: selector labels derived once from chart name and excluded from user-overridable labels (matchLabels immutability, RESEARCH_07 table); document `--atomic --timeout` upgrade guidance in NOTES.txt | templates |
| NOTES.txt: never render secrets; emit `kubectl get secret ... | base64 --decode` retrieval commands instead (RESEARCH_07 narrative-interface section) | `_chart_generator_templates.py` |
| Dependencies: exact version pinning in `Chart.yaml` `dependencies:`; alias support | `chart_generator.py`, models |
| CRD handling: `crds/` directory emission with README warning that Helm never upgrades CRDs (RESEARCH_07 CRD lifecycle) | `chart_generator.py` |
| Render-and-validate: `helm template | plan-06 engine` (+ helm lint --strict, ct lint via external bridge) | CLI handler |

## 4. Phased Steps

1. **Day one (P0):** GitOps insecure defaults (`HEAD`, `default` project, `*` chart revision) — small diffs, outsized risk (per 00_Overview rationale).
2. Kustomize v5 semantics (labels/includeSelectors, replacements, digest images).
3. Helm security defaults + CPU-limit change + schema generation.
4. AppProject/GitOpsPolicy allowlists, SSA annotation, components, hooks/NOTES/CRDs, render-and-validate pipeline.

## 5. Testing Notes

- GitOps: constructing `ArgoApplication` without pinned revision fails; suppression path produces receipt annotation on the Application; golden App+AppProject pair; assert `ServerSideDiff=true` present.
- Kustomize: `kustomize build` L3_Contract gate on golden base+overlay+component trees (skip-if-unavailable); assert no `commonLabels`/`vars` keys in any output; overlay applied to a live-style fixture never alters `spec.selector`.
- Helm: `helm lint --strict` gate; `helm template | kubeconform -strict` gate; schema negative tests (wrong type/enum rejected, root-level extra `global:` key accepted); production values contain no `limits.cpu`; NOTES.txt fixture contains no secret values.
- Flux: kustomization with `${VAR}` placeholder and missing substitute key yields finding.

## 6. Doc Reconciliation

- None of these three subpackages is documented in `_Docs/Asgard/Volundr/` — create `GitOps-Module.md`, `Kustomize-Module.md`, `Helm-Module.md` covering models, CLI (`volundr gitops|kustomize|helm ...` already in `cli/_parser_commands_2.py` / `handlers_gitops.py`), safe-defaults rationale (cite pinned-revision and non-default-project requirements), and the render-and-validate pipeline.
- Update `Overview.md` submodule table to list all shipped subpackages (Helm, Kustomize, Compose, GitOps, Validation, Scaffold).
