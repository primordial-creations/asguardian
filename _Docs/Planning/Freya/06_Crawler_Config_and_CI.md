# Plan 06 — Crawler Concurrency, Real Config System, CI Gate Wiring

**Priority:** P2
**Primary research:** thin — DEEPTHINK_02 (warn/fail gates, budget files) and DEEPTHINK_04 (CI persona) supply the gate design; crawl-scale research is **pending (RESEARCH_06)**. Engineering judgment fills the rest, flagged below.
**Depends on:** Plan 01 (QualityGate), Plan 03 (budget config schema), Plan 04 (env-mismatch flag)

---

## 1. Rationale

Current state (`Asgard/Freya/Integration/` + `cli/`):

- **Sequential crawl and test:** `site_crawler.py:_test_all_pages` iterates pages one-by-one with a fixed `delay_between_requests` sleep; `_crawler_discovery.crawl_site` is BFS on a single `BrowserContext`. A 30-page crawl running the full test battery takes many minutes for no architectural reason.
- **`config` CLI is a stub:** `cli/__init__.py:246-257` — `config show` prints hardcoded text; `config init` prints "Configuration file created: .freyarc" **without creating any file**. No loader exists anywhere; every run is flag-soup (see the 15-flag Zeus example in `_Docs/Asgard/Freya/Integration-Module.md`).
- **Gate is hardcoded:** exit 1 only on criticals (`cli/_handlers_integration.py:278-279`); DEEPTHINK_04's CI persona requires a declarative gate; DEEPTHINK_02 requires warn-vs-fail budgets and exemptions to live in reviewable config.
- **Unified crawl only tests 3 categories:** Performance/SEO/Security/Console/Links/Images never run during a crawl (`CrawlConfig.test_categories` only knows the 3-value enum) — the adapters from Plans 01/03/05 need a switchboard.

## 2. Target state

`.freyarc` (YAML — `pyyaml` already a declared dependency) is the single source of truth for crawl, budgets, gate, and category selection; `config init/show/validate` are real; the crawler tests pages concurrently with bounded parallelism and per-host politeness; CI exit codes come from `QualityGate`.

## 3. Concrete changes

### 3.1 Config system (`Asgard/Freya/Config/`, new subpackage)

```
Asgard/Freya/Config/
├── __init__.py
├── models/config_models.py    # FreyaConfig root model
└── services/config_loader.py  # discovery, load, validate, merge
```

`FreyaConfig` (Pydantic — validation for free) composes existing models rather than duplicating them:

```yaml
# .freyarc
wcag_level: AA
output_format: text
crawl:            # -> CrawlConfig fields (max_depth, max_pages, include/exclude, auth env-var refs, routes)
  max_depth: 2
  concurrency: 4
categories: [accessibility, visual, responsive, performance, security, links]
budgets:          # -> Plan 03 RouteBudget list, keyed by route glob
  "/docs/**": {archetype: document}
  "/checkout": {archetype: transactional}
gate:             # -> Plan 01 GateConfig
  fail_on: [blocker, critical]
  warn_on: [major]
  min_grade: C
visual:
  allow_env_mismatch: false
```

- Discovery order: `--config PATH` flag > `./.freyarc` > `./freya.yaml` > defaults. CLI flags always override file values (merge in `config_loader.py`; precedence documented in `--help`).
- Secrets: config never stores passwords — `auth.password_env: FREYA_PASSWORD` style env-var indirection only.
- `config init` writes a commented default `.freyarc` (template string constant); `config show` prints the merged effective config (source-annotated: `max_depth: 2 (from .freyarc)`); new `config validate` loads and reports Pydantic errors with line context. Replace the stub branch in `cli/__init__.py` with a real `_handlers_config.py`.

### 3.2 Crawler concurrency (`Integration/services/site_crawler.py`, `_crawler_discovery.py`, `_crawler_page_tester.py`)

