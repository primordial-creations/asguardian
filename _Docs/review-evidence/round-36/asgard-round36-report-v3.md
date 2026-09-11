# Asgard Round 36 ASG-04 author report (corrected v2 candidate)

## Scope

This shrink-only L3 ratchet covers seven public technical-debt value models in `Asgard.Bragi.Quality.models.debt_models`: `RemediationFunction`, `EffortInterval`, `FileFriction`, `ROIAnalysis`, `TimeProjection`, `EffortModels`, and `InterestRates`. The corrected 38-case suite pins every public field's JSON-schema type, typed mapping values, both complete Literal domains, exact default and custom wire shapes, declared constrained inputs, computed effort midpoints, and independent mutable ROI maps. The allowlist falls from 195 to 188 entries.

## Git and preservation

- Shared Asgard start/current at the final preservation check: branch `integration/all-current-updates-20260908`, HEAD `612d2a8650232adb10a58e7ed62f27c443a489b4`.
- Isolated workspace branch: `work/round36-asgard-asg04`.
- Isolated snapshot commit: `b331ca55cc71736a41047083c041c54f94d17a89`, containing the shared visible worktree before author edits.
- Rejected v1 feature: `9338ffd5742842ad4b7798827eb76e3fef3c39b2`.
- Corrected v2 feature: `28130ca9242fbbc9d210529a8dd62687c00aebee`.
- All 53 shared Asgard dirty paths match the candidate baseline byte for byte. Shared Asgard was read only, and the v2 incremental patch currently passes `git apply --check` there.
- The candidate is clean. Root must recheck applicability immediately before integration because concurrent agents may advance canonical state.
- Adrasta was briefly switched by an incorrectly scoped branch command, then immediately restored to `integration/all-current-updates-20260908` with dirty bytes retained and no file edits by this lane. Final preservation evidence records the restored branch, HEAD, and status identity.

## Independent v1 rejection and correction

Independent review v1 (`25aee8728b5519a168acd0d33d5d6fadd944aa687f8b4942726e020aba91c7ce`) rejected the first freeze because eight field-type/Literal-domain mutations survived. The corrected suite uses the models' public JSON schemas to distinguish integer, number, string, enum and typed-mapping contracts across every field. It also asserts the exact remediation-kind and confidence domains. All eight reviewer mutations now reject individually; v1 artifacts remain preserved as rejected evidence.

## Validation

- Corrected focused: **38 passed**, 113 warnings.
- Corrected complete L3/meta: **1,540 passed, 4 skipped**, 236 warnings.
- Baseline stale-entry control: exit 1 and names exactly the seven newly covered models.
- Corrected adversarial source mutations: **20/20 rejected** from a proven green baseline. This includes every v1 reviewer survivor plus constraints, defaults, computation and wire-value changes.
- `git diff --check` passes.
- Both corrected patches reverse-check from the clean v2 feature tree.
- Corrected incremental patch passes `git apply --check` against the current shared Asgard worktree.
- Ruff is unavailable in the local PATH, so locked lint/format remains an external-runner gate already retained by ASG-04.

## Integration

Apply only `asgard-round36-asg04-incremental-v2.patch` after final exact preimage/applicability verification. The v2 full patch exists for recovery and includes the copied pre-existing worktree state. Do not integrate either v1 patch.
