# L8 (Performance) Coverage Plan

L8 tests measure and enforce scanner throughput and latency. Today the suite
runs but does not gate.

See `_Docs/Testing/Testing_Standards.md` for the rules.

---

## Current state

- **24 benchmarks, all green**
- No budgets defined per benchmark
- No CI enforcement; regressions silently allowed
- Coverage skewed to Heimdall (9 of ~20 services) and Forseti (6)

---

## Phase 1 — Define budgets

Write an explicit budget table. Source of truth lives in
`Asgard_Test/L8_budgets.yaml` and is read by tests via a fixture.

- [ ] Create `Asgard_Test/L8_budgets.yaml`:

      ```yaml
      heimdall:
        redos_scanner:
          single_file_ms: 50
          hundred_file_ms: 2000
        injection_detection:
          single_file_ms: 75
          hundred_file_ms: 3000
        secrets_detection:
          single_file_ms: 30
          hundred_file_ms: 1500
        cryptographic_validation:
          single_file_ms: 40
        taint_analyzer:
          single_file_ms: 200
          hundred_file_ms: 10000
        architecture_analyzer:
          full_scan_1k_loc_ms: 500
        full_heimdall_scan:
          one_k_loc_ms: 500
      forseti:
        openapi_validation_ms: 100
        asyncapi_validation_ms: 100
        protobuf_validation_ms: 75
        breaking_change_diff_ms: 200
      freya:
        wcag_scan_per_page_ms: 250
        screenshot_diff_ms: 500
      verdandi:
        slo_evaluation_per_metric_ms: 10
        anomaly_detection_per_series_ms: 50
      volundr:
        dockerfile_lint_ms: 30
        terraform_lint_ms: 100
        k8s_manifest_lint_ms: 40
      ```

- [ ] Add a `pytest` fixture `l8_budget` that reads this file and returns the
      budget for a given key.
- [ ] Refactor existing 24 benchmarks to assert against the budget, not just
      run.

---

## Phase 2 — Benchmark every public service

### Heimdall — gap of 11

Currently benchmarked (9): ReDoS, Injection, Secrets, Crypto, Architecture,
OOP, Quality, Dependencies, Security umbrella.

Add benchmarks for:

- [ ] `BugDetectionService`
- [ ] `CoverageAnalysisService`
- [ ] `IssueAggregationService`
- [ ] `PerformanceHotspotService`
- [ ] `QualityProfileService`
- [ ] `QualityGateService`
- [ ] `RatingsService`
- [ ] `CodeFixService`
- [ ] `TaintAnalyzer`
- [ ] `LogAnalysisService`
- [ ] `ComplianceReporter`

Each test file: `Asgard_Test/tests_Heimdall/L8_Performance/test_<svc>_perf.py`.

### Forseti — audit & extend

Currently 6 benchmarks. Confirm coverage for:

- [ ] OpenAPI v3 validation (large spec, ~5k lines)
- [ ] AsyncAPI validation
- [ ] Protobuf validation
- [ ] Breaking-change diff (v1 vs v2)
- [ ] Database migration lint
- [ ] GraphQL SDL validation (if supported)

### Freya

- [ ] `Asgard_Test/tests_Freya/L8_Performance/test_wcag_scanner_perf.py`
- [ ] `test_color_contrast_perf.py`
- [ ] `test_screenshot_diff_perf.py`
- [ ] `test_site_crawler_perf.py`
- [ ] `test_layout_validator_perf.py`

### Verdandi

- [ ] `Asgard_Test/tests_Verdandi/L8_Performance/test_slo_evaluation_perf.py`
- [ ] `test_anomaly_detection_perf.py`
- [ ] `test_telemetry_ingestion_perf.py`

### Volundr

- [ ] `Asgard_Test/tests_Volundr/L8_Performance/test_dockerfile_lint_perf.py`
- [ ] `test_terraform_lint_perf.py`
- [ ] `test_kubernetes_lint_perf.py`
- [ ] `test_ci_pipeline_gen_perf.py`
- [ ] `test_deployment_gate_perf.py`

---

## Phase 3 — Realistic workload benchmarks

Synthetic loops (`"x = 1\n" * 500`) are a smoke test, not a benchmark.
Add benchmarks against a fixed real corpus.

- [ ] Create `Asgard_Test/fixtures/benchmark_corpus/` with ~100 representative
      files: a mix of small (~50 LOC) utility modules, medium (~500 LOC)
      service modules, and a few large (~2k LOC) files. Include Python, JS,
      TS, YAML, Dockerfile, `.tf`, `.proto`, OpenAPI YAML.
- [ ] Bench each top-level package's scanner against this corpus:
  - [ ] `test_heimdall_full_scan_corpus_perf.py`
  - [ ] `test_forseti_full_scan_corpus_perf.py`
  - [ ] `test_freya_full_scan_corpus_perf.py`
  - [ ] `test_verdandi_full_scan_corpus_perf.py`
  - [ ] `test_volundr_full_scan_corpus_perf.py`
- [ ] Bench Asgard scanning **itself** (eat-your-own-dogfood):
  - [ ] `test_self_scan_perf.py` — Heimdall over `Asgard/` directory.

---

## Phase 4 — CI enforcement

- [ ] Add a CI workflow `.github/workflows/benchmarks.yml` (or extend existing)
      that runs nightly on a stable runner.
- [ ] Use `pytest-benchmark`'s `--benchmark-json=bench.json` plus
      `--benchmark-compare=baseline.json` and
      `--benchmark-compare-fail=mean:20%` so any >20% regression fails CI.
- [ ] Commit the `baseline.json` to `Asgard_Test/L8_baselines/` and refresh
      it monthly via a labeled PR.
- [ ] Add an explicit `--benchmark-fail` threshold per test using the budget
      fixture (a budget breach fails immediately, regardless of trend).
- [ ] Publish a benchmark trend dashboard (optional but recommended) by
      uploading `bench.json` as a CI artifact and consuming it from a small
      static-site script under `Asgard/Dashboard/`.

---

## Acceptance criteria

- [ ] Every public top-level service has at least one L8 benchmark.
- [ ] Every L8 benchmark has a documented budget in `L8_budgets.yaml`.
- [ ] CI fails if any benchmark exceeds its budget.
- [ ] CI fails if any benchmark regresses >20% vs baseline.
- [ ] Nightly run completes in under 15 minutes on the standard CI runner.

## How to track

```bash
pytest Asgard_Test/ --benchmark-only --benchmark-json=bench.json
pytest Asgard_Test/ --benchmark-only \
    --benchmark-compare=Asgard_Test/L8_baselines/baseline.json \
    --benchmark-compare-fail=mean:20%
```
