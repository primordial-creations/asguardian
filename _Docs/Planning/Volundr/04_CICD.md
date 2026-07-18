# Volundr Upgrade Plan — 04 Zero-Trust CI/CD Pipeline Generation (P0)

**Scope:** `Asgard/Volundr/CICD/` (models + services).
**Depends on:** 06 (suppression schema, rule registry).
**Research basis:** DEEPTHINK_04 (Zero-Trust Orchestration: the five generative controls), RESEARCH_06 (SLSA v1.0 build track, provenance formats, per-platform capabilities, attack anatomy incl. March 2026 TeamPCP tag poisoning), RESEARCH_05 (pipeline as validation orchestrator).

---

## 1. Why (Research Rationale) — highest blast radius in Volundr

DEEPTHINK_04 Domain A lists the statically-fixable orchestration-plane flaws; the current generator (`services/pipeline_generator_helpers.py`) exhibits **all of them**:

1. **No `permissions:` block** anywhere → generated GitHub workflows inherit the dangerous `write-all` default token.
2. **Mutable action refs**: docs and defaults use `actions/checkout@v4` style tags. RESEARCH_06's March 2026 TeamPCP incident (76/77 trivy-action tags force-pushed malicious; KICS action likewise; downstream LiteLLM/axios compromises) is the direct empirical case against this.
3. **No injection immunity**: nothing prevents `run: echo "${{ github.event... }}"`; the generator must always route context through `env:` (DEEPTHINK_04 §B).
4. **No default `timeout-minutes` emitted**: model has `timeout_minutes: int = 60` on stages but GitHub emission only writes it if truthy — verify and enforce always-on; steps have none by default.
5. **Static-secret orientation**: `PipelineConfig.secrets: List[str]` encourages long-lived credentials; no OIDC scaffolding (DEEPTHINK_04 §A; Codecov attack anatomy in RESEARCH_06).
6. **No build/deploy trust segregation** (DEEPTHINK_04 §C fork-execution model) and no SLSA provenance/SBOM steps (RESEARCH_06).
7. Scoring rewards only triggers/stages/caching/env/timeouts — zero security dimensions (fixed via plan 07).

## 2. Target State

Generated pipelines are **zero-trust by construction**:

1. **Least privilege:** workflow-level `permissions: {}`; each job declares only needed scopes (e.g. build job `contents: read`; provenance job `id-token: write, attestations: write`). GitLab: no equivalent token block — enforce via job-scoped variables and documented PEP hooks (RESEARCH_06 GitLab section).
2. **SHA pinning:** every `uses:` resolved to full commit SHA with the human tag as trailing comment (`uses: actions/checkout@<sha> # v4.2.2`). Generator ships a curated pin-map for well-known actions (checkout, setup-python, setup-node, cache, upload/download-artifact, attest-build-provenance, docker/build-push) refreshed at release time; unknown actions passed by the user emit `VOL-CICD-PIN` finding unless already SHA-pinned or suppressed. Pair with a generated Renovate config snippet (RESEARCH_06 dependency-pinning section).
3. **Injection immunity:** `StepConfig.run` containing `${{ ... }}` referencing user-controllable contexts (event title/body/branch names, per DEEPTHINK_04 Domain A list) is rewritten: context → job/step `env:` var → `"$VAR"` in script. Non-rewritable cases fail generation (suppressible).
4. **Bounded execution:** `timeout-minutes` on every job (default 30, model default reduced from 60) and on long-running steps; `concurrency` emitted by default with `cancel-in-progress: true` for PR triggers.
5. **OIDC over static secrets:** new `OIDCConfig` (provider: aws|gcp|azure|vault, role/audience) generates the token-exchange step (`aws-actions/configure-aws-credentials@<sha>` with `role-to-assume`, `permissions: id-token: write`). Passing cloud keys via `secrets:` list yields `VOL-CICD-STATIC-SECRET` HIGH finding (suppressible).
6. **Build/deploy split** (`split_trust: bool = True` for pipelines with a deploy stage): untrusted build job with `permissions: {}` + zero secrets uploads a sealed artifact; deploy job (separate workflow via `workflow_run` for GitHub, or protected environment + `needs` fallback) downloads, verifies, assumes OIDC, deploys (DEEPTHINK_04 §C).
7. **SLSA provenance & SBOM** (`provenance: bool`, `sbom: bool`): GitHub → `actions/attest-build-provenance` (native L3 on hosted runners, RESEARCH_06); GitLab → runner-native provenance (L2) + documented PEP path to L3; Azure/CircleCI → scripted Cosign/DSSE steps; Jenkins → refuse `provenance=True` with explanatory error pointing at Tekton Chains (RESEARCH_06 platform matrix). SBOM via syft/trivy step, attached to the in-toto bundle (JSON Lines).
8. **Self-audit:** generated GitHub workflows include an optional `zizmor`/`actionlint` lint job (RESEARCH_06 tooling section) and pass both by construction.
9. Missing platform: `CICDPlatform.CIRCLECI` exists in the enum but `pipeline_generator.py` has no emitter — either implement (OIDC-capable per RESEARCH_06) or remove from enum + docs.

