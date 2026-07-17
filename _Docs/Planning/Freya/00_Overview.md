# Freya Upgrade Plans — Overview

**Status:** Planning (2026-07-16)
**Scope:** `Asgard/Freya/` (published as part of `asguardian`), the Web/UI testing module of Asgard.
**Inputs:** Completed research `_Docs/Research/Freya/Completed/DEEPTHINK_01`–`DEEPTHINK_06`, intended-behavior docs `_Docs/Asgard/Freya/*.md`, `_Docs/Asgard/Asgard.md`, `_Docs/Asgard/Asgard Package.md`, and a full survey of the current implementation under `Asgard/Freya/`.

---

## Executive Summary

Freya today is a substantial, working implementation (~21k LOC, 10 subpackages, Playwright-async throughout, ~1,000 unit tests for the four original subpackages). It already exceeds the intended docs in *breadth* — Performance, SEO, Security, Links, Console, and Images subpackages exist that the intended docs never describe. But it falls short of the research vision in *depth and honesty of reporting*:

1. **Scoring is the anti-pattern the research explicitly forbids.** `UnifiedTester` computes `overall = mean of category scores` (`Asgard/Freya/Integration/services/unified_tester.py`). DEEPTHINK_04 calls the compensatory arithmetic mean "a dangerous anti-pattern" (the Fungibility Fallacy) and prescribes a universal severity scale + non-compensatory grade capping. This is the highest-leverage single change and touches every subpackage.

2. **Accessibility reports a single pass/fail axis.** The custom WCAG checks (`Accessibility/services/_wcag_checks*.py`, 20 criteria) emit one severity per finding. DEEPTHINK_01 prescribes a **dual-axis architecture**: statutory WCAG conformance (binary) x heuristic usability impact (gradient), plus component-criticality weighting. DEEPTHINK_05 prescribes an ARIA automatability spectrum with a third verdict — "Needs Review" — for claims automation cannot decide.

3. **Performance grading uses universal thresholds and no CI budget machinery.** `PageLoadAnalyzer` grades LCP/CLS/FID against Google's global cut-points. DEEPTHINK_02 prescribes route-archetype budgets (Document / Transactional / Rich-App), lab-proxy metrics (TBT, payload weights) instead of field metrics, and a warn-vs-fail dual-threshold gate.

4. **Reports overstate epistemic confidence.** DEEPTHINK_03 (lab vs field) and DEEPTHINK_06 (observable signals vs actual posture) both require explicit scope disclaimers, "Lab Data / Synthetic Baseline" labeling, mitigation-oriented security language ("Missing Mitigation", never "Secure"), and delta-focused visual regression framing. None of this exists in the current formatters/reporters.

5. **Engineering hygiene gaps:** the `config` CLI command is a non-functional stub; `httpx` is imported (`Security/services/security_header_scanner.py:11`, `SEO/services/robots_analyzer.py:12`) but undeclared in `pyproject.toml`; the crawler is fully sequential; five subpackages (Performance, SEO, Security, Console, Links) have no dedicated L0 unit tests; README version strings conflict (2.0.0 vs 1.0.0).

A deliberate architectural note: the intended docs (`_Docs/Asgard/Freya/Overview.md` Technology Stack) name axe-core, pixelmatch, Pillow, BeautifulSoup4, cssutils, Jinja2 — the implementation uses **none** of them, by design (pure-Python `Visual/services/image_ops.py`, custom JS-injected heuristics, hand-built HTML reports). These plans **keep the zero-heavy-dependency design** (it is a real distribution advantage for a PyPI QA tool) and instead upgrade the custom engines to the research-specified behavior. Where the intended docs and implementation diverge, the plans call for updating the intended docs rather than importing dependencies — flagged per plan.

---

## Gap Analysis: Current vs Intended vs Research Vision

