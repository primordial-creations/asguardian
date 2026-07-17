# Volundr Upgrade Plan — 03 Dockerfile & Compose Generation (P1)

**Scope:** `Asgard/Volundr/Docker/` and `Asgard/Volundr/Compose/` (dedup + upgrade).
**Depends on:** 06 (suppressions/rules), 07 (scoring).
**Research basis:** RESEARCH_10 (hadolint/CIS Docker matrix, BuildKit secrets, digest pinning, compose-spec, Kompose limits), RESEARCH_04 (image scanners, VEX/SBOM pairing), DEEPTHINK_02 (suppressions).

---

## 1. Why (Research Rationale)

RESEARCH_10's empirical baseline (Durieux et al.: 16,145 smells in 11,313 Dockerfiles; +48 MB avg per smelly image; up to 89% size reduction from cache/package fixes) justifies enforcing the full hadolint/CIS matrix at generation time. Current `Docker/services/dockerfile_generator.py` emits multi-stage/USER/HEALTHCHECK/LABELs but misses, versus the matrix:

| Gap | Rule (RESEARCH_10) |
|---|---|
| No `# syntax=docker/dockerfile:1.x` directive; no BuildKit `--mount=type=secret` support — secrets can only enter via ENV/ARG (bakes into layers) | §3.6 |
| No digest pinning for `FROM` (tags only); `:latest` merely warned | DL3006 / §3.2 (digest + Renovate pairing) |
| No `SHELL ["/bin/bash","-o","pipefail","-c"]` before piped RUNs | DL4006 |
| Non-root user creation not generated (user must hand-write `adduser` run command); no `useradd -l` guidance | DL3002/DL3046 §3.3 |
| No package-manager hygiene generation: version pinning (DL3008/3013/3016/3018), same-layer cache cleanup `rm -rf /var/lib/apt/lists/*` (DL3009) — `optimize_layers` naively joins all RUNs with `&&` regardless of semantics | §3.5 |
| No COPY-vs-ADD enforcement in generation (validator has DL3020 but generator would emit whatever config says) | §3.4 |
| Cache ordering not guaranteed (copy_commands emitted in user order; deps-then-source ordering not enforced/advised) | §3.5 |

**Duplication:** two Compose implementations exist — `Docker/services/compose_generator.py` (+`docker_models.py`) and the richer `Compose/` package (generator + validator + models). They drift (e.g. `Compose/services/compose_generator_helpers.py:178` still emits the obsolete top-level `version:` key in override files; docs show `version: "3.8"`). RESEARCH_10 §4.1: compose-spec makes `version` obsolete.

**Compose production misconfigurations** (RESEARCH_10 §5) not enforced: `depends_on` without `condition: service_healthy`; missing `restart: unless-stopped`; host-interface port bindings (`"6379:6379"` binds 0.0.0.0) instead of loopback/internal networks; volume permission bootstrap.

RESEARCH_04 adds the ecosystem pairing: generated Dockerfiles should ship with scanner integration guidance (Trivy as default gate: recall 0.96, 6-hour DB refresh, air-gap capable) and SBOM/VEX hooks rather than Volundr reimplementing CVE scanning.

## 2. Target State

### Dockerfile generator
- Always emits `# syntax=docker/dockerfile:1.7` header.
- `FROM` handling: `base_image_digest` field → `image:tag@sha256:...`; tag-only input emits `VOL-DOCKER-DIGEST` completeness finding (suppressible) + generated `renovate.json` snippet option (RESEARCH_10 §3.2 workflow).
- New `secret_mounts: List[SecretMount]` → `RUN --mount=type=secret,id=...,target=...` and `ssh_mount: bool` → `--mount=type=ssh`; generator refuses plaintext secret-looking ENV/ARG values (`VOL-DOCKER-SECRET-ENV` CRITICAL, suppressible).
- Non-root scaffold: `user: NonRootUser(name, uid=65532, create=True)` generates `RUN useradd -l -u 65532 -m appuser` (or `adduser -D` on alpine, detected from base image) before final `USER`; ordering guaranteed after chown/install steps (RESEARCH_10 §3.3).
- Package manager intelligence: recognize apt/apk/pip/npm in `run_commands`; merge install+cleanup into one layer, inject `--no-install-recommends`, `rm -rf /var/lib/apt/lists/*`, `--no-cache-dir`, `--no-cache` respectively; warn on unpinned installs (DL3008-family) instead of blind `&&`-joining.
- `SHELL` pipefail emitted automatically when any RUN contains `|`.
- COPY ordering: dependency manifests (`requirements.txt`, `package.json`, `go.mod`…) copied before source; `COPY . .` triggers `.dockerignore` generation + finding.
- Multi-stage default for compiled/build-dep ecosystems; hadolint stage rules (DL3021-24) guaranteed by construction.