## 3. Concrete File/Module Changes

| Change | File |
|---|---|
| Model additions: `permissions: Dict[str,str]` (workflow+job), `oidc: Optional[OIDCConfig]`, `provenance/sbom: bool`, `split_trust: bool`, `suppressions: List[Suppression]`, `harden_runner: bool` (StepSecurity egress allowlist wrapper, DEEPTHINK_04 §E), step-level `timeout_minutes` default | `models/cicd_models.py` |
| Pin-map data + resolver (`known_action_pins.py`, dict tag→sha, release-time refresh script note) | new `services/action_pins.py` |
| GitHub emitter rewrite: permissions blocks, SHA pinning, env-var interpolation rewrite, always-timeout, provenance/SBOM jobs, split-trust dual-workflow output (return multiple files: extend `GeneratedPipeline` with `files: Dict[str,str]` like GitOps' model) | `services/pipeline_generator_helpers.py::generate_github_actions`, `services/pipeline_generator.py`, `models/cicd_models.py` |
| GitLab emitter: job-scoped variables, `timeout`, provenance flag, `rules` hardening; document PEP injection points as comments | `generate_gitlab_ci` |
| Azure/Jenkins emitters: timeouts, ephemeral-agent notes; Jenkins provenance refusal | `generate_azure_devops`, `generate_jenkins` |
| Injection-rewrite pass shared across emitters (works on `StepConfig` before platform rendering) | new `services/context_hardening.py` |
| Validation: delete local `validate_pipeline`/`calculate_best_practice_score`; register `VOL-CICD-*` rules (missing-permissions CRITICAL, mutable-ref HIGH, injection CRITICAL, static-secret HIGH, no-timeout MEDIUM, no-provenance MEDIUM/INFO by env profile) in plan-06 engine; scoring via plan 07 | `pipeline_generator_helpers.py`, `Validation/services/` |
| Suppression receipts: `# volundr:suppress=<rule> <reason>` comment above offending key (comment-preserving emission: build YAML via ruamel or post-process string) | emitters |
| CLI: `--oidc-provider`, `--provenance`, `--split-trust`, `--suppress` | `cli/_parser_commands_1.py:99-112`, `cli/handlers_infra.py` |

## 4. Generation Template (GitHub Actions, target shape)

```yaml
name: ci
on: {push: {branches: [main]}, pull_request: {branches: [main]}}
permissions: {}                      # workflow default: nothing
concurrency: {group: "${{ github.workflow }}-${{ github.ref }}", cancel-in-progress: true}
jobs:
  build:
    permissions: {contents: read}
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: step-security/harden-runner@<sha>   # optional, egress allowlist
      - uses: actions/checkout@<sha>  # v4.2.2
      - env: {PR_TITLE: "${{ github.event.pull_request.title }}"}
        run: echo "$PR_TITLE"         # never inline-interpolated
      - uses: actions/upload-artifact@<sha>
  provenance:
    needs: build
    permissions: {id-token: write, attestations: write, contents: read}
    ...actions/attest-build-provenance@<sha>
# deploy emitted as second file .github/workflows/deploy.yml on workflow_run
```

## 5. Phased Steps

1. **Immediate hardening (no new models):** `permissions: {}`, SHA pin-map for defaults, always-timeout, concurrency default, injection rewrite. This alone closes the CRITICAL gaps.
2. OIDC config + static-secret findings; provenance/SBOM jobs; CircleCI decision.
3. Split-trust multi-file output; harden-runner option; GitLab PEP documentation comments.
4. Validation/scoring delegation + suppression receipts + CLI.

## 6. Testing Notes

- `tests_Volundr/test_cicd.py`: assert every emitted GitHub job has `permissions` and `timeout-minutes`; assert zero `${{` inside any `run:` string across all fixtures (structural injection-immunity invariant, DEEPTHINK_04 §B); assert all `uses:` match `@[0-9a-f]{40}`.
- L3_Contract: `actionlint` and `zizmor` (skip-if-unavailable) must pass with zero findings on golden outputs.
- Split-trust: build workflow fixture has no secrets/OIDC; deploy workflow triggers on `workflow_run` only.
- Jenkins provenance request raises with actionable message.
- Adversarial: user-supplied step with `run: echo ${{ github.event.issue.title }}` is rewritten, not emitted verbatim.

## 7. Doc Reconciliation (`_Docs/Asgard/Volundr/CICD-Module.md`)

- Every YAML example in the doc shows mutable `@v4`/`@v5` refs, no permissions, no timeouts — regenerate all examples from the new emitters (goldens as source of truth).
- Doc scoring table replaced by pointer to plan-07 scheme.
- Document CircleCI support status once decided; document `secrets:` deprecation path toward OIDC.
