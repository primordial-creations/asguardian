# Asgard Round 36 ASG-04 independent review v3

## Verdict: GO

Frozen candidate `065104161285786fc872192ec5d8fbd63e22f73a` meets the Asgard L3
contract bar for the seven technical-debt value models. The 39 focused cases pin every public
field's JSON-schema type, ROI mapping key and value validation, complete remediation-kind and
confidence domains, the complete `TimeHorizon` name/value map, defaults, custom wire shapes,
declared bounds, computed interval values, and mutable-map isolation. The allowlist may shrink from
195 to 188 entries.

The v1 and v2 NO-GO findings are resolved. A fresh workspace-backed review clone rejected every
prior survivor plus analogous scalar, nested, and enum-name changes. No independent mutation
survived.

## Frozen identity and applicability

- Baseline: `b331ca55cc71736a41047083c041c54f94d17a89`.
- Candidate: `065104161285786fc872192ec5d8fbd63e22f73a` on non-`main` branch
  `work/round36-asgard-asg04`.
- Incremental patch SHA-256:
  `c0925b4a83640ebdde12de5d4bd5d25a7f1ce134f499abcc22469fe0afc2b8f9`.
- Full recovery patch SHA-256:
  `63f7edbad62311c52e568053704a5c3f807bef2b6a9a3f80620d25fb5c732211`.
- The incremental patch applies against a workspace index populated from the baseline and against
  the live canonical integration checkout at
  `612d2a8650232adb10a58e7ed62f27c443a489b4`.
- The live canonical allowlist blob remains the exact incremental preimage
  `f1b10ef5ef8094c57d5f83c3b7e2baa2ae9c118d`, and the new test path remains absent there.
- Both v3 patches reverse-check from a fresh clone of the frozen candidate.
- The candidate was clean at handoff. The review clone's `.review-tmp/` directory contains only
  reviewer test-run temp output and is absent from the candidate commit and both patches.

## Independent validation

- `git diff --check`: pass.
- Allowlist ratchet: 195 sorted unique entries at baseline; 188 sorted unique entries at candidate.
- Focused suite: 39 passed in 2.46 seconds.
- Complete L3/meta suite: 1,541 passed and 4 skipped in 13.20 seconds.
- All 21 author mutations reject from a green baseline.
- Seventeen independently replayed mutations reject, including all nine v1/v2 survivors:
  removal of `high` confidence, addition of a remediation kind, integer-to-number counter drift,
  ROI mapping value and key widening, string and numeric fields widened to `Any`, and a
  `TimeHorizon` member rename. Additional mutations covered analogous fields in each model.
- Direct boundary probe confirms the frozen `Dict[str, float]` model rejects a non-string ROI map
  key.
- Baseline stale-entry control names exactly the seven newly covered models.
- Every artifact referenced by evidence-v4 matches its recorded SHA-256.

Author report v4 SHA-256:
`44693f78fb86824e9da45ce623350e0bb87ebeea3c3cb09a5a5e671f1b8640fc`.
Evidence v4 SHA-256:
`74fac9494cec5beb77ee04b209c9413e994085c83ce430f587e063ca369ddcb4`.
Preservation v3 SHA-256:
`dca1771beab99fdc7b7cbb846c3e0f308988bde2bba003081f6deceb9be704cf`.

Ruff is unavailable locally and remains an external-runner gate, as the author report states.
This does not weaken the source-level L3 contract result.