- **Test phase (biggest win, lowest risk):** replace the sequential loop in `_test_all_pages` with `asyncio.Semaphore(config.concurrency)` workers over the discovered-page list; each worker opens its own `Page` from the shared authenticated context (contexts are cheap; the auth `localStorage` restore in `_crawler_page_tester` already runs per-page). Progress callback made thread-safe-ordered via a counter lock.
- **Politeness:** replace the global `delay_between_requests` sleep with a per-host token-bucket (`min_request_interval` default 500ms per host — same effective default as today, now enforced across workers). Honor `robots.txt` crawl-delay if present (parser already exists in `SEO/services/robots_analyzer.py` — reuse, don't duplicate).
- **Discovery phase:** keep BFS ordering but allow `concurrency_discovery` (default 2) sibling fetches within a depth level; dedupe via the existing `discovered_pages` dict with an `asyncio.Lock`.
- `CrawlConfig` gains `concurrency: int = 4`, `concurrency_discovery: int = 2`, `min_request_interval_ms: int = 500` (optional, defaulted — API compat). **PROVISIONAL pending RESEARCH_06** (link checking at scale: retry/backoff, HEAD-vs-GET, caching) — marked in code comments; Links subpackage politeness will merge with this machinery when that research lands.

### 3.3 Category switchboard

- Widen crawl category selection: `CrawlConfig.test_categories` accepts the new string category set (Plan 01 `Finding.category`); `_crawler_page_tester.test_page` dispatches to Performance/Security/SEO/Console/Links/Images runners via their `to_findings()` adapters (Plans 01/03/05). Default remains the current three (no surprise cost increase); `config init` template shows how to enable the rest.
- Per-page results aggregate through Plan 01's `GradeCalculator`; `SiteCrawlReport` site grade = worst-link model (Plan 01 §3.4).

### 3.4 CI wiring (`cli/_handlers_integration.py`, `html_reporter.py`, docs)

- Exit codes: `0` gate pass, `1` gate fail, `2` inconclusive (env-mismatch refusals, crawl errors > threshold) — distinct so pipelines can treat flake differently from failure.
- `--gate` off switch (`report-only` mode) for scheduled audit jobs.
- JUnit output (`ReportFormat.JUNIT` exists) gains one testcase per finding with severity as classname — consumable by GitLab/Gitea CI test panels; add `--format github` (already present for some commands) uniformly for annotations.
- Ship a working Gitea Actions example workflow in `Asgard/Freya/README.md` (this repo's forge is Gitea; keep the GitHub example from the intended docs too).

## 4. Phased steps

1. **Phase A:** Config subpackage + real `config init/show/validate` (no consumer changes yet).
2. **Phase B:** CLI handlers read merged config (flags still win) — crawl/test/security/perf commands.
3. **Phase C:** concurrent test phase + politeness bucket; benchmark on `freya_crawl_output` target site; tune default concurrency.
4. **Phase D:** discovery concurrency; category switchboard.
5. **Phase E:** gate exit codes, JUnit-per-finding, CI examples.

## 5. Testing notes

- `Asgard_Test/tests_Freya/L0_Mocked/Config/`: discovery precedence, flag-over-file merge, env-var secret indirection, invalid YAML/schema errors, `init` template round-trips through the loader.
- Crawler: politeness bucket timing (pure asyncio, fake clock), semaphore bounds (max in-flight assertion with stub `test_page`), dedupe-under-concurrency, exit-code matrix (pass/fail/inconclusive).
- L1 (`tests_Freya/L1_Integration/`): full crawl against a fixture site (existing pattern) at concurrency 1 vs 4 asserting identical page sets.

## 6. Thin-research flags

- **RESEARCH_06 (pending — link checking at scale):** retry/backoff strategy, HEAD-vs-GET, response caching, external-link etiquette — the token-bucket and concurrency defaults here are engineering placeholders to be recalibrated; `Links/services/link_validator.py` deep changes deferred entirely to that research.
- Distributed/multi-browser crawling and sitemap-seeded discovery: out of scope; note for future after RESEARCH_06.
