# Heimdall Upgrade Plan — Overview

**Scope:** Asgard's Heimdall module (static analysis, security scanning, quality gates, ratings, issues, profiles, reporting), plus the quality/architecture logic that currently lives in `Asgard/Bragi/`, `Asgard/Shared/`, and `Asgard/Reporting/`.

**Research base:** 30 docs in `_Docs/Research/Heimdall/Completed/` (DEEPTHINK_01–12, RESEARCH_01–18) and 13 docs in `_Docs/Research/Completed/` (tree-sitter, SOLID, architecture, cohesion/coupling, taint). Every plan file cites its sources.

---

## Executive Summary

Heimdall today is a broad but shallow scanner: ~30 security sub-domains (`Asgard/Heimdall/Security/*`), a large Python quality suite (`Asgard/Bragi/Quality/`), OOP metrics, SOLID/hexagonal checks, ratings, gates, issues, and profiles. The breadth is SonarQube-class; the depth is not:

1. **Detection is predominantly regex on raw text.** `SSRF/services/ssrf_scanner.py`, `ReDoS/services/redos_scanner.py`, `_injection_patterns.py`, and most of the 30 Security sub-packages match line-level regexes. Research (DEEPTHINK_01, DEEPTHINK_07, RESEARCH_07 top-level) shows this ceiling: 40%+ FP rates on SSRF, ~40% FP on heuristic ReDoS, and no ability to distinguish `execute(f"...{CONST}")` from `execute(f"...{user_input}")`.
2. **A tree-sitter foundation exists but is unused.** `Asgard/Heimdall/treesitter/` (loader, parser pool, query runner, 10 per-language query files) is wired into exactly one consumer (`Bragi/Architecture/services/_treesitter_solid_checks.py`). The multi-language "generic" SOLID/hexagonal checks (`_generic_solid_checks.py`) still regex-match `public\s+\w+` lines.
3. **Taint analysis is intra-file, binary, and confidence-free.** `Security/TaintAnalysis/` tracks assignments through one function with a boolean sanitizer flag. There is no confidence propagation, no function summaries, no cross-file resolution, no framework stubs (DEEPTHINK_03, DEEPTHINK_05, RESEARCH_02).
4. **Scoring is linear-subtractive.** `security_models_findings.py::_calculate_security_score` does `100 − 25·crit − 10·high − 5·med − 1·low` — exactly the model DEEPTHINK_02 demonstrates is gameable, size-blind, and prone to score starvation.
5. **The quality gate is absolute, not diff-aware.** `Bragi/QualityGate/` evaluates whole-project metrics; there is no fingerprint-based new-code regression gate (DEEPTHINK_12), so adopting Heimdall on a legacy codebase blocks unrelated work.
6. **Severity semantics drift across 30 modules.** Each scanner assigns its own CRITICAL/HIGH labels with no cross-module equivalency matrix and no severity/confidence decoupling (DEEPTHINK_11).
7. **No test-context engine.** Findings in `tests/`, `conftest.py`, fixtures, and mocks are reported at production severity (DEEPTHINK_08), a top driver of alert fatigue.
8. **No evaluation harness.** There is no benchmark corpus, no precision/recall measurement, no calibration of the `confidence` field that already exists on `SecurityFinding` (DEEPTHINK_03 §5, DEEPTHINK_06).

The plans in this directory upgrade Heimdall along five axes — engine (tree-sitter), analysis depth (taint/SOLID/architecture), scoring/severity mathematics, developer-trust machinery (gates, hotspots, test context, suppressions), and measurement (benchmarks/calibration) — in phases that never break the existing CLI or test suite (Strangler-Fig dual-engine pattern, DEEPTHINK_05 top-level).

---

## Gap Analysis