### Compose (single implementation)
- **Delete `Docker/services/compose_generator.py` + Compose parts of `docker_models.py`**; `Docker/__init__.py` re-exports from `Compose/` for one deprecation cycle. `Compose/` becomes the only engine.
- compose-spec output: no `version:` key anywhere (fix override generation).
- `depends_on` long form with `condition: service_healthy` whenever the dependency has a healthcheck; auto-generate healthchecks for known images (postgres `pg_isready`, redis `redis-cli ping`, mysql `mysqladmin ping` — RESEARCH_10 §5.1 table).
- `restart: unless-stopped` default for services without one (§5.2).
- Port exposure policy: only designated `edge` services may publish ports; internal services communicate over named networks; published ports for non-edge default to `127.0.0.1:` prefix; bare `H:C` publishing on datastores → `VOL-COMPOSE-EXPOSED` HIGH finding (§5.4).
- Named volumes preferred; bind mounts flagged; volume-permission bootstrap guidance finding when non-root user + fresh named volume (§5.3).
- Kompose-style Compose→K8s translation is explicitly **out of scope** (RESEARCH_10 §6 mismatches); document that K8s output comes from the Kubernetes module natively, and env secrets must become K8s Secrets (`valueFrom.secretKeyRef`) — add a Scaffold-level convenience later, not a translator.

### Scanner pairing (RESEARCH_04)
- `DockerfileConfig.emit_scan_workflow: bool` → optional CI snippet (Trivy image scan + SBOM cyclonedx + `.trivyignore`-discouraged/VEX-preferred comment). No scanning inside Volundr itself.

## 3. Concrete File/Module Changes

| Change | File |
|---|---|
| Model additions: `base_image_digest`, `secret_mounts`, `ssh_mount`, `non_root: NonRootUser`, `shell_pipefail: bool = True`, `syntax_version`, `suppressions` | `Docker/models/docker_models.py` |
| Emitter upgrades per §2 (syntax header, secret mounts, useradd -l, SHELL, package hygiene pass, copy ordering, `.dockerignore`) | `Docker/services/dockerfile_generator.py` (+ new `_package_manager_pass.py` helper) |
| Delete duplicate compose generator; re-export shim | `Docker/services/compose_generator.py`, `Docker/__init__.py` |
| compose-spec fixes: drop `version` (incl. override at `compose_generator_helpers.py:178`), healthcheck-gated depends_on, restart default, loopback/edge port policy, known-image healthchecks | `Compose/services/compose_generator*.py`, `Compose/models/compose_models.py` |
| Validators: fold `Compose/services/compose_validator*.py` + `Validation/services/dockerfile_validator*.py` rules into plan-06 registry (keep DL IDs; add CKV_DOCKER-equivalents: exposed SSH port, missing healthcheck CKV_DOCKER_2, last-user-root CKV_DOCKER_8 — RESEARCH_10 §2.2) | `Validation/services/` |
| Scoring: delete `_calculate_best_practice_score` in both generators; plan 07 | generators |
| CLI: `--digest`, `--secret-mount id[:target]`, `--edge-service NAME`, `--suppress` | `cli/_parser_commands_1.py:77-92` |

## 4. Phased Steps

1. Dockerfile hardening that needs no new deps: syntax header, SHELL pipefail, useradd -l scaffold, package-hygiene pass, copy ordering, `.dockerignore`.
2. Digest pinning + secret mounts + suppressions/receipts (`# volundr:suppress=` trailing comments).
3. Compose dedup (shim + delete), compose-spec fixes, healthcheck/depends_on/ports/restart policies.
4. Validation/scoring delegation; scanner-pairing snippet emission.

## 5. Testing Notes

- `tests_Volundr/test_docker.py`: golden Dockerfiles per (ecosystem × multi-stage × secret-mount) matrix; L3_Contract gate: `hadolint` zero findings (skip-if-unavailable); assert first line is syntax directive; assert no `${SECRET}`-shaped ENV values.
- Compose: `docker compose config --quiet` L3 gate (RESEARCH_10 §4.2.1); assert absence of `version:` key in all outputs incl. overrides; assert datastore services publish no host ports in default fixtures; depends_on renders long-form with `condition: service_healthy` when dependency has healthcheck.
- Dedup regression: `from Asgard.Volundr.Docker import ComposeGenerator` still imports (shim) with DeprecationWarning.
- Adversarial: config attempting `ENV AWS_SECRET_ACCESS_KEY=...` fails without suppression.

## 6. Doc Reconciliation (`_Docs/Asgard/Volundr/Docker-Module.md`)

- Doc shows `version: "3.8"` in ComposeConfig and output — remove (compose-spec).
- Doc's `DockerfileConfig` shape (flat `copy_files`, `run_commands`, `multi_stage` bool, `build_stages`) diverges from code (`stages: List[BuildStage]`, `optimize_layers`, `use_non_root`) — regenerate examples from real models.
- Document the `Compose/` package (generator + validator) as the single Compose engine; document deprecation of `Docker.ComposeGenerator`.
- Add secret-mount, digest-pinning + Renovate pairing, and scanner-pairing sections.
