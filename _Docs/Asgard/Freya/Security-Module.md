# Freya Security Module

## Overview

The Security module checks HTTP response headers and page DOM for
observable **threat-mitigation signals**: standard security headers
(HSTS, X-Frame-Options, COOP/COEP/CORP, etc.), deep Content-Security-Policy
directive analysis, Subresource Integrity (SRI) on cross-origin scripts
and stylesheets, and mixed-content (`http://` on an `https://` page)
detection.

Per DEEPTHINK_06, external observation reliably proves the *absence* of a
defense, almost never the *effectiveness* of one — reports are framed as
**Threat Mitigation**, never "Secure"/"Vulnerable". The headline metric
is the **Frontend Defense-in-Depth Score** (field name `security_score`
kept for API compatibility), not a "security score". Every report carries
an executive disclaimer and a scope matrix stating what the tool validates
(observable signal) versus what requires DAST/manual testing (actual
posture); passing checks still surface `manual_verification` ("yes,
but…") notes where a human must confirm intent (e.g. nonce entropy).

---

## Package Structure

```
Freya/Security/
├── __init__.py
├── models/
│   ├── __init__.py
│   └── security_header_models.py
└── services/
    ├── __init__.py
    ├── security_header_scanner.py
    ├── _security_header_analyzers.py
    ├── csp_analyzer.py
    ├── _csp_analyzer_helpers.py
    ├── sri_checker.py
    ├── mixed_content_checker.py
    └── _mitigation_framing.py
```

---

## Services

### SecurityHeaderScanner

Fetches response headers for a URL (`httpx`, async) and classifies each
tracked header's mitigation status.

### CSPAnalyzer

Parses a `Content-Security-Policy` header into directives, flags
`unsafe-inline`/`unsafe-eval`/wildcard sources, detects nonce/hash/
`strict-dynamic` usage, and computes a CSP-specific score. Parsing is
string-split/regex based.

### SRIChecker

Playwright-based: enumerates cross-origin `<script src>` and
`<link rel=stylesheet href>` elements, validates the `integrity` attribute
format (`sha256|sha384|sha512-` + base64) and presence of `crossorigin`.
Detects scripts injected after initial load (dynamic injection bypasses
SRI) and reports that as an observable-but-incomplete signal.

### MixedContentChecker

Playwright-based: listens for network requests on an `https://` page and
flags any `http://` request. Active mixed content (script/iframe/xhr) is
a deterministic MITM exposure; passive (img/media) is lower severity;
static DOM `http://` references are reported separately as
misconfigured/auto-upgradable.

### _mitigation_framing

Shared vocabulary/templates: `MitigationStatus` labels, per-header
assume-breach threat-context sentences, and the executive
disclaimer/scope-matrix constants reused by every analyzer and by the
CLI/HTML formatters.

---

## Models

- `SecurityHeader`, `SecurityHeaderReport` — per-header result and aggregate report
- `SecurityHeaderSeverity`, `SecurityHeaderStatus`, `MitigationStatus` — enums
- `CSPDirective`, `CSPReport` — parsed CSP structure and analysis
- `SRIFinding`, `SRIReport` — Subresource Integrity findings
- `MixedContentFinding`, `MixedContentReport` — mixed-content findings
- `SecurityIssue`, `SecurityConfig` — issue detail and scanner configuration

---

## CLI Commands

```bash
freya security headers <url>          # security header analysis
freya security csp <url>              # deep CSP analysis
freya security sri <url>              # Subresource Integrity check
freya security mixed-content <url>    # mixed-content detection

# Options
--format [text|json|github|html]      # headers subcommand; others: text|json
--output <file>
```

`freya security headers --format html` renders a standalone HTML
threat-mitigation report (executive disclaimer, mitigation-status table
with threat-context/manual-verification notes, scope-matrix appendix) via
`Integration/services/html_reporter.py:HTMLReporter.generate_security_report`.

---

## Technology

Zero heavy dependencies: **httpx** (async) for header/robots-style fetches
in `SecurityHeaderScanner`/`CSPAnalyzer`; **Playwright** for the two
DOM-dependent checks (`SRIChecker`, `MixedContentChecker`) that need the
rendered page, not just headers. CSP directive parsing and SRI hash-format
validation use stdlib `re`/`base64`/`urllib.parse` — no dedicated CSP
parser or crypto library.

Severity calibration is **provisional pending RESEARCH_04** (CSP
effectiveness). Per Plan 05 §3.5, a security "critical" finding never
forces a site-wide Blocker on its own; a CSP-absent finding escalates to
Blocker only when the route is explicitly tagged `auth`, `checkout`, or
`transactional` (see `Scoring/services/severity_mapper.py:
escalate_security_for_route`).