| # | Area | Current state (file evidence) | Target state | Research | Plan |
|---|------|-------------------------------|--------------|----------|------|
| 1 | Parsing engine | Regex line scans everywhere; `Heimdall/treesitter/` scaffold unused except one SOLID check | Tree-sitter CST as universal front-end; single-parse-per-file; `@with_ast_fallback` dual engine; optional `[ast]` extra | DEEPTHINK_05 (top), RESEARCH_01/02/04/08 (top) | 01 |
| 2 | SOLID detection | `_solid_checks.py` (Python `ast`), `_generic_solid_checks.py` (regex), partial `_treesitter_solid_checks.py` | CIR pipeline: one `extract.scm` per language → language-agnostic `ClassInfo/MethodInfo` → pure-Python evaluators with confidence grades | DEEPTHINK_01/02 (top), RESEARCH_03/06 (top) | 02 |
| 3 | Architecture enforcement | `hexagonal_analyzer.py` glob-pattern layers from `architecture.yml`; no layer inference, no drift detection, file-level cycles only | Import-graph CSP with min/max level propagation, drift paradox detection, module-level Tarjan SCC, incremental updates | DEEPTHINK_03 (top), RESEARCH_05 (top) | 03 |
| 4 | Security taint | Intra-function AST visitor, boolean sanitizer flag, no confidence | 3-layer dispatch (regex → AST → lazy taint), Bayesian confidence propagation, flow-insensitive function summaries, k≤4 hops, framework stubs | DEEPTHINK_01/03/05, RESEARCH_02; DEEPTHINK_04 (top) | 04 |
| 5 | Cohesion/coupling | `Bragi/OOP/` Python-only LCOM/CBO/RFC via `ast` | LCOM4 (graph components incl. method-call edges), heuristic cross-file CBO/Ca/Ce via global symbol index, multi-language via CIR | RESEARCH_06 (top), DEEPTHINK_02 (top) | 05 |
| 6 | Security scoring | Linear `100−25c−10h−5m−1l`, floor 0 | Multiplicative decay `100·0.4^C·0.8^H·0.9^M_eff·0.95^L_eff` with size normalization (√LOC/1000) on MED/LOW only and per-category 0.8-exponent soft caps | DEEPTHINK_02, RESEARCH_13 | 06 |
| 7 | Severity normalization | Each of ~30 modules picks its own labels | Central Normalization Engine, universal CIA-impact criteria, cross-module equivalency matrix, `Priority = Impact × Confidence × Context` | DEEPTHINK_11 | 06 |
| 8 | Domain scanners (SSRF, ReDoS, secrets, crypto, deserialization, auth, access, TOCTOU, container, TLS, supply chain, sensitive data) | Regex pattern tables per language | Per-domain upgrade recipes: SSRF backward slicing + host-control heuristic; ReDoS Glushkov-NFA EDA/IDA; secrets dummy-filter + semantic context; crypto `usedforsecurity` context; etc. | DEEPTHINK_07/08/09, RESEARCH_03–12, 14–18 | 07 |
| 9 | Hotspots & test context | `Hotspots/` category list exists; no test-context engine; hotspots and findings share severity space | Exception-only hotspot philosophy (6 pattern families), AST-level test-context tainting, contextual severity matrix, secrets never suppressed | DEEPTHINK_08, DEEPTHINK_10 | 08 |
| 10 | Quality gate / new code | Absolute-threshold gate; `Baseline/` exists but not fingerprint-based AST-anchored diffing | Fingerprint (rule+file+AST-node) regression gate; block only NEW HIGH/CRITICAL; structured suppression schema; zero-flakiness policy; break-glass label | DEEPTHINK_12, DEEPTHINK_06 §F-beta | 09 |
| 11 | Evaluation & calibration | None | Benchmark corpus (dual-annotated fixtures + CVE holdouts), dedup by (sink, CWE), AST bounding-box matching, reliability diagrams + isotonic regression, Brier-score CI gate for new rules | DEEPTHINK_03 §5, DEEPTHINK_06, RESEARCH_01 | 10 |

---

## Priority Index (recommended build order)

| Priority | Plan | Why first |
|----------|------|-----------|
| P0 | `01_TreeSitter_Migration.md` | Everything else (SOLID CIR, taint layer-2, domain scanners) consumes the tree-sitter front-end. Scaffold exists; needs the dual-engine decorator, single-parse pipeline, and benchmark harness. |
| P0 | `09_QualityGate_NewCode.md` | Fingerprint diff gating is the single biggest developer-trust win and is independent of engine work. Unblocks adoption on legacy codebases. |
| P1 | `06_Security_Scoring_Severity.md` | Pure-math change with huge credibility payoff; touches one model file plus a new normalization engine. Prerequisite for meaningful ratings/gates. |
| P1 | `04_Security_Taint.md` | Converts the noisiest CRITICAL findings (injection/SSRF) from regex guesses into confidence-scored flows. Depends on 01 for multi-language, but the Python `ast` upgrade can start immediately. |
| P1 | `08_Hotspots_TestContext.md` | Test-context engine + hotspot discipline slashes FP volume across every module at low cost. |
| P2 | `02_SOLID_Detection.md` | CIR-based multi-language SOLID; replaces regex `_generic_solid_checks.py`. Depends on 01. |
| P2 | `03_Architecture_Enforcement.md` | Layer-inference CSP + drift detection; upgrades `architecture.yml` schema. Depends on import extraction from 01. |
| P2 | `07_Domain_Scanner_Upgrades.md` | Per-domain precision work (SSRF, ReDoS, secrets, crypto, deserialization…). Each item is independently shippable behind the dual engine. |
| P3 | `05_Cohesion_Coupling.md` | LCOM4/CBO across languages via CIR; feeds SOLID SRP and ratings. |
| P3 | `10_Evaluation_Benchmarking.md` | Formal corpus + calibration. Start the fixture corpus early (each migrated rule must add benchmark cases per plan 01's acceptance gate); the statistical machinery lands last. |

## Cross-cutting invariants (apply to every plan)

- **Never break the current API/tests.** All engine swaps go through the `@with_ast_fallback` decorator (DEEPTHINK_05 top-level); the ~350-test suite must pass under both engines via a parametrized fixture.
- **Tree-sitter stays optional.** `pip install asguardian[ast]`; graceful degradation prints a single INFO line.
- **Findings carry `severity` (CIA impact) and `confidence` (probability) as orthogonal fields.** Severity is never diluted by uncertainty (DEEPTHINK_11 §2).
- **Confidence is displayed as qualitative buckets** — Certain (>0.85), Probable (0.50–0.85), Possible (0.25–0.49), Unlikely (<0.25) — never raw percentages (DEEPTHINK_03 §4).
- **Only deterministic rules may block a pipeline.** Any rule proven flaky is demoted to warn-only (DEEPTHINK_12 §4).
- **Do not modify `Asgard/` source until a plan is approved** — these documents are the specification.
