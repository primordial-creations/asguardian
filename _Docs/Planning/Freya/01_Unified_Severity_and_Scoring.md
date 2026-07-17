# Plan 01 — Unified Severity Scale, Grade Capping, and Persona Presentation

**Priority:** P0 (highest-leverage change; every other plan builds on it)
**Primary research:** `_Docs/Research/Freya/Completed/DEEPTHINK_04`
**Supporting:** DEEPTHINK_02 (warn/fail gates), cross-cutting Heimdall research (A–E `Ratings` precedent for grade-letter consistency across Asgard)

---

## 1. Rationale (research-backed)

DEEPTHINK_04 is unambiguous: *"A purely mathematical average (e.g., an 85/100 composite score) is a dangerous anti-pattern"* — the **Fungibility Fallacy**. Freya currently commits it twice:

- `Asgard/Freya/Integration/services/unified_tester.py:116` — `overall_score = (accessibility_score + visual_score + responsive_score) / 3`. Per-category scores are `100 − Σ penalty` (`_calculate_category_score`, penalties 20/10/5/2), fully compensatory.
- `Asgard/Freya/Integration/services/_crawler_report.py:36-39` — site-level report averages the averages.

Additional problems the research exposes:

- **Category coverage gap:** `TestCategory` (`Integration/models/_integration_base_models.py`) only knows ACCESSIBILITY / VISUAL / RESPONSIVE. Performance, SEO, Security, Console, Links, Images each have their own bespoke score/grade logic (e.g., `Performance/services/_page_load_helpers.py:score_to_grade`, `Security/services/csp_analyzer.py:calculate_score`) that never flow into the unified report. There is no shared severity currency.
- **Severity vocabularies diverge:** Accessibility uses `ViolationSeverity` (critical/serious/moderate/minor/info), Integration uses `TestSeverity` (critical/serious/moderate/minor), Performance/Security use grades. DEEPTHINK_04 requires one universal scale: **Blocker / Critical / Major / Minor**.
- **Gate is a hardcoded boolean on criticals only:** `cli/_handlers_integration.py:278-279` (`return 1 if has_critical else 0`). DEEPTHINK_04's CI persona needs a configurable quality gate (`FAIL IF new Blockers > 0 OR grade < B`).
- **Mental-model trap:** an 85/100 hides a fatal flaw. Research prescribes **letter grades A–F with non-compensatory score capping** (Blocker → F/≤59, Critical → D/≤69, Major → C/≤79), following SSL Labs and CWV weakest-link precedents. Heimdall already ships A–E `Ratings`; Freya adopting letter grades gives Asgard-wide consistency.

## 2. Target state

One universal severity scale and one grading function, consumed by four presentation layers:

| Persona | Surface | Data |
|---|---|---|
| CI pipeline | exit code + gate summary line | boolean from `QualityGate.evaluate()` |
| Developer | "unified inbox": findings across all categories sorted by severity → URL → selector | flat `List[Finding]` |
| Executive | capped letter grade + per-category 0–100 radar data | `GradedScore` + `category_scores` dict |
| Auditor | compliance ledger (raw per-check pass/fail matrix, no composite) | ledger section in JSON/HTML report |

## 3. Concrete changes in `Asgard/Freya/`

### 3.1 New shared subpackage `Asgard/Freya/Scoring/`

```
Asgard/Freya/Scoring/
├── __init__.py
├── models/
│   ├── __init__.py
│   └── scoring_models.py      # UniversalSeverity, QualityGrade, Finding, GradedScore, GateConfig, GateResult
└── services/
    ├── __init__.py
    ├── severity_mapper.py     # per-category mapping tables → UniversalSeverity
    ├── grade_calculator.py    # base score + capping algorithm
    └── quality_gate.py        # configurable gate evaluation
```

Models (Pydantic v2, matching house style):

```python
class UniversalSeverity(str, Enum):
    BLOCKER = "blocker"    # journey failure / legal liability / severe data risk
    CRITICAL = "critical"  # severe UX exclusion or high financial penalty
    MAJOR = "major"        # friction, sub-optimal compliance
    MINOR = "minor"        # technical debt

class QualityGrade(str, Enum):
    A = "A"; B = "B"; C = "C"; D = "D"; F = "F"

class Finding(BaseModel):
    category: str                    # "accessibility" | "performance" | ... (string, not the old 3-value enum)
    severity: UniversalSeverity
    check_id: str                    # e.g. "wcag.1.4.3", "security.csp.unsafe-inline"
    message: str
    url: Optional[str] = None
    selector: Optional[str] = None
    source_severity: Optional[str] = None   # original vocabulary, for traceability
    needs_review: bool = False              # forward-compat with Plan 02 verdicts

class GradedScore(BaseModel):
    base_score: float               # weighted mean, for sorting/trending only
    capped_score: float             # after applying caps
    grade: QualityGrade
    cap_reason: Optional[str]       # e.g. "1 blocker: security.csp.missing"
    category_scores: Dict[str, float]  # radar data
```

### 3.2 Grading algorithm (`grade_calculator.py`)

