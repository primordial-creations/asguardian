# L0 (Unit / Mocked) Coverage Plan

L0 tests cover a single function or class in isolation with all external
dependencies mocked. They are the foundation of the suite and must be both
green and comprehensive before higher levels can be trusted.

See `_Docs/Testing/Testing_Standards.md` for level definitions.

---

## Current state

- **Total coverage: ~52%** across Asgard packages
- **620 L0 failures** out of the 843 total
- Several top-level modules have **0% coverage** (no L0 tests exist at all)
- Most failures are stale fixtures referencing APIs that drifted after the
  recent SOLID refactor (commit `c435e1d`)

### Per-package L0 coverage snapshot

| Package    | Cover% | Notes                                  |
|------------|--------|----------------------------------------|
| Heimdall   | 54.1%  | Largest absolute gap (13,781 missing)  |
| Forseti    | 49.2%  | `protobuf_validator` heavily failing   |
| Freya      | 45.4%  | Worst — most of the 620 failures here  |
| Volundr    | 55.1%  | Moderate gap                           |
| Verdandi   | 60.5%  | Best of the five                       |
| config     | 0.0%   | No tests                               |
| Baseline   | 0.0%   | No tests                               |
| cli.py     | 0.0%   | No tests                               |

---

## Phase 1 — Triage existing failures (BLOCKING)

Fix the **top 15 worst-offender files** first. Each is almost certainly a stale
fixture referencing a renamed/removed API after the SOLID refactor.

For each: read the current production code, identify the new API shape, rewrite
the fixtures and assertions to match. Do **not** mass-delete.

- [ ] `Asgard_Test/L0_unit/freya/test_image_optimization_scanner.py` — 72 failures
- [ ] `Asgard_Test/tests_Freya/L0_Mocked/Integration/test_site_crawler.py` — 39
- [ ] `Asgard_Test/tests_Freya/L0_Mocked/Accessibility/test_color_contrast.py` — 34
- [ ] `Asgard_Test/tests_Freya/L0_Mocked/Accessibility/test_screen_reader.py` — 30
- [ ] `Asgard_Test/tests_Freya/L0_Mocked/Visual/test_layout_validator.py` — 29
- [ ] `Asgard_Test/tests_Freya/L0_Mocked/Accessibility/test_wcag_validator.py` — 29
- [ ] `Asgard_Test/tests_Freya/L0_Mocked/Accessibility/test_aria_validator.py` — 29
- [ ] `Asgard_Test/tests_Freya/L0_Mocked/Integration/test_baseline_manager.py` — 26
- [ ] `Asgard_Test/tests_Freya/L0_Mocked/Accessibility/test_keyboard_nav.py` — 25
- [ ] `Asgard_Test/L0_unit/forseti/test_protobuf_validator_service.py` — 25
- [ ] `Asgard_Test/tests_Freya/L0_Mocked/test_cli.py` — 24
- [ ] `Asgard_Test/tests_Freya/L0_Mocked/Visual/test_screenshot_capture.py` — 22
- [ ] `Asgard_Test/tests_Heimdall/L0_Mocked/test_new_code_period.py` — 21

That clears ~405 of the 620 failures. The remaining ~215 will be the long-tail
across smaller files — group them into batches of 10 per pass.

- [ ] Long-tail pass 1 — Freya remaining
- [ ] Long-tail pass 2 — Forseti remaining
- [ ] Long-tail pass 3 — Heimdall remaining
- [ ] Long-tail pass 4 — Verdandi/Volundr remaining

**Exit criterion**: `pytest Asgard_Test/ -k "L0 or L0_Mocked or L0_unit"` returns
zero failures.

---

## Phase 2 — Zero-coverage modules

These modules have **no L0 tests at all**. A new test file per module:

- [ ] `Asgard_Test/tests_config/L0_Mocked/test_*` covering every file under
      `Asgard/config/` (508 stmts). One test file per config submodule.
      Focus: schema loading, defaults, env-var overrides, validation errors.
- [ ] `Asgard_Test/tests_CLI/L0_Mocked/test_cli.py` for `Asgard/cli.py`
      (61 stmts). Mock the handler layer; assert argparse wiring + dispatch.
