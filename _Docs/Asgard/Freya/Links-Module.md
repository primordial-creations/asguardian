# Freya Links Module

## Overview

The Links module discovers every link on a rendered page and validates
each one to detect broken links (4xx/5xx), redirect chains, and
categorize link types (internal/external/anchor/mailto/tel/etc.).

---

## Package Structure

```
Freya/Links/
├── __init__.py
├── models/
│   ├── __init__.py
│   └── link_models.py
└── services/
    ├── __init__.py
    ├── link_validator.py
    └── _link_validator_helpers.py
```

---

## Services

### LinkValidator

Extracts links from the rendered DOM via Playwright (so JS-rendered
links are caught, not just static HTML), then validates each link's
status/redirect chain concurrently with `httpx` (async, via `asyncio`).
Supports a `--max-links` cap and per-link timeout to bound crawl cost on
large pages.

### _link_validator_helpers

`get_link_type` and related helpers classify each discovered URL
(internal/external/anchor/mailto/tel/javascript/etc.) using stdlib
`re`/`urllib.parse` — no external URL-classification library.

---

## Models

- `LinkResult`, `LinkStatus`, `LinkType`, `LinkSeverity` — per-link outcome and classification
- `BrokenLink` — a link that returned a 4xx/5xx or failed to resolve
- `RedirectChain` — a link that redirected one or more times before resolving
- `LinkReport`, `LinkConfig` — aggregate report and validator configuration

---

## CLI Commands

```bash
freya links validate <url>

# Options
--format [text|json|github]
--external, -e         # also check external links (default: internal only)
--max-links <n>        # default 500
--timeout <ms>         # default 10000
```

---

## Technology

Zero heavy dependencies: **Playwright** discovers links from the live,
rendered DOM; **httpx** performs the actual HTTP validation
(HEAD/GET, status codes, redirect chains), run concurrently via
`asyncio`. No BeautifulSoup4 or scrapy-style crawling library.

Epistemic note: by default only internal links are checked (external
checks are opt-in via `--external`, since they add third-party network
dependency and latency to the run). Severity calibration is
**provisional pending RESEARCH_06**.
