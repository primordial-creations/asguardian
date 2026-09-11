# Asgard Round 36 ASG-04 independent review v1

## Verdict: NO-GO

Frozen candidate `9338ffd5742842ad4b7798827eb76e3fef3c39b2` adds useful default,
validation, computation, and serialization checks, and its 195-to-188 allowlist ratchet is
mechanically correct. It does not yet satisfy Asgard's L3 contract bar because the suite does not
pin the declared field types or both `Literal` domains. Eight independent contract-breaking
mutations survive all 31 focused tests.

## Required corrections

1. Pin the field annotation/schema for every public field of all seven removed models. Exact
   Python-dictionary equality is insufficient for wire types because values such as `17` and
   `17.0` compare equal. Use exact model JSON-schema assertions, explicit field-annotation
   assertions, incompatible-input rejection cases, or an equivalent oracle that distinguishes
   integer, number, string, and typed mapping values.
2. Pin both `Literal` domains exhaustively. `RemediationFunction.kind` must remain exactly
   `constant`, `linear`, and `linear_with_offset`; `EffortInterval.confidence` must remain exactly
   `high`, `medium`, and `low`. The current tests accept the known remediation values and reject
   one unknown value, but they do not reject adding another allowed value; they also never exercise
   the valid `high` confidence value.
3. Add distinct adverse mutations for these type and domain contracts and refreeze the commit,
   patches, report, evidence, and hashes. Keep the seven models allowlisted until the strengthened
   tests pass independent review.

The test-module docstring should say “declared constrained inputs” or the implementation should
add separately justified validation before claiming all inputs are bounded. The production models
currently accept an inverted `EffortInterval` and negative values in `EffortModels` and
`InterestRates`; this observation does not itself require a behavior change for this tests-only
packet, but the evidence must not imply validation that does not exist.

## Surviving independent mutations

Each mutation was applied alone in a workspace-backed clone of the frozen commit, followed by the
complete 31-test focused file. Every run returned zero with `31 passed`:

- remove the valid `high` member from `EffortInterval.confidence`;
- add an undocumented `exponential` member to `RemediationFunction.kind`;
- change `FileFriction.churn_commits_90d` from `int` to `float`;
- change `ROIAnalysis.roi_by_type` from `Dict[str, float]` to `Dict[str, Any]`;
- change `RemediationFunction.unit` from `str` to `Any`;
- change `EffortModels.complexity_reduction_factor` from `float` to `Any`;
- change `TimeProjection.current_debt_hours` from `float` to `Any`;
- change `InterestRates.high_complexity` from `float` to `Any`.

These are material public-contract regressions under
`_Docs/Delivered/Planning/TestCoverage/L3_Plan.md`, which defines L3 as coverage of field names,
types, required fields, and validation errors.

## Verified evidence

- Baseline identity: `b331ca55cc71736a41047083c041c54f94d17a89`.
- Candidate identity: `9338ffd5742842ad4b7798827eb76e3fef3c39b2` on non-`main` branch
  `work/round36-asgard-asg04`.
- Incremental patch SHA-256 matched
  `ec0fce44fd7ea585b31068a66b12b3d314666ba828b9f808c3f9ce2f375e2143`.
- Full recovery patch SHA-256 matched
  `54e4fe89f9bbdbd1459dab13eb5075b5cfeefa1e27eab2f6865103164c769101`.
- The incremental patch applies to the live canonical integration checkout at
  `612d2a8650232adb10a58e7ed62f27c443a489b4`, whose allowlist blob remains the exact candidate
  preimage and whose new test path remains absent.
- The incremental patch applies against a workspace index populated from the synthetic baseline.
  Both incremental and full patches reverse-check from an untouched clone of the frozen commit.
- Allowlist entries are sorted and unique: exactly 195 at baseline and 188 at candidate.
- Candidate test bytes match the separately supplied test fixture, SHA-256
  `2ac432d714960a15071106d0cc3518271fa55d8f2e6cb11334a920a2ac992a4e`.
- Independent focused rerun: 31 passed.
- Independent complete L3/meta rerun: 1,533 passed and 4 skipped in 15.27 seconds.
- Baseline stale-entry evidence names exactly the seven removed models.
- The author's twelve supplied mutations are all rejected, but none probes the surviving field
  type or exhaustive-domain failures above.
- `git diff --check` passes.

Author report v2 SHA-256:
`e6873d9de209f318ad986e9d931e124050d13a689f200239c9ae61daf6ad20a6`.
Evidence v2 SHA-256:
`26e1ffab2c975b286e86e7fe6b2d1ddafb26bcd269c70e3f1f2753651251991f`.
Preservation evidence SHA-256:
`3f77c48fb581b071c8c7416cbc23eb2dbadf18cd96d638e03f2710544d2c3a25`.

Ruff remains unavailable locally and therefore remains an external-runner gate, as the author
report states. This limitation does not affect the NO-GO finding.
