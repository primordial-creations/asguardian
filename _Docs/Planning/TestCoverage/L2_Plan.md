# L2 (Cross-Package) Coverage Plan

L2 tests verify that multiple Asgard packages work together. They live in
`Asgard_Test/L2_CrossPackage/`. Today there are 5 files and **23 failures**.

See `_Docs/Testing/Testing_Standards.md` for the rules.

---

## Current state

- 5 L2 test files
- **23 failures**, concentrated in:
  - `L2_CrossPackage/test_freya_volundr_integration.py`
  - `L2_CrossPackage/test_full_pipeline_integration.py`
- Existing pairs covered (passing or attempted):
  - Heimdall ↔ Forseti
  - Heimdall ↔ Volundr
  - Forseti ↔ Verdandi
  - Freya ↔ Volundr (failing)
  - Full pipeline (failing)

---

## Phase 1 — Fix the 23 failures (BLOCKING)

- [ ] `Asgard_Test/L2_CrossPackage/test_freya_volundr_integration.py` — identify
      stale API references (likely Volundr CI module or Freya report shape
      changed). Rewrite fixtures.
- [ ] `Asgard_Test/L2_CrossPackage/test_full_pipeline_integration.py` — likely
      multiple stale entry points. Walk each failing assertion, map to current
      service contract.

**Exit criterion**: `pytest Asgard_Test/L2_CrossPackage/` returns zero failures.

---

## Phase 2 — Coverage matrix: every natural package pair

There are 10 unique pairs across the 5 packages. Today 4 are covered (plus
full-pipeline). The missing pairs all have natural integration points:

| Pair                  | Status   | Integration scenario                                  |
|-----------------------|----------|-------------------------------------------------------|
| Heimdall ↔ Forseti    | Covered  | Dependency scan + contract drift                      |
| Heimdall ↔ Volundr    | Covered  | Security findings gate CI pipeline                    |
| Forseti ↔ Verdandi    | Covered  | Contract violations vs SLO error budgets              |
| Freya ↔ Volundr       | Covered (failing) | Frontend audit gates deploy                  |
| **Heimdall ↔ Verdandi**   | **Missing** | Security findings feed SLO violation count       |
| **Heimdall ↔ Freya**      | **Missing** | Security scan on frontend bundle artifacts       |
| **Forseti ↔ Volundr**     | **Missing** | Contract validation in CI deployment gate        |
| **Forseti ↔ Freya**       | **Missing** | API contract drives Freya accessibility fixtures |
| **Verdandi ↔ Volundr**    | **Missing** | SLO results trigger deployment gates             |
| **Freya ↔ Verdandi**      | **Missing** | Frontend performance metrics feed SLO            |

New files to create (each must include at least one positive and one
negative scenario):

- [ ] `Asgard_Test/L2_CrossPackage/test_heimdall_verdandi_integration.py`
- [ ] `Asgard_Test/L2_CrossPackage/test_heimdall_freya_integration.py`
- [ ] `Asgard_Test/L2_CrossPackage/test_forseti_volundr_integration.py`
- [ ] `Asgard_Test/L2_CrossPackage/test_forseti_freya_integration.py`
- [ ] `Asgard_Test/L2_CrossPackage/test_verdandi_volundr_integration.py`
- [ ] `Asgard_Test/L2_CrossPackage/test_freya_verdandi_integration.py`

Each file should:

1. Use `tmp_path` to lay down a fixture project.
2. Run the first package's scanner, capture its report object.
3. Pass the report (or a derived input) into the second package.
4. Assert that the downstream behaviour reflects the upstream finding
   (e.g., CRITICAL Heimdall finding ⇒ Verdandi SLO breach recorded).

---

## Phase 3 — Real-world scenario tests

Beyond pairwise coverage, model the actual ways teams chain packages:

- [ ] **PR pipeline scenario**
      `Asgard_Test/L2_CrossPackage/test_pr_pipeline_scenario.py` —
      run Heimdall + Forseti + Freya on a fixture diff; aggregate findings;
      assert a single combined report is produced.

- [ ] **Deployment gate scenario**
      `Asgard_Test/L2_CrossPackage/test_deployment_gate_scenario.py` —
      Verdandi SLO check + Heimdall security gate + Volundr config lint must
      all pass; failing any one blocks deploy.

- [ ] **Full audit scenario**
      `Asgard_Test/L2_CrossPackage/test_full_audit_scenario.py` — run every
      package's top-level scanner on the Asgard repo itself (or a curated
      fixture corpus). Sanity-check the combined report shape.

- [ ] **Baseline + drift scenario**
      Use `Asgard/Baseline/` to capture a baseline of findings, then re-run
      after a fixture mutation and assert the new-findings-only delta is
      correctly reported.

---

## Acceptance criteria

- [ ] **0 L2 failures** in `pytest Asgard_Test/L2_CrossPackage/`
- [ ] Every package pair listed above has at least one cross-package test.
- [ ] All three real-world scenarios pass.
- [ ] L2 suite runs in under 10 minutes locally.

## How to track

```bash
pytest Asgard_Test/L2_CrossPackage/ -v --durations=10
```
