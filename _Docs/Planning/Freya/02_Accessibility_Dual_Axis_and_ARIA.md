# Plan 02 — Accessibility: Dual-Axis Reporting, Component Criticality, ARIA Automatability

**Priority:** P0
**Primary research:** DEEPTHINK_01 (dual-axis architecture), DEEPTHINK_05 (ARIA automatability spectrum)
**Supporting:** DEEPTHINK_03 (epistemic disclaimers), DEEPTHINK_04 (severity mapping — Plan 01)
**Depends on:** Plan 01 (`UniversalSeverity`, `Finding.needs_review`)

---

## 1. Rationale (research-backed)

Current state (`Asgard/Freya/Accessibility/`): 20 WCAG success criteria implemented via custom JS-injected checks (`services/_wcag_checks.py`, `_wcag_checks_part2.py`, catalog in `_wcag_criteria.py`), plus contrast/keyboard/screen-reader/ARIA validators. Every finding carries exactly one `ViolationSeverity` — a single axis. Score is pass-ratio minus penalties. `ARIAValidator` (`services/aria_validator.py` + `_aria_validator_checks*.py`) returns binary pass/fail on roles, attributes, and IDREFs.

DEEPTHINK_01 identifies this as the Goodhart trap ("map vs territory") and prescribes:

1. **Dual-Axis Reporting** — Axis 1: statutory WCAG conformance (binary, per success criterion, needed for legal/VPAT use); Axis 2: heuristic usability impact (gradient: Blocker/High/Moderate/Low). A 4.3:1 contrast on a footer date and the same ratio on a submit button are the same on Axis 1 and far apart on Axis 2.
2. **Component criticality weighting** — weight findings by interactive vs static context.
3. **Spatial vs DOM analysis** — compare 2D rendered coordinates of focusable elements to DOM traversal order; erratic X/Y jumps = "High-Risk Disorientation" even when 1.3.2 technically passes.
4. **"Compliance Debt" framing** for low-impact strict violations ("Severity: Micro-barrier. Status: Strict WCAG Violation" + quick-win rationale) — never plain "low priority".
5. **ARIA-smell heuristic** — high ARIA density / conflicting overrides correlate with broken AT experiences.
6. **Legal disclaimer** distinguishing automated-litigation shielding from substantive meaningful-access claims.

DEEPTHINK_05 classifies ARIA misuse by automatability and mandates moving off binary pass/fail:

| Tier | Examples | Verdict type |
|---|---|---|
| Fully automatable | redundant roles (`<nav role="navigation">`), dangling IDREFs, cyclical `aria-owns`, missing required attrs | PASS/FAIL (deterministic) |
| Partially automatable | `role="presentation"` on focusable/structural elements, `<div role="button">` | heuristic WARNING ("syntactically valid, but…") |
| Fundamentally unautomatable | live-region salience, composite widgets (`combobox`, `tablist`, `treegrid`, `grid`) | **NEEDS_REVIEW** + manual test directive |

Note: the intended docs (`_Docs/Asgard/Freya/Accessibility-Module.md`) specify axe-core via playwright-axe. Per the Overview's ground rules we keep the custom zero-dependency engine and instead bring its *reporting semantics* up to the research spec; Plan 07 updates the intended docs.

## 2. Target state

Every accessibility finding carries: `wcag_criterion` + binary `conformance_status`, a `usability_impact` gradient, a `criticality` context weight, and a `verdict` (PASS / FAIL / WARNING / NEEDS_REVIEW). Reports render two sections: a **Conformance Ledger** (Axis 1, auditor-facing) and an **Impact Inbox** (Axis 2, developer-facing), each headed by the mandated disclaimers.

## 3. Concrete changes in `Asgard/Freya/Accessibility/`

### 3.1 Models (`models/_accessibility_enums.py`, `accessibility_models.py`, `_accessibility_report_models.py`)

New enums + optional fields (all defaulted — public API compatibility per Overview ground rules):

```python
class UsabilityImpact(str, Enum):
    BLOCKER = "blocker"; HIGH = "high"; MODERATE = "moderate"; LOW = "low"

class ComponentCriticality(str, Enum):
    PRIMARY_INTERACTIVE = "primary_interactive"  # submit buttons, nav links, form fields
    INTERACTIVE = "interactive"                  # other focusable/clickable
    CONTENT = "content"                          # headings, main text, images w/ meaning
    DECORATIVE = "decorative"                    # footers, spacers, aria-hidden trees

class CheckVerdict(str, Enum):
    PASS = "pass"; FAIL = "fail"; WARNING = "warning"; NEEDS_REVIEW = "needs_review"
```

