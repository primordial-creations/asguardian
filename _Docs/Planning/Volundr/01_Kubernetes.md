# Volundr Upgrade Plan — 01 Kubernetes Manifest Generator (P0)

**Scope:** `Asgard/Volundr/Kubernetes/` (models + services).
**Depends on:** 06 (suppression schema, rule registry), 07 (scoring).
**Research basis:** RESEARCH_03 (NSA/CISA + CIS static control matrix with exact YAML paths), DEEPTHINK_02 (max-secure defaults + reified suppressions), RESEARCH_05 (rendered-output validation), DEEPTHINK_05 (nutrition-label generation UX).

---

## 1. Why (Research Rationale)

RESEARCH_03 defines the full statically-enforceable control matrix a "commercial-grade manifest generator" must emit and concludes the output must "pass a local kubesec/datree scan with a perfect score without human intervention." Current generator (`services/manifest_generator.py`) emits a good core (runAsNonRoot, runAsUser/Group, drop ALL, RO rootfs, allowPrivilegeEscalation false, pod-level seccomp RuntimeDefault, fsGroup 2000) but is missing, versus the matrix:

| Missing control | RESEARCH_03 reference | Required value |
|---|---|---|
| `automountServiceAccountToken: false` + dedicated ServiceAccount per workload | CIS 5.1.5/5.1.6 | pod-level `false`; generate `ServiceAccount` object |
| `imagePullPolicy: Always` | NSA/CISA supply chain (cache poisoning) | container-level |
| Digest pinning `image@sha256:` | NSA/CISA supply chain | validate/warn on mutable tags; accept digest input |
| Container-level seccomp + AppArmor field (`appArmorProfile.type`, K8s ≥ 1.30) or annotation fallback | CIS 5.6.2 / NSA | `RuntimeDefault`; emit correct shape per `target_k8s_version` |
| Auto `emptyDir` for `/tmp` (+ configurable writable paths) when RO rootfs | RESEARCH_03 "Immutable Root Filesystems" edge case | injected volume + mount |
| Default-deny NetworkPolicy **always**, with DNS egress carve-out (kube-dns TCP/UDP 53) | CIS 5.3.2 | today NetPol only for ENHANCED+ profiles (`manifest_generator.py:67`), and the egress rule exists but ingress uses a namespaceSelector rather than starting from default-deny |
| PDB regardless of environment (weighting handled by scoring profile) | operability | today only production && replicas>1 (`:70`) |
| `fsGroupChangePolicy: OnRootMismatch` option | RESEARCH_03 fsGroup edge case | model field |

Second structural gap (DEEPTHINK_02): `SecurityProfile.BASIC/ENHANCED/STRICT/ZERO_TRUST` silently *adds* hardening as profile rises — i.e., BASIC silently relaxes. Research mandates the inverse: always generate maximum security; deviations only via justified suppressions that leave receipts.

Also: Jobs/CronJobs (`_generate_job`) get a **reduced** securityContext (no capabilities drop, no seccomp, no pod-level context) — the nested-path problem RESEARCH_03 calls out (`spec.jobTemplate.spec.template.spec`); controls must be uniform across all five workload paths.

## 2. Target State

- **One hardened template.** Every workload kind gets the complete RESEARCH_03 matrix at the correct nesting depth. No profile-conditional hardening.
- `SecurityProfile` enum retained for compat but redefined as a **suppression preset**: e.g. `BASIC` = preset suppressing `VOL-K8S` rules {NetPol-egress-strict, digest-pinning} *with generated reasons marked `preset:` in receipts*, so relaxation is visible in output. `ZERO_TRUST` = empty preset.
- **Companion resources always generated:** dedicated ServiceAccount (automount false), default-deny NetworkPolicy + explicit allows derived from `ports` and declared egress needs, PDB (when replicas > 1), headless Service for StatefulSets (currently named but never emitted — bug: `serviceName: {name}-headless` references a non-existent Service, `manifest_generator.py:188`).
- **Suppressible ergonomics for legitimate exceptions** (DEEPTHINK_02 §1 taxonomy): DaemonSet log collector (hostPath + privileges), database writable mount, legacy root image — all expressible as `suppressions:` entries in `ManifestConfig`, producing annotation receipts.
- **Rendered-output validation & scoring** via plan 06/07; generator itself performs no scoring.
- **Nutrition-label completeness:** generator marks context it cannot know (image digest, real egress destinations, PDB minAvailable strategy) as completeness findings with remediation hints instead of guessing silently (DEEPTHINK_05 §2 Phase 1).

## 3. Concrete File/Module Changes

