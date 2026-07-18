# 09 — Quality Gate: New-Code Diff Gating, Suppressions, Anti-Flakiness

**Sources:** `_Docs/Research/Heimdall/Completed/DEEPTHINK_12` (CI gate policy), `DEEPTHINK_06` (F-beta by deployment profile), `DEEPTHINK_04` (FP/FN cost by stage).

## Rationale

`Bragi/QualityGate/services/quality_gate_evaluator.py` evaluates the "Asgard Way" gate on **absolute whole-project metrics** (ratings, duplication %, critical-vuln count). On a legacy codebase with 500 existing findings this blocks a developer's unrelated CSS change — the "hostage situation" that ends in an executive disabling the scanner (DEEPTHINK_12 §1). `Baseline/` exists but is not the fingerprint-based, AST-anchored diff mechanism the research requires.

## Target State — "High-Trust Guardrail"

### 1. Fingerprint-based regression (DEEPTHINK_12 §2)
Abandon count ratchets (gameable by suppressing an unrelated LOW to offset a new CRITICAL; and they punish debt cleanup). Compute per-finding fingerprint:
```
fingerprint = sha256(rule_id + normalized_file_path + ast_node_signature)
```
`ast_node_signature` = structural hash of the enclosing AST node (function/statement subtree), **excluding line numbers** so refactors that shift lines don't churn fingerprints. Reuse `common/_hash_cache.py` + tree-sitter/`ast` node spans (plan 01 `FileParseContext`).

Gate evaluation is diff-aware: compare PR-branch fingerprints against the target-branch (`main`) fingerprint set (persisted per branch, keyed by commit, alongside `Reporting/History`).

### 2. Blocking policy
- **Block iff a NEW finding of HIGH or CRITICAL severity** (post plan-06 normalization, post plan-08 context) is introduced.
- NEW MEDIUM/LOW → non-blocking inline PR comments (via `Reporting/PRDecoration`).
- Pre-existing baseline findings → ignored by the gate, pushed to `Shared/Issues` for async burndown (the 500 legacy findings don't block; EM allocates ~10% sprint capacity).
- Confidence coupling: only **Certain/Probable** (≥0.50) findings can block; Possible/Unlikely never block (plans 04/06). This operationalizes DEEPTHINK_06 Profile A ($F_{0.5}$, precision-weighted) for the developer-facing gate, versus Profile B ($F_2$, recall-weighted) for the async audit dashboard.

Keep the existing absolute "Asgard Way" gate as a selectable mode (`--mode=absolute`) for greenfield projects; default becomes `--mode=diff`.

### 3. Suppression governance (DEEPTHINK_12 §3)
Structured inline comments only (survive refactors, context-local, no central-registry merge conflicts):
```
# heimdall-ignore: SQLI - FP: input cast to int before query          # valid FP
# heimdall-ignore: SQLI - RISK ACCEPTED until 2026-12-01 - TICKET-123  # valid, expiring
# heimdall-ignore: SQLI                                                # INVALID -> gate fails
```
- A lightweight linter step enforces the schema (rule id + `FP:`/`RISK ACCEPTED until <date> - <ticket>`); missing justification fails the build. Expired `RISK ACCEPTED` dates fail the build; pure FP suppressions never expire (time-limited FPs randomly break unrelated PRs — operationally disastrous).
- Audit loop: newly merged `heimdall-ignore` comments emit to a review channel/report; weekly async tech-lead review (coaching, not synchronous blocking). Suppressions recorded in `Shared/Issues`.

### 4. Break-glass (DEEPTHINK_12 §3 escalation)
PR label `emergency-sec-bypass` → gate step skips gracefully, auto-files a P1 ticket + pages tech lead, 48h remediation SLA. Fully audited.

### 5. Zero-flakiness (DEEPTHINK_12 §4)
A blocking gate must be a deterministic state machine. Any rule proven non-deterministic (finding appears/disappears on identical input due to traversal order/timeout) forfeits blocking rights → demoted to warn-only or moved to the nightly async scan. Enforce with a determinism CI check: scan the same fixture twice, diff fingerprints, fail the rule (not the user) on mismatch. This is why plan-04 requires byte-identical repeat scans.

## Concrete Changes

| File | Change |
|---|---|
| `Bragi/QualityGate/services/quality_gate_evaluator.py` | add `mode=diff`; new-finding classification via fingerprints |
| `Bragi/QualityGate/fingerprint.py` | NEW: AST-node-signature hashing |
| `Bragi/QualityGate/baseline_store.py` | NEW (or extend `Baseline/`): per-branch fingerprint sets keyed by commit |
| `Bragi/QualityGate/suppressions.py` | NEW: inline-comment parser + schema linter + expiry check |
| `Shared/Issues` | store suppressions + baseline burndown items |
| `Reporting/PRDecoration` | NEW vs blocking comments; break-glass detection; suppression audit digest |
| `cli/handlers` | `heimdall gate evaluate <path> --mode=diff --base=main`; break-glass + suppression subcommands |

## Testing
- Diff-gate fixtures: new CRITICAL in PR → FAIL; pre-existing CRITICAL untouched → PASS; refactor shifting lines of an existing finding → not counted as new (fingerprint stability test).
- Debt-substitution test: introduce a CRITICAL while suppressing an unrelated LOW → still FAILs (proves ratchet abandonment).
- Suppression schema tests: valid FP passes; bare ignore fails; expired RISK-ACCEPTED fails.
- Break-glass test: label present → step skipped + P1 recorded.
- Determinism test harness reused from plan 04.