`AccessibilityViolation` gains: `usability_impact: Optional[UsabilityImpact] = None`, `criticality: Optional[ComponentCriticality] = None`, `verdict: CheckVerdict = CheckVerdict.FAIL`, `manual_test_directive: Optional[str] = None`, `framing: Optional[str] = None` (compliance-debt text). Report models gain `needs_review_count`, `conformance_ledger: Dict[str, str]` (criterion id → "pass"/"fail"/"needs_review"/"not_checked" across all ~50 WCAG 2.1 SCs, explicitly listing the ~30 *not checked* — DEEPTHINK_03's coverage honesty).

### 3.2 New service: criticality classifier (`services/_component_criticality.py`)

JS-injected classifier used by all validators. Algorithm per element:
1. PRIMARY_INTERACTIVE if: `<button type=submit>`, elements inside `<form>` that are focusable, `<nav>` descendants that are links, elements matching `[data-testid*=submit|login|checkout|cta]`.
2. INTERACTIVE if focusable (`tabindex >= 0`, native interactive tag, `role` in interactive set) or has click handler heuristics (`onclick`, `cursor: pointer`).
3. DECORATIVE if inside `aria-hidden="true"`, `<footer>`, `role="presentation"` subtree, or zero-size/offscreen.
4. Else CONTENT.

`usability_impact` = f(base severity of the check, criticality): a two-key lookup table, e.g. contrast-fail × PRIMARY_INTERACTIVE → HIGH; contrast-fail × DECORATIVE → LOW. Table lives in `_component_criticality.py` as data.

### 3.3 New check: DOM vs visual order (`services/_focus_order_spatial.py`)

Wire into `KeyboardNavigationTester` (`services/keyboard_nav.py`):
1. Collect focusable elements in DOM/tab order; record `getBoundingClientRect()` centers.
2. Walk the sequence; score each step: expected reading flow = (Δy > line-threshold → new row) else (Δx ≥ 0). Count "regressions" (jump up a row, or leftward jump > 40% viewport width within a row).
3. Regression ratio > 0.25 (tunable) → emit finding `wcag.1.3.2.spatial` with verdict WARNING, impact HIGH, message "High-Risk Disorientation: visual focus order diverges from DOM order" (DEEPTHINK_01's spatial analysis). Never a hard FAIL — it is a heuristic.

### 3.4 ARIA validator upgrade (`services/aria_validator.py`, `_aria_validator_checks*.py`)

- Tag every existing check with its automatability tier; deterministic checks keep PASS/FAIL.
- Add **redundant-role check** (implicit-role table from HTML-AAM: ~30 entries, static dict) → verdict WARNING, framing "code smell".
- Add **non-native interactive role check** (`div/span[role=button|link|checkbox|tab...]`) → WARNING with DEEPTHINK_05's wording ("Syntactically valid, but requires custom keyboard handling and carries compatibility risk. Prefer `<button>`.").
- Add **NEEDS_REVIEW escalation**: any `aria-live` region, and any composite widget role (`combobox`, `listbox`, `tablist`, `tree`, `treegrid`, `grid`, `menu`) → verdict NEEDS_REVIEW + `manual_test_directive`, e.g. *"Found role=combobox. Manual QA: with NVDA running, verify focus containment and Up/Down arrow navigation of options."* Directive templates: static dict keyed by role.
- Add **ARIA density smell**: aria attribute count / element count over the page and per-subtree; density above threshold (start: >0.6 per element in any 50+ node subtree) → WARNING "ARIA soup: over-engineered accessibility correlates with broken AT experiences".
- `ARIAReport` gains `needs_review: List[ARIAViolation]` and per-tier counts. A page with NEEDS_REVIEW items must not report "100% pass" — formatter prints "Passed: N, Failed: M, Needs Human Review: K".

### 3.5 Scoring & framing

- Axis-1 conformance status feeds the ledger; Axis-2 impact feeds Plan 01's `SeverityMapper` (BLOCKER→blocker, HIGH×interactive→critical, etc. — table in Plan 01 §3.3).
- Low-impact strict violations get `framing` text per DEEPTHINK_01 §2 (compliance debt / quick win), emitted by a small template function in `_accessibility_report_models.py`.
- Formatters (`cli/_formatters_accessibility.py`) and HTML reporter add the standing disclaimer (DEEPTHINK_01 §3 / DEEPTHINK_03): *"Automated scans evaluate machine-readable syntax (~20–30% of WCAG criteria). A passing score reduces exposure to automated compliance litigation; it does not guarantee meaningful access. Manual screen-reader testing is required."*

## 4. Phased steps

1. **Phase A:** enums + optional model fields + conformance ledger (no check changes; ledger derives from existing results).
2. **Phase B:** criticality classifier + impact lookup; wire into contrast, WCAG, keyboard, screen-reader checks.
3. **Phase C:** ARIA tiering — new checks, NEEDS_REVIEW verdicts, directives, density smell.
4. **Phase D:** spatial focus-order check.
5. **Phase E:** formatter/report surfaces (dual sections, disclaimers, framing text); Plan 01 mapper hookup.

## 5. Testing notes

- Extend `Asgard_Test/tests_Freya/L0_Mocked/Accessibility/`: criticality classifier (fixture DOM snippets → expected class), impact lookup table completeness (every severity×criticality pair maps), redundant-role table, NEEDS_REVIEW escalation per composite role, directive text presence, spatial-order algorithm on synthetic coordinate lists (pure function — test without Playwright), ledger includes not-checked criteria.
- Regression guard: existing ~1,000 L0 accessibility tests must pass unmodified except where they assert absence of new optional fields.

## 6. Thin-research flags

- **RESEARCH_01 (pending — empirical a11y tool coverage):** the "~20–30% of WCAG" disclaimer figure and the rule-catalog sizing (should Freya grow from 20 toward axe-core's ~90 rules?) must be recalibrated when it lands.
- **Support-matrix warnings** (DEEPTHINK_05's "CanIUse model", a11ysupport.io data) are deferred: no completed research supplies the compatibility dataset. Plans leave a `support_notes: Optional[str]` field on ARIA violations as the future hook.
- LLM-based semantic alt-text/label evaluation (DEEPTHINK_01 "Semantic AI Evaluation") is out of scope — would break the zero-dependency posture; noted as a possible future opt-in.
