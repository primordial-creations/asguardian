# L8 Performance Budget Policy

Status: ACTIVE for local runs; CI enforcement drafted but **not enabled**
(`.github/workflows/l8-perf-budgets.yml` carries `if: false` on every job —
enabling it, and deciding whether it gates merges, is Jake's call).

The draft is already hardened: `permissions: contents: read`,
`persist-credentials: false`, SHA-pinned actions, `timeout-minutes`, and
no unguarded `pip install -e` on `pull_request`. Do not flip `if: false`
without keeping that split. See `_Docs/Architecture/Security_Hardening.md`.

The ordinary CI workflow explicitly ignores both `L8_PerfBudgets` and every
`L8_Performance` directory. This is part of the disabled-state contract: L8
must not be activated accidentally by recursive test or coverage collection.
The dedicated workflow installs the declared `[l8]` extra on trusted events;
on pull requests it installs the equivalent base and L8 dependencies directly
without executing package build hooks.

## What is enforced

All budgets live in one file: `Asgard_Test/L8_budgets.yaml`.

1. **Budgeted smoke tests** — `Asgard_Test/L8_PerfBudgets/test_budget_smoke.py`
   times a representative operation per scanner against an explicit budget
   (`heimdall.*`, `forseti.*`, `verdandi.*`, `volundr.*` keys) via the
   `l8_budget` fixture.
2. **Per-suite gates on the pytest-benchmark suites** — every benchmark test
   under `Asgard_Test/tests_*/L8_Performance/` is gated by the autouse
   `l8_suite_budget_gate` fixture (`Asgard_Test/L8_PerfBudgets/enforcement.py`,
   re-exported by each directory's `conftest.py`). Budgets sit under the
   `suites:` key, keyed by module filename stem, and are compared against the
   **fastest** observed round (`stats.min`) — the most noise-resistant
   statistic on shared or varied hardware.
3. **Benchmark corpus + self-scan** —
   `Asgard_Test/L8_PerfBudgets/test_corpus_and_self_scan.py` scans the small
   synthetic repo in `Asgard_Test/_fixtures/l8_bench_corpus/` (`l8_corpus.*`
   budgets) and a bounded slice of Asgard's own source,
   `Asgard/Heimdall/Security/services` (~5k LOC, `self_scan.*` budgets).
   Both workloads are copied to a temp dir before scanning because
   Heimdall's default excludes deliberately skip `Asgard_Test` and
   `Asgard/Heimdall` paths.
4. **Heimdall Plan-02 CIR bar** — `Asgard_Test/L8_PerfBudgets/test_cir_50kloc.py`
   builds the CIR for a deterministic synthetic ~50k LOC Python tree.
   Plan target was <5s on 4 cores; the enforced budget
   (`heimdall.cir_build_50kloc_ms: 25000`) carries 5x headroom over that
   target. Observed on the 2026-08-13 reference run: ~0.8s single-threaded
   (after the compiled-query cache fix in
   `Asgard/Bragi/Architecture/cir/builder.py`).

## Budget-setting policy

- **Headroom >= 5x**: every budget is at least 5x the *maximum* per-test
  timing observed on the reference run, then rounded up to a coarse figure
  (e.g. 295ms observed -> 3000ms budget). Budgets exist to catch
  order-of-magnitude regressions — accidental O(n^2), pathological regex,
  unbounded rescans — never micro-variance.
- **Reference observations are recorded** as comments next to the `suites:`
  section in `L8_budgets.yaml`; update them whenever budgets are recalibrated.
- **Deterministic-ish across hardware**: gates use `stats.min` (per-suite) or
  a single wall-clock measurement against a generous budget (smoke/corpus).
  A budget failure on healthy code should be treated as a calibration bug —
  raise the budget in `L8_budgets.yaml` with a comment, don't skip the test.
- **Never trade correctness for a budget**: budgets must not motivate muting
  a real taint flow or weakening detection. If a legitimate feature makes a
  workload slower, raise the budget and note why.

## Running locally

```bash
python3 -m pytest Asgard_Test/L8_PerfBudgets -q
python3 -m pytest Asgard_Test/tests_Heimdall/L8_Performance -q  # etc.
```

## CI enablement (deferred decision)

The draft workflow runs both layers on PRs touching `Asgard/**` or the L8
files. To enable: remove the `if: false` guards, then decide whether the job
is required for merge. Until then, nothing network-facing or CI-facing
changes — L8 budgets are enforced only when the tests are run.
