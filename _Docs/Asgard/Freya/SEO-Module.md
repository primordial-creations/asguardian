# Freya SEO Module

## Overview

The SEO module performs on-page and site-level SEO analysis: meta tag
compliance (title/description/canonical/Open Graph/Twitter Card),
Schema.org structured-data validation (JSON-LD), and robots.txt/sitemap.xml
crawlability checking.

---

## Package Structure

```
Freya/SEO/
├── __init__.py
├── models/
│   ├── __init__.py
│   └── seo_models.py
└── services/
    ├── __init__.py
    ├── meta_tag_analyzer.py
    ├── _meta_tag_analyzers.py
    ├── robots_analyzer.py
    ├── _robots_analyzer_helpers.py
    ├── structured_data_validator.py
    └── _structured_data_checks.py
```

---

## Services

### MetaTagAnalyzer

Playwright-based: reads the rendered DOM's `<title>`, `<meta>`,
Open Graph, and Twitter Card tags and checks for presence, length, and
duplication issues. Runs against the rendered DOM (not raw HTML) so
JS-injected meta tags are covered.

### StructuredDataValidator

Playwright-based: extracts `<script type="application/ld+json">` blocks
from the rendered page and validates them as Schema.org structured data
using stdlib `json` parsing plus targeted per-type checks.

### RobotsAnalyzer

httpx-based (no browser): fetches and parses `/robots.txt` and any
referenced `sitemap.xml` directly as text/XML — this check does not need
a rendered page.

---

## Models

- `MetaTag`, `MetaTagReport`, `MetaTagType` — meta-tag findings
- `StructuredDataItem`, `StructuredDataReport`, `StructuredDataType` — JSON-LD findings
- `RobotDirective`, `RobotsTxtReport`, `SitemapEntry`, `SitemapReport` — crawlability findings
- `SEOIssue`, `SEOReport`, `SEOSeverity`, `SEOConfig` — aggregate report and configuration

---

## CLI Commands

```bash
freya seo audit <url>              # full SEO audit
freya seo meta <url>               # meta tag analysis only
freya seo structured-data <url>    # structured data validation
freya seo robots <url>             # robots.txt / sitemap analysis

# Options
--format [text|json|github]
```

---

## Technology

Zero heavy dependencies: **Playwright** for `MetaTagAnalyzer` and
`StructuredDataValidator` (need the rendered/hydrated DOM); **httpx**
for `RobotsAnalyzer` (static text/XML fetch, no browser needed).
robots.txt parsing is hand-rolled with `re`; sitemap.xml parsing uses
stdlib `xml.etree.ElementTree` — no external XML/sitemap library and no
BeautifulSoup4 anywhere in this module.

Epistemic note: findings here are heuristic/observable-signal checks
(tag presence, syntax validity) — they do not evaluate actual search
ranking impact, which depends on factors outside static analysis.
Severity calibration is **provisional pending RESEARCH_05**; no finding
in this category can reach Blocker (see
`Scoring/services/severity_mapper.py:NO_BLOCKER_CATEGORIES`).
