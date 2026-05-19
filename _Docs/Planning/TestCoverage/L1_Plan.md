# L1 (Integration) Coverage Plan

L1 tests run a real scanner end-to-end against real temporary files. No mocks
of Asgard's own code — only the filesystem and `tmp_path` are involved.

See `_Docs/Testing/Testing_Standards.md` for the rules.

---

## Current state

- **185 L1 failures** out of the 843 total
- Each Asgard package has *some* L1 coverage but many top-level services lack
  even a single integration test
- Failures concentrated in:
  - `tests_Forseti/L1_Integration/test_contract_integration.py` (~18 failures)
  - `tests_Forseti/L1_Integration/test_database_integration.py` (~18 failures)
  - `tests_Heimdall/L1_Integration/test_oop_integration.py` (25 failures)
  - `tests_Freya/L1_Integration/` cluster (~60+ failures)
  - `tests_Freya/L1_Integration/test_unified_integration.py` (21 failures)

---

## Phase 1 — Fix the 185 L1 failures (BLOCKING)

Each failing L1 file most likely has fixtures or assertions referencing
API shapes that changed in the SOLID refactor. Methodology:

1. Run the file alone with `-x --tb=short`.
2. Identify the first failure's root cause (missing field, renamed method,
   removed class).
3. Read the current implementation in `Asgard/<Package>/...`.
4. Update the fixture/assertion — do not weaken the test.

- [ ] `Asgard_Test/tests_Forseti/L1_Integration/test_contract_integration.py`
- [ ] `Asgard_Test/tests_Forseti/L1_Integration/test_database_integration.py`
- [ ] `Asgard_Test/tests_Heimdall/L1_Integration/test_oop_integration.py`
- [ ] `Asgard_Test/tests_Freya/L1_Integration/test_unified_integration.py`
- [ ] Remaining `tests_Freya/L1_Integration/*` files (~40 failures)
- [ ] Remaining `tests_Verdandi/L1_Integration/*` if any
- [ ] Remaining `tests_Volundr/L1_Integration/*` if any

**Exit criterion**: `pytest Asgard_Test/ -k L1_Integration` returns zero
failures.

---

## Phase 2 — Cover missing integration paths

Every public top-level service in each package must have at least one L1 test
that constructs the service, runs a scan on `tmp_path`, and asserts on report
fields.

### Heimdall

Currently has L1 for: Architecture, OOP, Quality, Security (some), Dependencies.
Missing L1 coverage for:

- [ ] `Heimdall/BugDetection/` — `BugDetectionService`
- [ ] `Heimdall/Coverage/` — `CoverageAnalysisService` (lcov fixture, cobertura fixture)
- [ ] `Heimdall/Issues/` — `IssueAggregationService`
- [ ] `Heimdall/Performance/` — `PerformanceHotspotService`
- [ ] `Heimdall/Profiles/` — `QualityProfileService`
- [ ] `Heimdall/QualityGate/` — `QualityGateService`
- [ ] `Heimdall/Ratings/` — `RatingsService`
- [ ] `Heimdall/CodeFix/` — `CodeFixService`
- [ ] `Heimdall/TaintAnalysis/` — `TaintAnalyzer` end-to-end
- [ ] `Heimdall/LogAnalysis/` — `LogAnalysisService`
- [ ] `Heimdall/Container/` — container manifest scan
- [ ] `Heimdall/Infrastructure/` — IaC scan
- [ ] `Heimdall/Frontend/` — frontend artifact scan
- [ ] `Heimdall/Headers/` — security headers scan
- [ ] `Heimdall/TLS/` — TLS config scan
- [ ] `Heimdall/Access/` — access policy scan
- [ ] `Heimdall/Auth/` — auth pattern scan
- [ ] `Heimdall/Compliance/` — compliance report generation

### Forseti

Currently has L1 for: contract (failing), database (failing).
Add / fix:

- [ ] `Forseti/Compatibility/` — breaking-change detector against fixture v1/v2 specs
- [ ] `Forseti/OpenAPI/` — full OpenAPI 3 spec validation
- [ ] `Forseti/AsyncAPI/` — AsyncAPI spec validation
- [ ] `Forseti/Protobuf/` — `.proto` file validation
- [ ] `Forseti/GraphQL/` — GraphQL SDL validation (if present)
- [ ] `Forseti/Migrations/` — migration linter

### Freya

After Phase 1 rewrite, add coverage for:

- [ ] `Freya/Accessibility/` — full WCAG scan against a fixture HTML site
- [ ] `Freya/Visual/` — screenshot capture + diff (use headless browser
      fixture or pre-captured baseline images)
- [ ] `Freya/Performance/` — Lighthouse-equivalent metric run
- [ ] `Freya/Crawler/` — site crawl on a fixture static site

### Verdandi

- [ ] `Verdandi/SLO/` — SLO evaluation against synthetic time-series fixture
- [ ] `Verdandi/Anomaly/` — anomaly detection on synthetic spike fixture
- [ ] `Verdandi/Telemetry/` — telemetry ingestion + aggregation
- [ ] `Verdandi/Reporting/` — Verdandi report generation

### Volundr

- [ ] `Volundr/CI/` — CI pipeline generation for fixture repo
- [ ] `Volundr/Container/` — Dockerfile lint on fixture `Dockerfile`s
- [ ] `Volundr/Infrastructure/` — Terraform lint on fixture `.tf`
- [ ] `Volundr/Deployment/` — deployment gate evaluation
- [ ] `Volundr/Kubernetes/` — K8s manifest lint

---

## Phase 3 — End-to-end workflow tests

Per package, add at least one L1 test that exercises the **CLI entry point**
end-to-end:

- [ ] Heimdall: `asgard heimdall scan <tmp_path>` produces a report file with
      expected fields.
- [ ] Forseti: `asgard forseti validate <spec>` produces a report file.
- [ ] Freya: `asgard freya audit <fixture_site>` produces a report file.
- [ ] Verdandi: `asgard verdandi evaluate <metrics>` produces a report file.
- [ ] Volundr: `asgard volundr lint <pipeline>` produces a report file.

These are invoked via `subprocess.run([sys.executable, "-m", "Asgard", ...])`
so they exercise the entire stack including argparse, handlers, and reporting.

---

## Acceptance criteria

- [ ] **0 L1 failures** in `pytest Asgard_Test/ -k L1_Integration`
- [ ] Every public top-level service listed above has at least one passing L1
      test that writes to `tmp_path` and asserts on real report fields.
- [ ] Every package has at least one end-to-end CLI L1 test.
- [ ] L1 suite runs in under 5 minutes locally on a developer laptop.

## How to track

```bash
pytest Asgard_Test/ -k L1_Integration -v --durations=20
```