1. `base_score` = weighted mean of category scores (default equal weights; weights configurable via Plan 06 config).
2. Apply cap from highest unresolved severity: any BLOCKER → cap 59 (F); else any CRITICAL → cap 69 (D); else any MAJOR → cap 79 (C).
3. `capped_score = min(base_score, cap)`; `grade` from bands 90/80/70/60.
4. Record `cap_reason` naming the capping finding — the report must show *why* the grade is capped (DEEPTHINK_04: "the highest-severity unresolved issue dictates the ceiling").

### 3.3 Severity mapping tables (`severity_mapper.py`)

Deterministic per-category dictionaries; initial calibration (revisit per pending research, see §6):

| Category | Blocker | Critical | Major | Minor |
|---|---|---|---|---|
| Accessibility | keyboard trap, `critical` on interactive element | `critical` (static), `serious` on interactive | `serious`, `moderate` on interactive | `moderate`, `minor`, `info` |
| Security | missing CSP entirely on auth/checkout-tagged route; `unsafe-inline`+`unsafe-eval` together | missing HSTS on https; CSP wildcard script-src | any other missing header analyzers flag | informational header advice |
| Performance | — (lab data cannot prove Blocker; DEEPTHINK_03) | hard-budget breach (Plan 03) | soft-budget breach | advisory |
| Links | broken link on nav/primary CTA (Plan 02 criticality heuristic reused) | 404 on internal link | redirect chains, 4xx external | anchors, slow links |
| Visual | — | diff above hard threshold vs valid baseline | diff above soft threshold | metadata-only mismatch |
| Responsive | content unusable (overflow hides interactive el.) | touch target < 24px on interactive | touch target < 44px, viewport meta issues | spacing |
| SEO / Console / Images | — (no Blocker until RESEARCH_05/07/10 land) | page-level (noindex accident, uncaught exception) | most findings | advisory |

Mapping lives in data (dicts), not logic, so pending research can recalibrate without code churn.

### 3.4 Integration into existing services (backward-compatible)

- `UnifiedTestReport` (`Integration/models/_integration_base_models.py`): add optional fields `graded: Optional[GradedScore] = None`, `findings: List[Finding] = []`, `blocker_count: int = 0`, `major_count: int = 0`. Keep `overall_score` populated (= `capped_score`) so existing consumers keep working; docstring notes the semantics change.
- `unified_tester.py`: after collecting results, run each through `SeverityMapper`, build `Finding` list, call `GradeCalculator`. Delete-in-place the arithmetic mean at line 116 — `overall_score` becomes the capped score.
- `PageTestResult` / `SiteCrawlReport` (`_integration_crawl_models.py`): add optional `grade`, `cap_reason`, `blocker_count`. Site-level grade = **worst-link model**: grade of the site is capped by the worst page's capping severity (never an average of grades); `average_overall_score` retained but relabeled "trend indicator" in report text.
- `cli/_handlers_integration.py`: replace `return 1 if has_critical else 0` with `QualityGate.evaluate(report, gate_config)`; default gate = `fail_on: [blocker, critical]` (behavior-preserving-ish, strictly stronger). Gate config comes from CLI flags now, config file after Plan 06.
- `cli/_formatters*.py`: text/markdown formatters print `Grade: D (capped by: 1 critical — wcag.2.1.2 keyboard trap)` line above the score; HTML reporter (`html_reporter.py`) gains a radar-data JSON block (render as simple SVG polygon — no external libs, consistent with zero-dependency posture) and a "Findings Inbox" table sorted by severity.
- Standalone subpackage reports (Performance/Security/etc.) are **not** rewritten here; they gain a `to_findings()` adapter each (thin functions in `severity_mapper.py`) so `UnifiedTester` and the crawler can fold them in when those categories are enabled (crawler wiring in Plan 06).

## 4. Phased steps

1. **Phase A — Scoring subpackage** (no behavior change): models, mapper, calculator, gate + L0 tests.
2. **Phase B — UnifiedTester adoption**: findings pipeline, capped `overall_score`, new optional report fields, formatter grade line.
3. **Phase C — Crawler + CLI gate**: site-level worst-link grade, gate-driven exit codes, HTML radar/inbox.
4. **Phase D — Adapters** for the six non-unified subpackages (`to_findings()` each).

## 5. Testing notes

- L0 (`Asgard_Test/tests_Freya/L0_Mocked/Scoring/`): capping math (all four cap tiers, empty findings → A/100), mapper tables (one test per category asserting representative mappings), gate matrix (fail_on combinations), backward-compat test asserting `UnifiedTestReport` still parses old JSON (optional fields default).
- Property-style test: capped_score ≤ base_score always; grade monotonic in capped_score.
- Update existing crawler/unified L0 tests that assert mean-based `overall_score` values.

## 6. Thin-research flags

- Severity calibration for SEO (RESEARCH_05), Images (RESEARCH_07), Console (RESEARCH_10), link checking (RESEARCH_06) is provisional — tables in `severity_mapper.py` carry `# PROVISIONAL pending RESEARCH_XX` comments and must be revisited when those docs land.
- CSP directive severity calibration awaits RESEARCH_04 (Plan 05 dependency).
