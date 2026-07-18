# Plan 07 — Testing Coverage, Packaging Hygiene, Documentation Alignment

**Priority:** P2 (but §3.1 httpx fix is a one-liner to do immediately alongside Plan 01)
**Primary research:** n/a — engineering hygiene supporting all other plans. Epistemic-language doc updates trace to DEEPTHINK_01/03/06.

---

## 1. Rationale

Verified gaps:

1. **Undeclared dependency:** `httpx` is imported in 5 modules — `Security/services/security_header_scanner.py:11`, `Security/services/_security_header_analyzers.py:3`, `SEO/services/robots_analyzer.py:12`, `Links/services/link_validator.py:15`, `Images/services/image_optimization_scanner.py:14` — but `pyproject.toml` `dependencies` lists only `pydantic`, `pyyaml`, `playwright`. A clean `pip install asguardian` breaks five subpackages at import time.
2. **Zero L0 tests for five subpackages:** `Asgard_Test/tests_Freya/L0_Mocked/` contains only `Accessibility/`, `Integration/`, `Responsive/`, `Visual/`, `test_cli.py`, and two Images test files. **Performance, SEO, Security, Console, Links have no L0 directories at all.** (Note: Images has partial coverage — `test_image_models.py`, `test_image_optimization_scanner.py`.)
3. **Version drift:** `Asgard/Freya/README.md:319` says `Version: 1.0.0` while the README header/intended docs describe the 10-subpackage 2.x feature set; the package uses `dynamic = ["version"]` (setuptools-scm `guess-next-dev`) so any hardcoded number will drift — remove it rather than bump it.
4. **Intended docs are stale:** `_Docs/Asgard/Freya/*.md` name axe-core/playwright-axe, Pillow, pixelmatch, BeautifulSoup4, cssutils, Jinja2 — none used (deliberate zero-heavy-dependency design, per 00_Overview). Test-location section points at `Hercules/tests/L0_unit/freya/` — actual location is `Asgard_Test/tests_Freya/L0_Mocked/`. Docs also omit six shipped subpackages (Performance, SEO, Security, Console, Links, Images).

## 2. Target state

`pip install asguardian` imports every Freya subpackage cleanly; every subpackage has an L0 suite following the house mock pattern; docs describe the tool that exists, including the new epistemic-language surfaces from Plans 02–05.

## 3. Concrete changes

### 3.1 Packaging (`pyproject.toml`)

- Add `"httpx>=0.24.0"` to `[project] dependencies`. One line; ship with Plan 01's first PR.
- Audit for other silent imports while there: `grep -rhE '^(import|from) ' Asgard/Freya --include='*.py' | sort -u` diffed against declared deps (quick check found only httpx, but re-verify after Plans 03–06 land).
- Remove the hardcoded `Version: 1.0.0` line from `Asgard/Freya/README.md` (setuptools-scm owns versioning); state minimum Python (3.11 per `ruff`/`mypy` targets in pyproject).

### 3.2 L0 test coverage (`Asgard_Test/tests_Freya/L0_Mocked/`)

Create five new suites mirroring the existing house pattern (mock at the Playwright `Page` / `httpx.Client` boundary, `@pytest.mark` per module, pure-function tests unmocked):

| New dir | Priority targets |
|---|---|
| `Performance/` | `_page_load_helpers` scoring/grading math, `build_metrics`, `identify_issues` thresholds; then Plan 03's budget evaluator/archetype detector |
| `Security/` | each analyzer in `_security_header_analyzers` (mocked header dicts), CSP directive parsing + `calculate_score`, nonce/hash detection; then Plan 05 additions |
| `SEO/` | meta-tag analyzers, robots.txt parsing (`_robots_analyzer_helpers`), structured-data checks on fixture JSON-LD |
| `Console/` | message classification in `_console_capture_helpers`, severity mapping, dedup |
| `Links/` | URL normalization/classification in `_link_validator_helpers`, status-code handling matrix (mocked httpx), internal/external split |

Order: Security and Performance first (they receive the most Plan 03/05 changes — tests must exist *before* refactors), then Links, SEO, Console. Target: every public service class has at least import/construct/happy-path/error-path coverage; pure helpers get table-driven tests.

- Add a coverage floor for these five packages in CI once suites exist (start 60%, ratchet).

### 3.3 Documentation alignment (`_Docs/Asgard/Freya/*.md`, `Asgard/Freya/README.md`)

- **Technology Stack sections** (Overview, Visual-Module, Integration-Module, Accessibility-Module): replace axe-core/Pillow/pixelmatch/BeautifulSoup4/cssutils/Jinja2 rows with reality — custom JS-injected heuristic checks, pure-Python PNG codec + SSIM/pHash (`Visual/services/image_ops.py`), hand-built HTML reporter, httpx for header/link scanning — plus one sentence stating the zero-heavy-dependency design intent (from 00_Overview §Executive Summary).
- **New module docs:** add `Performance-Module.md`, `Security-Module.md`, `SEO-Module.md`, `Console-Module.md`, `Links-Module.md`, `Images-Module.md` stubs (structure, services, CLI, models — same template as existing module docs). Keep them short until pending RESEARCH_05/07/10 justify deeper content.
- **Test-location fix:** Overview's Testing section → `Asgard_Test/tests_Freya/` layout (L0_Mocked/L1_Integration/L3_Contract/L8_Performance/L14_Industry) and current pytest invocations.
- **Epistemic language:** docs for Accessibility, Performance, Visual, Security modules gain the standing disclaimers introduced by Plans 02/03/04/05 (lab-data label, ~20-30% WCAG coverage note pending RESEARCH_01 calibration, tripwire framing, defense-in-depth wording) so docs and tool output can't drift apart — quote the constants from code where practical.
- **CLI docs:** document `config init/show/validate` (Plan 06), new security subcommands (Plan 05), gate flags/exit codes (0/1/2 semantics).

### 3.4 Cross-plan consistency checks (do last)

- Grep the tree for remaining "overall score is the average" claims (README quick-start, `html_reporter` template text) after Plan 01 lands.
- Confirm `Asgard/Freya/__init__.py` re-exports (~70 names) unchanged plus new public models (`UniversalSeverity`, `GradedScore`, `FreyaConfig`, `EnvironmentFingerprint`) — additive only.

## 4. Phased steps

1. **Phase A (immediate):** httpx declaration + README version line removal.
2. **Phase B:** Security + Performance L0 suites (pre-refactor safety net for Plans 03/05).
3. **Phase C:** Links, SEO, Console L0 suites.
4. **Phase D:** doc realignment (tech stack, test paths, new module stubs).
5. **Phase E:** epistemic-language doc sync + consistency sweep, after Plans 02–05 merge.

## 5. Testing notes

This plan *is* testing; meta-checks: a packaging smoke test (fresh venv, `pip install -e .`, `python -c "import Asgard.Freya.Security, Asgard.Freya.SEO, Asgard.Freya.Links, Asgard.Freya.Console, Asgard.Freya.Performance"`) added to CI; docs checked by a link/path linter pass (manual is fine at this scale).

## 6. Thin-research flags

- Deep behavioral test scenarios for SEO/Console/Images await RESEARCH_05/10/07; the L0 suites here cover current behavior so those future redesigns start from a tested baseline.
