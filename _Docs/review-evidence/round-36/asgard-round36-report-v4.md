# Asgard Round 36 ASG-04 author report (corrected v3 candidate)

## Scope

This shrink-only L3 ratchet covers seven public technical-debt value models in `Asgard.Bragi.Quality.models.debt_models`: `RemediationFunction`, `EffortInterval`, `FileFriction`, `ROIAnalysis`, `TimeProjection`, `EffortModels`, and `InterestRates`. The final 39-case suite pins every public field's JSON-schema type, typed mapping key and value constraints, both complete Literal domains, exact default and custom wire shapes, declared constrained inputs, computed effort midpoints, and independent mutable ROI maps. The allowlist falls from 195 to 188 entries.

## Git and preservation

- Shared Asgard start/current at the final preservation check: branch `integration/all-current-updates-20260908`, HEAD `612d2a8650232adb10a58e7ed62f27c443a489b4`.
- Isolated workspace branch: `work/round36-asgard-asg04`.
- Isolated snapshot commit: `b331ca55cc71736a41047083c041c54f94d17a89`, containing the shared visible worktree before author edits.
- Rejected v1 feature: `9338ffd5742842ad4b7798827eb76e3fef3c39b2`.
- Rejected v2 feature: `28130ca9242fbbc9d210529a8dd62687c00aebee`.
- Corrected v3 feature: `065104161285786fc872192ec5d8fbd63e22f73a`.
- All 53 shared Asgard dirty paths match the candidate baseline byte for byte. Shared Asgard was read only, and the v3 incremental patch currently passes `git apply --check` there.
- The candidate is clean. Root must recheck applicability immediately before integration because concurrent agents may advance canonical state.
- Adrasta was briefly switched by an incorrectly scoped branch command, then immediately restored to `integration/all-current-updates-20260908` with dirty bytes retained and no file edits by this lane. Final preservation evidence records the restored branch, HEAD, and status identity.
- This lane removed only disposable caches/build output within its scratch candidate, freeing 405,036 KiB; source, Git history and all evidence remain.

## Independent rejections and corrections

Independent v1 review (`25aee8728b5519a168acd0d33d5d6fadd944aa687f8b4942726e020aba91c7ce`) rejected eight surviving field-type and Literal-domain mutations. V2 pinned public JSON schemas across every field and exact remediation-kind/confidence domains, rejecting those eight and seven analogous probes. Independent v2 review (`2859b71e533a1cf11197c8765b9212c6edc4bf074b83e774afcc91c9e13a5dc3`) then exposed JSON Schema's inability to express the Python key type of `ROIAnalysis.roi_by_type`; widening `Dict[str, float]` to `Dict[Any, float]` survived. V3 adds a direct non-string-key rejection contract and a distinct mutation. Both rejected versions and reviews remain preserved.

## Validation

- Final focused: **39 passed**, 113 warnings.
- Final complete L3/meta: **1,541 passed, 4 skipped**, 236 warnings.
- Baseline stale-entry control: exit 1 and names exactly the seven newly covered models.
- Final adversarial source mutations: **21/21 rejected** from a proven green baseline, covering every v1/v2 reviewer survivor plus analogous types, constraints, defaults, computation and wire-value changes.
- `git diff --check` passes.
- Both v3 patches reverse-check from the clean v3 feature tree.
- The v3 incremental patch passes `git apply --check` against current shared Asgard.
- Ruff is unavailable in the local PATH, so locked lint/format remains an external-runner gate already retained by ASG-04.

## Integration

Apply only `asgard-round36-asg04-incremental-v3.patch` after final exact preimage/applicability verification. The v3 full patch exists for recovery and includes the copied pre-existing worktree state. Do not integrate v1 or v2 patches.
