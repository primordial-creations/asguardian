# Plan 05 — Security: Mitigation Vocabulary, Scope Matrix, SRI + Mixed-Content Checks

**Priority:** P1
**Primary research:** DEEPTHINK_06 (observable signals vs actual posture)
**Depends on:** Plan 01 (severity mapping); Plan 07 declares `httpx`

---

## 1. Rationale (research-backed)

Current state (`Asgard/Freya/Security/`):

- `services/security_header_scanner.py` (httpx-based) checks 11 headers via `_security_header_analyzers.py`; `csp_analyzer.py` parses directives and computes a `security_score`.
- Wording is plain pass/fail with a numeric "security score" — exactly the "security theater" DEEPTHINK_06 warns about. There is no SRI check, no mixed-content check, no disclaimer, no scope matrix.

DEEPTHINK_06's mandates:

1. **Asymmetry principle:** external observation reliably proves the *absence* of a defense, almost never the *effectiveness* of one. Reports must be framed as **Threat Mitigation**, not absence-of-vulnerabilities.
2. **Vocabulary:** never "Secure"/"Vulnerable". Use "Missing Mitigation"; rename score to **"Frontend Defense-in-Depth Score"** / "Resilience Grade".
3. **Conditional framing:** *"Your site lacks a CSP. If an XSS vulnerability exists, the browser has no instructions to block the payload…"* (assume-breach phrasing).
4. **"Yes, but…" contextualized passes:** a strict nonce-CSP pass must ship with "Manual Verification Required: ensure nonces are cryptographically random and unique per response."
5. **Executive disclaimer + Scope Matrix:** every report states what the tool validates (observable signal) vs what requires DAST/manual testing (actual posture), with the four-row matrix from the research (CSP / HSTS / SRI / Framing).
6. **Reliably inferable additions:** SRI absence on external scripts and mixed content are deterministic observable signals the tool should check but currently doesn't.

## 2. Target state

Security reports speak mitigation language end-to-end, carry the executive disclaimer and scope matrix, include SRI and mixed-content detection, and emit findings into Plan 01's severity pipeline with contextualized passes preserved (a pass can still carry a `manual_verification` note).

## 3. Concrete changes in `Asgard/Freya/Security/`

### 3.1 Models (`models/security_header_models.py`)

- New enum `MitigationStatus(str, Enum)`: `PRESENT = "present"`, `PRESENT_NEEDS_VERIFICATION = "present_needs_verification"`, `MISCONFIGURED = "misconfigured"` (present but self-sabotaging, e.g. `unsafe-inline`), `MISSING = "missing"`.
- Finding model gains optional fields: `mitigation_status`, `threat_context: Optional[str]` (the conditional assume-breach sentence), `manual_verification: Optional[str]` (the "yes, but" text), `observable_signal: Optional[str]` / `unverifiable_posture: Optional[str]` (scope-matrix row content).
- `SecurityHeaderReport`: rename display semantics of `security_score` → keep field name (API compat) but add `score_label: str = "Frontend Defense-in-Depth Score"`; add `disclaimer: str` (populated constant) and `scope_matrix: List[Dict[str, str]]`.

### 3.2 Vocabulary + framing pass (`_security_header_analyzers.py`, `csp_analyzer.py`, `cli/_formatters_security_console_links.py`)

- Sweep all analyzer message strings: "missing X header" → "Missing Mitigation: X"; any "secure"/"vulnerable" wording replaced per DEEPTHINK_06 §4A.
- Threat-context templates (static dict keyed by header): CSP, HSTS, X-Frame-Options/frame-ancestors, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, COOP/COEP/CORP — each a one-sentence conditional ("If … exists, the browser …").
- Contextualized passes: nonce/hash CSP → `manual_verification` = entropy/uniqueness text; HSTS pass → "verify the server drops plain-HTTP before preload pinning"; SRI pass → "hash pins a version, not its safety".
- Formatters print: score with new label, executive disclaimer block (verbatim from DEEPTHINK_06 §5), findings grouped by `MitigationStatus`, then the scope matrix as an appendix table. HTML reporter mirrors this.

### 3.3 New check: Subresource Integrity (`services/sri_checker.py`, new)

Requires DOM, not just headers → Playwright-based (pattern: reuse `Integration/services/playwright_utils.py` page acquisition, as the a11y validators do):

1. Enumerate `script[src]` and `link[rel=stylesheet][href]` with cross-origin URLs (different origin than the page).
2. For each: `integrity` attribute present? valid format (`sha256|sha384|sha512-` + base64)? `crossorigin` attribute present alongside?
3. Findings: missing integrity on cross-origin script → MAJOR "Missing Mitigation: Subresource Integrity — third-party CDN compromise executes with full page privileges"; malformed hash → MAJOR; style sheets → MINOR. Detect dynamically-injected scripts (compare DOM after load vs static HTML via one `page.content()` + response-body fetch) → NEEDS-VERIFICATION note "dynamically injected scripts bypass SRI" (observable but incomplete — say so).

### 3.4 New check: mixed content (`services/mixed_content_checker.py`, new)

Playwright network listener during load of an https URL: record any `request` with `http://` scheme (excluding localhost). Active mixed content (script/iframe/xhr) → CRITICAL "MITM exposure is deterministic"; passive (img/media) → MAJOR. Also scan static DOM attributes (`src`, `href`, `action`) for `http://` references that browsers may auto-upgrade or block — report as MISCONFIGURED with note.

### 3.5 Severity mapping (Plan 01)

Per Plan 01 §3.3 table: no observable-signal finding maps to Blocker by itself except CSP-absent + route tagged transactional/auth (tag source: Plan 03 archetypes / Plan 06 config); active mixed content → CRITICAL; most missing headers → MAJOR. Calibration is **provisional pending RESEARCH_04** (CSP effectiveness) — tables carry the marker comment.

## 4. Phased steps

1. **Phase A:** model fields + vocabulary/framing sweep + disclaimer/scope-matrix surfaces (pure string/data work, no new I/O).
2. **Phase B:** SRI checker + CLI subcommand `freya security sri <url>` (parser addition in `cli/_parser_subcommands_*`).
3. **Phase C:** mixed-content checker + CLI `freya security mixed-content <url>`; fold both into the existing `security scan` aggregate.
4. **Phase D:** Plan 01 `to_findings()` adapter + gate participation.

## 5. Testing notes

- New `Asgard_Test/tests_Freya/L0_Mocked/Security/` (subpackage currently has zero L0 tests — Plan 07): mitigation-status classification per analyzer (mocked header dicts), threat-context template coverage (every header key has one), SRI attribute validation (format matrix: valid sha384, bad algo, bad base64, missing crossorigin), mixed-content classification (active vs passive vs localhost exclusion), disclaimer/scope-matrix presence in formatter output, `security_score` API compatibility.
- SRI/mixed-content Playwright layers mocked at the page-object boundary (house pattern from Accessibility L0 tests).

## 6. Thin-research flags

- **RESEARCH_04 (pending — CSP effectiveness):** directive-level severity calibration, `strict-dynamic`/Trusted Types guidance.
- **RESEARCH_09 (pending — SRI):** hash-management workflows, coverage statistics; §3.3 implements only the deterministic observable checks DEEPTHINK_06 already justifies, leaving workflow tooling for after RESEARCH_09.
