# Asgard Round 36 ASG-04 independent review v2

## Verdict: NO-GO

Corrected candidate `28130ca9242fbbc9d210529a8dd62687c00aebee` resolves all eight v1
findings and pins every scalar field's JSON-schema type plus both complete `Literal` domains. One
public nested type remains unprotected: changing `ROIAnalysis.roi_by_type` from
`Dict[str, float]` to `Dict[Any, float]` leaves all 38 focused tests green.

This is a real validation-contract regression rather than a schema-only distinction. The frozen
production model rejects `ROIAnalysis(roi_by_type={1: 2.5})` with a `ValidationError`; the widened
mutation accepts the same non-string key. The current test asserts numeric mapping values but never
asserts the declared string-key type, and JSON Schema's object representation does not express
that Python construction boundary by itself.

## Required correction

Add a focused rejection assertion for a non-string `roi_by_type` key and a distinct
`Dict[str, float]` to `Dict[Any, float]` adverse mutation. Refreeze the commit, incremental/full
patches, report, evidence, and hashes, then request v3 review. Retain the 195-to-188 allowlist
entries until the corrected packet receives GO.

## Independent mutation evidence

All eight v1 survivor mutations now reject individually:

- removing `high` confidence;
- adding an undocumented remediation kind;
- widening the FileFriction counter from integer to number;
- widening ROI mapping values to `Any`;
- widening remediation unit to `Any`;
- widening an EffortModels field to `Any`;
- widening a TimeProjection field to `Any`;
- widening an InterestRates field to `Any`.

Seven additional scalar mutations across the remaining model field families also reject. The sole
survivor was `ROIAnalysis.roi_by_type: Dict[str, float]` to `Dict[Any, float]`, with `38 passed`.

## Verified evidence

- Baseline: `b331ca55cc71736a41047083c041c54f94d17a89`.
- Candidate: `28130ca9242fbbc9d210529a8dd62687c00aebee` on non-`main` branch
  `work/round36-asgard-asg04`.
- Incremental patch SHA-256:
  `ff245143d7049c000d8867949e16f8d06f9ce9707bcdbb7bdc4cc897bef38a43`.
- Full recovery patch SHA-256:
  `966f0e7a27c79d9bcd37d13772e3eb3323cd237a35a70bedafdc985a9d267899`.
- The incremental patch applies against a workspace index populated from the baseline and against
  the live canonical integration checkout at
  `612d2a8650232adb10a58e7ed62f27c443a489b4`. The canonical allowlist blob is the exact preimage,
  and the new test path remains absent there.
- Both v2 patches reverse-check from a fresh clone of the frozen candidate.
- All evidence-v3 referenced artifact hashes match.
- The allowlist remains sorted and unique at exactly 195 baseline entries and 188 candidate
  entries.
- Independent focused rerun: 38 passed in 2.02 seconds.
- Independent complete L3/meta rerun: 1,540 passed and 4 skipped in 13.12 seconds.
- The baseline stale-entry control and the author's 20/20 mutation result are internally
  consistent.
- `git diff --check` passes.

Author report v3 SHA-256:
`502346f77ccef50926c92e2d7162dd8964bd60c4ae8b1dd0e52036e233563ab2`.
Evidence v3 SHA-256:
`efe4ae5c7f8a4e3cdade3f71b71ffae1f5aa30a2042aca96aad10a11abb093b8`.
Preservation v2 SHA-256:
`d4a1ab101d3d7e98acbd170848eb237fa4b638518b0262a27344fd463740c89c`.

Ruff remains unavailable locally and remains an external-runner gate. The temporary
`pytest-of-jake/` path belongs only to the workspace-backed review clone and is absent from the
candidate commit and reviewed patches.
