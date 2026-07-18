# Freya Images Module

## Overview

The Images module scans a rendered page's `<img>` elements for
optimization and accessibility issues: missing alt text, oversized
images (rendered vs. natural dimensions), missing lazy-loading,
non-modern formats, missing width/height causing layout shift (CLS),
and estimated byte savings from optimization.

---

## Package Structure

```
Freya/Images/
├── __init__.py
├── models/
│   ├── __init__.py
│   └── image_models.py
└── services/
    ├── __init__.py
    ├── image_optimization_scanner.py
    ├── _image_scanner_checks.py
    ├── _image_scanner_checks_part2.py
    └── _image_scanner_report.py
```

---

## Services

### ImageOptimizationScanner

Enumerates rendered `<img>` elements via Playwright (natural vs.
displayed size, `loading` attribute, `alt` text) and fetches each image's
actual transferred size/format via `httpx` `Content-Length`/content-type
headers for savings estimates.

### _image_scanner_checks / _image_scanner_checks_part2

Per-image heuristic checks: `detect_format`, `estimate_size_savings`, and
related functions. Format detection is extension/`Content-Type`-header
based (stdlib `re`/`urllib.parse`), not real image decoding.

### _image_scanner_report

`build_report` / `calculate_score` aggregate per-image findings into an
`ImageReport` and compute an overall optimization score.

---

## Models

- `ImageInfo` — per-image DOM/network data (dimensions, format, size)
- `ImageIssue`, `ImageIssueType`, `ImageIssueSeverity` — findings
- `ImageFormat` — detected/recommended format enum
- `ImageReport`, `ImageConfig` — aggregate report and scanner configuration

---

## CLI Commands

```bash
freya images audit <url>          # full image optimization audit
freya images alt-text <url>       # alt-text check only
freya images performance <url>    # performance-only checks

# Options
--format [text|json|github]
--include-all
--oversized-threshold <n>   # performance subcommand, default 1.5
```

---

## Technology

Zero heavy dependencies: **no Pillow, no image-decoding library**.
Dimensions and rendered size come from Playwright DOM properties
(`naturalWidth`/`naturalHeight` vs. displayed box); actual transferred
file size and format come from `httpx` response headers
(`Content-Length`, `Content-Type`) rather than decoding image bytes.
Format/extension matching uses stdlib `re`.

Epistemic note: byte-savings estimates are heuristic approximations
based on format/size/dimension mismatches, not a real re-encode/measure
pass — treat them as directional, not exact. Severity calibration is
**provisional pending RESEARCH_07**; no finding in this category can
reach Blocker.
