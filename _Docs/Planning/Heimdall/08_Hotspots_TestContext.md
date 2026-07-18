# 08 — Security Hotspots Discipline & Test-Context Engine

**Sources:** `_Docs/Research/Heimdall/Completed/DEEPTHINK_10` (hotspot epistemology), `DEEPTHINK_08` (test-context policy), `DEEPTHINK_03` (test-file confidence caps).

## Part A — Hotspot discipline (`Security/Hotspots/`)

### Rationale
The current `HotspotDetector` category list is broader than defensible. DEEPTHINK_10's core rule: a hotspot is *syntactically flawless code whose safety depends on extrinsic context* (intent, provenance, topology) — never a "failed finding." Reclassifying weak taint findings as hotspots to inflate precision is explicitly forbidden.

### Target category set — exactly six families (DEEPTHINK_10 §5)
1. Weak hashing: `hashlib.md5|sha1` (business-domain question).
2. Standard PRNG: `random.*` (unless plan-04 taint proves a security sink, which upgrades it to a finding).
3. Disabled transport security: `verify=False`, `ssl._create_unverified_context` (network-topology question).
4. Permissive bindings/CORS: `host='0.0.0.0'`, `allow_origins=['*']` (deployment question).
5. Opaque deserialization: `pickle.loads`, `yaml.load(Loader=Loader)` on non-taint-proven data (provenance question).
6. `cryptography.hazmat.*` usage (mathematical-soundness review).

**Remove/reroute the cop-outs:** current `REGEX_DOS` → plan-07 ReDoS analyzer (deterministic finding/skip); `SSRF` hotspot → plan-07 SSRF pipeline; `PERMISSION_CHECKS` (`os.chmod` blanket flag) → drop or fold into Misconfig with real conditions; `XML_EXTERNAL_ENTITY` → AST kwarg finding; generic `CRYPTOGRAPHIC_CODE` ("any use of hashlib") → only families 1/6 above. If the scanner lacks proof, it emits a Finding via taint or stays silent — never a hotspot.

### Workflow rules
- Hotspots reviewed only on **new code in PR scans**; never block pipelines on legacy bulk scans (exception-only philosophy).
- Volume guard: if >5 hotspots would attach to one PR, collapse to a single summary comment (the >5 threshold is where bulk "Mark as Safe" malicious compliance begins).
- Statuses: `TO_REVIEW`, `SAFE_IN_CONTEXT` (**requires mandatory justification text**, stored in `Shared/Issues` audit log), `FIXED`. **No "Acknowledged Risk" status** — risk acceptance belongs in a GRC/ticket system; a scanner UI granting it creates discoverable-negligence liability (DEEPTHINK_10 §4).

### Changes
- `Security/Hotspots/models`: prune `HotspotCategory` enum; add `justification` to review transitions; wire reviews into `Shared/Issues` persistence (issue_type `security_hotspot` already exists).
- `Reporting/PRDecoration`: hotspot summary block with per-PR cap.

## Part B — Test-Context Engine (new: `Security/context/test_context.py`)

### Rationale
No current suppression/downgrade for test code: `tests/conftest.py` MD5 fixtures and fake credentials surface at production severity. DEEPTHINK_08 supplies the full policy; DEEPTHINK_03 caps test-file exploitability confidence at 0.1.

### Context determination (composite, in precedence order)
1. **File-level** `TEST_UNIT` / `TEST_INTEGRATION`: path matches boundary regex `(?:^|/)(tests?|testing|specs?|__tests__)(?:/|$)` **AND** filename `^test_.*\.py$|.*_test\.py$`; or filename ∈ {`conftest.py`, `noxfile.py`, `factories.py`, `mocks.py`}. `integration|e2e|system` path segment → `TEST_INTEGRATION`. (Word-boundary matching prevents the `/ab_testing/` false positive; name+dir conjunction prevents `test_db_connection.py` prod-script suppression.)
2. **AST-level `TEST_FUNCTION` tainting** for files not tagged above: class inherits `unittest.TestCase`/`django.test.TestCase`; decorators `@pytest.fixture|@patch|@mock.patch|@responses.activate|@given`; or name `^test_` + contains `assert`. Context pushes/pops with AST scope so a prod helper in a test file — and a mock factory in `utils.py` — are each handled correctly.

### Contextual severity matrix (routing, applied post-detection pre-scoring)

| Category | TEST_UNIT / TEST_FUNCTION | TEST_INTEGRATION |
|---|---|---|
| Data-flow injection (SQLi/XSS/path traversal) | SUPPRESS | SUPPRESS |
| Weak crypto / weak PRNG | SUPPRESS | SUPPRESS |
| Command injection / SSRF | SUPPRESS | DOWNGRADE → LOW (CI-runner attack surface) |
| Network config (`verify=False`, hardcoded IPs) | SUPPRESS | DOWNGRADE → INFO |
| **Hardcoded secrets** | **NEVER suppressed** — dummy filter (plan 07.3) then CRITICAL | same |

Suppressed findings are retained with `suppressed_by_context=true` (visible via `--include-test-context`), excluded from score (plan 06) and gate (plan 09).

### Overrides (security-regression tests must stay scannable)
- Inline pragma `# heimdall: enforce` strips context tags for the node.
- `.heimdall.yml` `strict_scan_paths: ["tests/security/.*"]` bypasses the engine entirely.

### Changes
- `Security/context/test_context.py` (detector) + integration hook in the plan-04 dispatch pipeline so every module inherits it.
- `SecurityFinding` gains `context_tag` field; normalization engine (plan 06) consumes it.
- CLI flag `--include-test-context`; profile toggle `test_context_enabled` (default true).

## Testing
- Path-heuristic table tests (the DEEPTHINK_08 failure-mode list verbatim: `ab_testing/`, `test_flight_api.py`, `conftest.py`, student-exam `test/` app dir with pragma escape).
- Secrets-in-conftest fixture: high-entropy GitHub PAT stays CRITICAL; `sk_test_...` + `EXAMPLE` keys dropped.
- Hotspot cap test: PR fixture with 8 hotspots produces 1 summary + 0 inline.
- Round-trip: `SAFE_IN_CONTEXT` without justification text is rejected.
