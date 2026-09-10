# Performance report completion

Each enabled analyzer is required. Disabled analyzers appear as skipped in `analyzer_outcomes`; execution failures and unavailable inputs/dependencies remain distinct from a completed scan with no findings. Successful subreports stay visible if another analyzer fails. Diagnostics describe failure classes without copying source text or private exception payloads.

`is_complete` requires every enabled analyzer's report and rejects failed outcomes. `performance_score` is now nullable: incomplete reports serialize it as JSON null and cannot be healthy. Complete reports retain the existing severity penalties. Consumers must check completeness and reject a null score, never substitute zero or 100. Legacy reports missing required subreports are incomplete when loaded into this model.

The per-analyzer convenience methods explicitly skip other analyzers without changing the caller's configuration. The performance CLI returns failure for an incomplete report; the comprehensive scan emits an INCOMPLETE performance step and uses the actual total issue count. Text reports label incomplete scores; JSON reports include typed outcomes and completeness.

This changes the public score contract and needs consumer/package adoption before release. Hercules's separate F03 security scanner protocol is unaffected by this performance model change.