| Area | Current (`Asgard/Freya/`) | Intended docs (`_Docs/Asgard/Freya/`) | Research vision (DEEPTHINK) | Gap severity |
|---|---|---|---|---|
| Unified scoring | `UnifiedTester`: per-category `100 − penalty`, overall = arithmetic mean of 3 categories; crawl exits 1 only on criticals | "Score: 85/100" style composite | DT_04: universal Blocker/Critical/Major/Minor severity across all 7+ categories, **grade capping** (any Blocker → F), persona-specific presentation (gate boolean, dev inbox, radar data, compliance ledger) | **High** |
| Accessibility reporting | Single severity enum (`ViolationSeverity`), score = pass ratio minus penalties; 20 WCAG criteria via custom JS checks; no axe-core | axe-core via playwright-axe; 13 guideline families; A/AA/AAA | DT_01: dual-axis (statutory conformance x usability impact), component criticality weighting, DOM-vs-visual-order check, "compliance debt" framing; DT_05: ARIA automatability tiers + "Needs Review" verdict + support-matrix warnings | **High** |
| ARIA validation | `ARIAValidator` binary pass/fail on roles/attrs/IDREFs | "Valid roles, required attributes, state management" | DT_05: deterministic checks (redundant roles, dangling IDREFs) = pass/fail; context-dependent = heuristic warnings; live regions & composite widgets = "Needs Review" + manual test directives | **High** |
| Performance | `PageLoadAnalyzer` grades LCP/CLS/FID vs universal Google thresholds; no budgets, no TBT | Not covered by intended docs (module didn't exist) | DT_02: route archetypes with per-archetype budgets, lab proxies (TBT, image weight, render-blocking scripts), warn/fail dual thresholds, exemption tags; DT_03: label everything "Lab Data" | **High** |
| Visual regression | 4 diff methods (pixel, SSIM, pHash, histogram) in pure Python; `BaselineManager` with `baselines.json`; no environment metadata | pixelmatch + Pillow; pixel/perceptual/structural | DT_03: baselines only valid as **controlled deltas**; fingerprint environment (OS, browser version, DPR, fonts), refuse/warn on cross-environment comparison, "structural tripwire" framing | **Medium** |
| Security | `SecurityHeaderScanner` (httpx) + `CSPAnalyzer`; no SRI, no mixed-content check; plain pass/fail wording | Not covered by intended docs | DT_06: "Missing Mitigation" vocabulary, "yes, but…" contextualized passes, executive disclaimer + scope matrix, SRI & mixed-content detection, defense-in-depth score naming | **Medium** |
| Crawler / Integration | Sequential BFS, one Chromium context, regex include/exclude, 0.5s delay, JSON+HTML report; JUnit XML exists; `config` CLI is a stub; no config file loader | Crawl w/ auth, SPA discovery, baselines, HTML reporter, CI examples | Thin direct research; DT_02/DT_04 imply gate configs and budget files; pending RESEARCH_06 (link checking at scale) will inform politeness/concurrency | **Medium** |
| Reporting honesty | No disclaimers anywhere; `github` format for some commands | HTML report with galleries | DT_03: epistemic-status labels on every report; DT_01/DT_06: legal/scope disclaimers | **Medium** |
| Tests & packaging | No L0 tests for Performance/SEO/Security/Console/Links; `httpx` undeclared; version drift | Hercules L0 layout (path is stale — tests live in `Asgard_Test/tests_Freya/`) | n/a (engineering hygiene) | **Medium** |

---

## Plan Index

| File | Theme | Priority | Primary research |
|---|---|---|---|
| `01_Unified_Severity_and_Scoring.md` | Universal severity scale, grade capping, persona presentation layers, quality gates | **P0** | DEEPTHINK_04 |
| `02_Accessibility_Dual_Axis_and_ARIA.md` | Dual-axis a11y reporting, component criticality, ARIA automatability tiers, "Needs Review" verdicts | **P0** | DEEPTHINK_01, DEEPTHINK_05 |
| `03_Performance_Context_Budgets.md` | Route archetypes, lab-proxy metrics (TBT), warn/fail budget gates, Lab-Data labeling | **P1** | DEEPTHINK_02, DEEPTHINK_03 |
| `04_Visual_Regression_Epistemics.md` | Environment fingerprinting, baseline validity, delta framing, diff-engine hardening | **P1** | DEEPTHINK_03 |
| `05_Security_Signal_Framing.md` | Mitigation vocabulary, scope matrix, SRI + mixed-content checks, contextualized passes | **P1** | DEEPTHINK_06 |
| `06_Crawler_Config_and_CI.md` | Concurrent crawling, real config system (`.freyarc`), CI gate wiring, report pipeline | **P2** | DT_02/DT_04 (gates); crawl research is thin — see below |
| `07_Testing_Packaging_Docs.md` | L0 coverage for 5 untested subpackages, `httpx` declaration, version/doc alignment | **P2** | n/a (hygiene; supports all plans) |

Recommended execution order: 01 → 02 → 03 → 05 → 04 → 06 → 07, with 07's dependency fix (httpx) done immediately as a one-line change alongside 01.

---

## Where the Completed Research Is Thin (and what Pending research will cover)

The six completed DEEPTHINK docs are *conceptual/architectural* — they define reporting philosophy, scoring math, and epistemic framing, but contain little tool-level empirical data. The ten pending docs in `_Docs/Research/Freya/Pending/` (RESEARCH_01–10, currently prompt files) will supply the empirical layer:

| Pending doc | Expected coverage | Plans that must be revisited when it lands |
|---|---|---|
| RESEARCH_01 | Empirical automated-a11y coverage (axe-core, Lighthouse, Pa11y, IBM EA) | 02 (rule catalog sizing, coverage-% claims in disclaimers) |
| RESEARCH_02 | Core Web Vitals 2024–25, FID→INP transition | 03 (INP replaces FID in models; current code still grades FID) |
| RESEARCH_03 | Visual regression tooling (Percy, Chromatic, Applitools, OSS) | 04 (diff-algorithm benchmarks, baseline workflows) |
| RESEARCH_04 | CSP effectiveness & deployment practice | 05 (CSP directive severity calibration) |
| RESEARCH_05 | Technical SEO signal-ranking correlation | (future SEO plan; SEO changes here are limited to severity mapping) |
| RESEARCH_06 | Link checking at scale | 06 (crawler politeness, retry/caching, HEAD-vs-GET strategy) |
| RESEARCH_07 | Image optimization analysis | (future Images plan; severity mapping only here) |
| RESEARCH_08 | Responsive validation methodology | (Responsive upgrades kept minimal here; revisit after) |
| RESEARCH_09 | Subresource Integrity | 05 (SRI check design details) |
| RESEARCH_10 | Console error taxonomy | (future Console plan; severity mapping only here) |

Consequently, these plans deliberately do **not** propose deep redesigns of SEO, Images, Console, or Responsive beyond wiring them into the universal severity system — the completed research does not yet support such redesigns, and each plan flags this explicitly.

Cross-cutting research in `_Docs/Research/Completed/` (DEEPTHINK_01–05 + RESEARCH_01–08 there) is Heimdall-focused (tree-sitter, SOLID, taint analysis). Its only Freya-relevant content is the quality-gate/letter-rating philosophy, which is consistent with Freya DEEPTHINK_04 and is cited in Plan 01 for cross-tool grade consistency (Heimdall already ships A–E `Ratings`).

## Ground Rules for All Plans

- No changes outside `Asgard/Freya/` except: `pyproject.toml` (dependency declaration, Plan 07) and new tests under `Asgard_Test/tests_Freya/`.
- Preserve public API backward compatibility (`Asgard/Freya/__init__.py` re-exports ~70 names); new fields on Pydantic models must be optional with defaults.
- Keep the zero-heavy-dependency posture: no Pillow/numpy/axe-core; `httpx` (already a de-facto dependency) is the only addition to declare.
- Every new report surface carries the epistemic-status language mandated by DEEPTHINK_03/06.