- [ ] `Asgard_Test/tests_CLI/L0_Mocked/test_cli_handlers.py` for
      `Asgard/_cli_handlers.py` (61 stmts). Mock each package's entry point;
      assert each subcommand calls the right scanner with the right config.
- [ ] `Asgard_Test/tests_CLI/L0_Mocked/test_cli_help.py` for `_cli_help.py`
      (trivial — 1 stmt, but include for completeness).
- [ ] `Asgard_Test/tests_Baseline/L0_Mocked/test_*` covering `Asgard/Baseline/`
      (245 stmts). Focus: baseline file load/save, diff computation,
      drift detection.

**Exit criterion**: every file listed above moves from 0% to ≥90% covered.

---

## Phase 3 — Per-package gap-fill

Audit each package for submodules with **<80% L0 coverage** and add tests.

### Heimdall (54.1% → target 95%)

Submodules likely under-covered (verify with `--cov-report=term-missing`):

- [ ] `Heimdall/BugDetection/` — services, detectors, rule engine
- [ ] `Heimdall/Coverage/` — coverage parsers (lcov, cobertura, jacoco)
- [ ] `Heimdall/Issues/` — issue aggregation and deduplication
- [ ] `Heimdall/Performance/` — perf hot-path analyzer
- [ ] `Heimdall/Profiles/` — quality profile loader
- [ ] `Heimdall/QualityGate/` — gate evaluation logic
- [ ] `Heimdall/Ratings/` — A-E rating calculators
- [ ] `Heimdall/CodeFix/` — fix-suggestion engine
- [ ] `Heimdall/TaintAnalysis/` — data flow analyzer
- [ ] `Heimdall/LogAnalysis/` — log pattern matcher

### Forseti (49.2% → target 95%)

- [ ] `Forseti/Contract/` — OpenAPI/AsyncAPI/protobuf validators
- [ ] `Forseti/Database/` — migration linter, schema differ
- [ ] `Forseti/Compatibility/` — breaking-change detector

### Freya (45.4% → target 95%)

- [ ] `Freya/Accessibility/` — most failures live here, rewrite after Phase 1
- [ ] `Freya/Visual/` — screenshot/layout diff engine
- [ ] `Freya/Performance/` — Lighthouse-style metric collectors
- [ ] `Freya/Integration/` — site crawler, baseline manager

### Verdandi (60.5% → target 95%)

- [ ] `Verdandi/SLO/` — SLO budget calculator
- [ ] `Verdandi/Anomaly/` — anomaly detection thresholds
- [ ] `Verdandi/Telemetry/` — metric ingestion

### Volundr (55.1% → target 95%)

- [ ] `Volundr/CI/` — pipeline generators
- [ ] `Volundr/Container/` — Dockerfile/K8s linter
- [ ] `Volundr/Infrastructure/` — Terraform/CloudFormation linter
- [ ] `Volundr/Deployment/` — deployment gate evaluator

**Exit criterion**: every named submodule reaches ≥90% line coverage.

---

## Phase 4 — Hardening

Once the floor is at 90%, add depth:

- [ ] Parametrized edge-case tests per scanner (empty input, single-line input,
      binary file, unicode, deeply nested directory, symlink loops).
- [ ] Explicit error-path tests for every `raise` statement.
- [ ] Branch coverage pass — run `pytest --cov-branch` and target uncovered
      branches.
- [ ] Property-based tests (Hypothesis) for the parsing-heavy modules
      (regex parsers, AST walkers, config schemas).
- [ ] Mutation testing pass on `common/` with `mutmut` to find weak assertions.

---

## Acceptance criteria

- [ ] **0 L0 failures** in `pytest Asgard_Test/ -k L0`
- [ ] **≥95% line coverage** for every package listed above
- [ ] **≥80% branch coverage** for every package listed above
- [ ] No file in `Asgard/` is below 80% covered
- [ ] CI runs `--cov-fail-under=95` on the L0 suite

## How to track

```bash
pytest Asgard_Test/ -k L0 --cov=Asgard --cov-report=term-missing \
    --cov-report=html:coverage_html
python3 -m coverage report --format=total
```