| Change | File |
|---|---|
| `ManifestConfig` additions: `suppressions: List[Suppression]`, `target_k8s_version: str = "1.30"`, `image_digest: Optional[str]`, `writable_paths: List[str] = ["/tmp"]`, `egress_rules: List[EgressRule]`, `service_type: ClusterIP|None`, `automount_service_account_token: bool = False`, `fs_group_change_policy`, `apparmor: bool = True`, `pdb: PDBConfig` | `models/kubernetes_models.py` |
| `SecurityContext` model: add `seccomp_profile`, `apparmor_profile`; defaults stay maximal | `models/kubernetes_models.py` |
| Unify workload rendering: single `_build_pod_spec()` consumed by `_generate_workload` and `_generate_job` so Jobs/CronJobs inherit identical hardening; path-aware injection per workload kind | `services/manifest_generator.py` |
| Emit ServiceAccount, always-on NetworkPolicy (default-deny + port allows + DNS egress), PDB, StatefulSet headless Service | `services/manifest_generator_helpers.py` (new `generate_service_account`, rewrite `generate_network_policy`, `generate_pdb`; new `generate_headless_service`) |
| `imagePullPolicy: Always`; image handling: if `image_digest` given emit `repo@sha256:`, else emit tag + completeness finding `VOL-K8S-IMG-DIGEST` (suppressible) | `services/manifest_generator.py` |
| Auto-emptyDir injection for `writable_paths` when `read_only_root_filesystem` | `services/manifest_generator.py` |
| Suppression receipts: annotations `volundr.asgard/suppress-<rule>` + `volundr.asgard/rationale` on affected objects; suppressed rules relax the corresponding emitted field (e.g. `runAsNonRoot` suppression permits `runAsUser: 0` **only** with receipt) | generator + plan-06 engine |
| Delete local `validate_manifests` / `calculate_best_practice_score`; call `Validation` engine + scoring engine on rendered YAML | `services/manifest_generator_helpers.py`, `manifest_generator.py` |
| Fix ConfigMap stub content (currently emits fake `example.conf`; should emit `data` from `config.env_vars` or an explicit `configmap_data` field) and Secret stub (emit `stringData` keys as completeness findings, never fake empties silently) | `manifest_generator_helpers.py:27-45` |
| CLI: `--target-k8s-version`, `--suppress RULE:TARGET:REASON` (repeatable), `--digest`, remove misleading defaults | `cli/_parser_commands_1.py`, `cli/handlers_infra.py` |

## 4. Generation Template (per Deployment, target shape)

ServiceAccount(automount:false) → Workload(podSpec: seccomp+appArmor RuntimeDefault, fsGroup, container: full matrix + pullPolicy Always + emptyDir mounts) → Service → NetworkPolicy(default-deny I/E + allows) → PDB. All objects labeled `app.kubernetes.io/name|instance|managed-by: volundr` (move off bare `app:` gradually; keep `app` in selectors to avoid immutable-selector breakage — RESEARCH_07 immutable-fields table).

## 5. Security Policies Enforced (rule pack, plan 06 registry)

`VOL-K8S-` rules asserting presence-of-safety for every matrix row above, each mapped to its CIS/NSA reference (metadata), CRITICAL for runAsNonRoot/privilege-escalation/capabilities, HIGH for RO-rootfs/seccomp/automount/NetPol-presence, MEDIUM for pullPolicy/digest/PDB, LOW for label hygiene.

## 6. Phased Steps

1. Model extensions + unified pod-spec builder + Jobs/CronJobs parity (pure hardening, no suppression dependency).
2. Always-on companions (SA, NetPol, PDB, headless Svc) + emptyDir injection + pullPolicy/digest.
3. Suppression integration + profile-as-preset redefinition + receipts.
4. Validation/scoring delegation; delete local scorer; CLI flags.

## 7. Testing Notes

- Extend `tests_Volundr/test_kubernetes.py`: parametrize the full control matrix over all five workload kinds (assert exact YAML paths from RESEARCH_03's table).
- Golden files per (workload × suppression-set); `kubeconform -strict` L3_Contract gate; `kube-score`/`kubesec` parity check when available (target: zero findings un-suppressed).
- Regression: StatefulSet renders its headless Service; RO-rootfs manifests include `/tmp` emptyDir; NetPol always present; DNS egress allowed.
- Suppression receipts round-trip: generate → validate → suppressed rules yield zero warnings and annotations present.

## 8. Doc Reconciliation (`_Docs/Asgard/Volundr/Kubernetes-Module.md`)

- Docs list `SecurityProfile.RESTRICTED/BASELINE/PRIVILEGED`; code has `BASIC/ENHANCED/STRICT/ZERO_TRUST` — rewrite for profile-as-suppression-preset model.
- Documented fields that don't exist: `create_service`, `create_configmap`, `create_secret`, `create_network_policy`, `create_pdb`, `tolerations`, `affinity`, `env_from_secrets`, `env_from_configmaps`, `resources.requests/limits` dict shape, probe `port`/`http_path` names. Either implement (tolerations/affinity are cheap, add to model) or correct docs; decide per field during phase 1.
- CLI doc lists `--cpu-limit`, `--memory-limit`, `--service-port`, `--type`, `--output` — parser has `--output-dir`, `--port`, etc. (`cli/_parser_commands_1.py:11-39`). Align both directions after CLI changes.
