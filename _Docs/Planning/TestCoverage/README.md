# Asgard Test Coverage Plan — Master Index

This directory contains the multi-phase plan for getting Asgard's test suite to
100% coverage at every applicable level. Each level has its own document; this
README is the entry point and progress tracker.

> L4 (UI/E2E) and L9 (Chaos/Live) are **explicitly excluded** — Asgard is a
> static-analysis library with no UI and no live infrastructure. See
> `_Docs/Testing/Testing_Standards.md`.

---

## Current state (baseline)

| Metric                     | Value                              |
|----------------------------|------------------------------------|
| Total line coverage        | **52.72%** (28,977 missing / 61,282) |
| Tests collected            | 5,705                              |
| Tests passing              | 4,861                              |
| Tests failing              | **843**                            |
| Tests skipped / errored    | 1 skipped, 3 errors                |

### Failures by level

| Level | Failures | Notes                                                          |
|-------|----------|----------------------------------------------------------------|
| L0    | **620**  | Mostly Freya stale tests, `image_optimization_scanner`, `protobuf_validator` |
| L1    | **185**  | Forseti contract integration, Freya integration, Heimdall OOP  |
| L2    | **23**   | `test_freya_volundr_integration`, `test_full_pipeline_integration` |
| L3    | 0        | Recently added, all green                                      |
| L5    | 0        | Recently added, all green                                      |
| L8    | 0        | Separate run, all green                                        |

### Zero-coverage modules

These have **no L0 tests at all** and contribute the largest absolute gap:

- `Asgard/config/*` — 508 statements, 0%
- `Asgard/cli.py` — 61 statements, 0%
- `Asgard/_cli_handlers.py` — 61 statements, 0%
- `Asgard/_cli_help.py` — 1 statement, 0%
- `Asgard/Baseline/*` — 245 statements, 0%

---

## Goal

Reach **100% line coverage** and zero failures at every applicable level:

- L0 — Unit / mocked
- L1 — Integration
- L2 — Cross-package
- L3 — Contract (Pydantic model shape)
- L5 — Compliance (security scanner detection quality)
- L8 — Performance (with budgets defined and CI-enforced)

L4 and L9 remain out of scope.

---

## Per-level summary

| Level | Current coverage / size                              | Passing | Gap                                  | Phases | Plan                |
|-------|------------------------------------------------------|---------|--------------------------------------|--------|---------------------|
| L0    | ~52% line coverage across packages                   | ~4,000  | 620 failures + zero-coverage modules | 4      | [L0_Plan.md](./L0_Plan.md) |
| L1    | Partial — most services missing integration tests    | ~500    | 185 failures + service gaps          | 3      | [L1_Plan.md](./L1_Plan.md) |
| L2    | 5 files exist, 23 failures, 6 package pairs missing  | ~10     | 23 failures + missing pairs          | 3      | [L2_Plan.md](./L2_Plan.md) |
| L3    | 218 tests covering ~80 of ~300+ models (~26%)        | 218     | ~220 models without L3               | 4      | [L3_Plan.md](./L3_Plan.md) |
| L5    | 18 tests, only new scanners + 4 arch rules           | 18      | ~20 older scanners + non-Heimdall    | 4      | [L5_Plan.md](./L5_Plan.md) |
| L8    | 24 benchmarks, no budgets, no CI enforcement         | 24      | ~11 Heimdall + Forseti/Freya/etc.    | 4      | [L8_Plan.md](./L8_Plan.md) |

### Per-package L0 coverage

| Package    | Stmts  | Miss   | Cover% |
|------------|--------|--------|--------|
| Heimdall   | 30,019 | 13,781 | 54.1%  |
| Forseti    | 9,890  | 5,027  | 49.2%  |
| Freya      | 8,604  | 4,695  | 45.4%  |
| Volundr    | 5,076  | 2,281  | 55.1%  |
| Verdandi   | 4,459  | 1,760  | 60.5%  |
| common     | 881    | 10     | 98.9%  |
| Reporting  | 723    | 286    | 60.4%  |
| Dashboard  | 312    | 119    | 61.9%  |
| MCP        | 286    | 134    | 53.1%  |
| HooksSetup | 81     | 8      | 90.1%  |
| BackendInit| 71     | 0      | 100.0% |

---

## Sequencing

The plans are written to run **in parallel** by level, but one phase is
non-negotiable and global:

### Phase 0 — Triage failures (BLOCKING)

Before adding any new tests at any level, the existing **843 failures** must be
either fixed or quarantined. Every other phase below assumes a green baseline.
Most failures are stale fixtures referencing APIs that drifted after the SOLID
refactor — they should be fixed, not deleted.

- [ ] Triage all 620 L0 failures (see [L0_Plan.md Phase 1](./L0_Plan.md))
- [ ] Triage all 185 L1 failures (see [L1_Plan.md Phase 1](./L1_Plan.md))
- [ ] Triage all 23 L2 failures (see [L2_Plan.md Phase 1](./L2_Plan.md))

### After Phase 0 — Parallel expansion

Once the suite is green, each level's plan can be driven independently:

- L0 expansion (Phases 2-4 of L0_Plan)
- L1 expansion (Phases 2-3 of L1_Plan)
- L2 expansion (Phases 2-3 of L2_Plan)
- L3 expansion (Phases 1-4 of L3_Plan)
- L5 expansion (Phases 1-4 of L5_Plan)
- L8 expansion (Phases 1-4 of L8_Plan)

---

## How to verify progress

### Full suite

```bash
pytest Asgard_Test/ -v --cov=Asgard --cov-report=term-missing
python3 -m coverage report --format=total
```

### Per-level

```bash
pytest Asgard_Test/tests_Heimdall/L0_Mocked/ --cov=Asgard.Heimdall
pytest Asgard_Test/tests_Heimdall/L3_Contract/ -v
pytest Asgard_Test/tests_Heimdall/L5_Compliance/ -v
pytest Asgard_Test/ --benchmark-only
```

### Coverage gate (target)

```bash
pytest Asgard_Test/ --cov=Asgard --cov-fail-under=95
```

Each plan file lists its own concrete acceptance criteria. When all six
acceptance gates pass, this initiative is complete.
