# Asgard Round 36 ASG-04 author report (v1)

## Scope

This shrink-only L3 ratchet covers seven public technical-debt value models in `Asgard.Bragi.Quality.models.debt_models`: `RemediationFunction`, `EffortInterval`, `FileFriction`, `ROIAnalysis`, `TimeProjection`, `EffortModels`, and `InterestRates`. The new contracts pin exact default and custom wire shapes, every documented remediation kind and time-horizon wire value, bounded inputs, computed effort midpoints, nested validation, and independent mutable ROI maps. The allowlist falls from 195 to 188 entries.

## Git and preservation

- Shared Asgard start: branch `integration/all-current-updates-20260908`, HEAD `612d2a8650232adb10a58e7ed62f27c443a489b4`, with substantial pre-existing worktree edits.
- Isolated workspace branch: `work/round36-asgard-asg04`.
- Isolated snapshot commit: `b331ca55cc71736a41047083c041c54f94d17a89` (the shared visible worktree copied before author edits).
- Feature commit: `9338ffd5742842ad4b7798827eb76e3fef3c39b2`.
- The shared Asgard checkout was read only. Root must revalidate the two-path preimage because concurrent edits are expected.
- Adrasta was briefly switched by an incorrectly scoped branch command, then immediately restored to `integration/all-current-updates-20260908` at the same HEAD with its dirty bytes retained. No files there were edited by this lane.

## Validation

- Focused: `31 passed`, 113 warnings.
- Complete L3/meta: `1533 passed, 4 skipped`, 236 warnings.
- Baseline stale-entry control: exit 1 and names exactly the seven newly covered models.
- Adversarial source mutations: all 12 rejected (default wire values, numeric bounds, function kind, confidence domain, computed midpoint, enum value, projection default, cost defaults, and interest defaults).
- `git diff --check` passes.
- Both frozen patches reverse-check from the feature tree.
- Ruff is unavailable in the local PATH, so locked lint/format remains an external runner gate already retained by ASG-04.

## Integration

Apply only `asgard-round36-asg04-incremental-v1.patch` to the matching current Asgard worktree after exact preimage/applicability verification. The full patch exists for recovery and includes the copied pre-existing worktree state.
