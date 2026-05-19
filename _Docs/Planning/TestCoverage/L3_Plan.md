# L3 (Contract / Pydantic Model Shape) Coverage Plan

L3 tests verify the public API surface — field names, types, required fields,
and validation errors — for every Pydantic model in Asgard.

See `_Docs/Testing/Testing_Standards.md` for the rules.

---

## Current state

- **218 L3 tests, 0 failures**
- Covers ~80 of the estimated 300+ public Pydantic models (~26%)
- Largest gap is older Heimdall scanners; new scanners and architecture have
  full L3 coverage as part of recent work

---

## Phase 1 — Model inventory

Generate an authoritative list of every public Pydantic model.

- [ ] Add a discovery script `_scripts/list_pydantic_models.py`:

  ```python
  import importlib, inspect, pkgutil
  import Asgard
  from pydantic import BaseModel

  def walk(pkg):
      for m in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
          try:
              mod = importlib.import_module(m.name)
          except Exception:
              continue
          for name, obj in inspect.getmembers(mod, inspect.isclass):
              if issubclass(obj, BaseModel) and obj is not BaseModel \
                 and obj.__module__ == mod.__name__:
                  print(f"{obj.__module__}.{name}")

  walk(Asgard)
  ```

- [ ] Run the script, capture output to
      `_Docs/Planning/TestCoverage/_artifacts/model_inventory.txt`.
- [ ] For each model, mark `Y` / `N` for L3 test presence. The Y/N column is
      the master checklist for Phases 2 and 3.

---

## Phase 2 — Heimdall gap

L3 coverage today covers Security (new scanners) and Architecture. The
following submodules have **no L3 tests** — each needs a `L3_Contract/` file
testing every model in that submodule:

- [ ] `Asgard_Test/tests_Heimdall/L3_Contract/test_quality_models.py`
- [ ] `Asgard_Test/tests_Heimdall/L3_Contract/test_performance_models.py`
- [ ] `Asgard_Test/tests_Heimdall/L3_Contract/test_coverage_models.py`
- [ ] `Asgard_Test/tests_Heimdall/L3_Contract/test_dependencies_models.py`
- [ ] `Asgard_Test/tests_Heimdall/L3_Contract/test_hotspots_models.py`
- [ ] `Asgard_Test/tests_Heimdall/L3_Contract/test_bug_detection_models.py`
- [ ] `Asgard_Test/tests_Heimdall/L3_Contract/test_compliance_models.py`
- [ ] `Asgard_Test/tests_Heimdall/L3_Contract/test_code_fix_models.py`
- [ ] `Asgard_Test/tests_Heimdall/L3_Contract/test_issues_models.py`
- [ ] `Asgard_Test/tests_Heimdall/L3_Contract/test_profiles_models.py`
- [ ] `Asgard_Test/tests_Heimdall/L3_Contract/test_quality_gate_models.py`
- [ ] `Asgard_Test/tests_Heimdall/L3_Contract/test_ratings_models.py`
- [ ] `Asgard_Test/tests_Heimdall/L3_Contract/test_taint_analysis_models.py`
- [ ] `Asgard_Test/tests_Heimdall/L3_Contract/test_backend_init_models.py`
- [ ] `Asgard_Test/tests_Heimdall/L3_Contract/test_headers_models.py`
- [ ] `Asgard_Test/tests_Heimdall/L3_Contract/test_tls_models.py`
- [ ] `Asgard_Test/tests_Heimdall/L3_Contract/test_access_models.py`
- [ ] `Asgard_Test/tests_Heimdall/L3_Contract/test_auth_models.py`
- [ ] `Asgard_Test/tests_Heimdall/L3_Contract/test_container_models.py`
- [ ] `Asgard_Test/tests_Heimdall/L3_Contract/test_frontend_models.py`
- [ ] `Asgard_Test/tests_Heimdall/L3_Contract/test_infrastructure_models.py`
- [ ] `Asgard_Test/tests_Heimdall/L3_Contract/test_log_analysis_models.py`

Each file follows the canonical L3 template:

```python
from pydantic import ValidationError
import pytest

class TestQualityFindingContract:
    def test_requires_message_field(self):
        with pytest.raises(ValidationError):
            QualityFinding()

    def test_accepts_valid_payload(self):
        f = QualityFinding(message="x", severity="HIGH", rule_id="Q123")
        assert f.severity == "HIGH"
        assert f.rule_id == "Q123"
```

---

## Phase 3 — Other packages

Review per-package L3 coverage against the model inventory.

### Forseti

- [ ] Confirm contract models (OpenAPI/AsyncAPI/protobuf) are L3-covered.
- [ ] Add `test_database_models.py`, `test_compatibility_models.py`,
      `test_migrations_models.py` if missing.

### Freya

- [ ] `test_accessibility_models.py` — WCAG finding, ARIA violation models
- [ ] `test_visual_models.py` — screenshot diff result models
- [ ] `test_performance_models.py` — Freya perf metric models
- [ ] `test_crawler_models.py` — crawler config & page models

### Verdandi

- [ ] `test_slo_models.py` — SLO budget, breach, target models
- [ ] `test_anomaly_models.py` — anomaly detection result models
- [ ] `test_telemetry_models.py` — metric ingestion models

### Volundr

- [ ] `test_ci_models.py` — pipeline config and finding models
- [ ] `test_container_models.py` — Dockerfile/Compose finding models
- [ ] `test_infrastructure_models.py` — Terraform/CFN finding models
- [ ] `test_deployment_models.py` — deployment gate models
- [ ] `test_kubernetes_models.py` — K8s manifest finding models

### Cross-cutting

- [ ] `Asgard_Test/tests_common/L3_Contract/test_common_models.py` —
      `Finding`, `Severity`, `ScanReport`, `Location`, etc.
- [ ] `Asgard_Test/tests_config/L3_Contract/test_config_models.py` — every
      config schema in `Asgard/config/`.
- [ ] `Asgard_Test/tests_Reporting/L3_Contract/test_reporting_models.py`
- [ ] `Asgard_Test/tests_Baseline/L3_Contract/test_baseline_models.py`

---

## Phase 4 — Contract enforcement (meta-test)

Add an introspective test that walks `Asgard` and **fails CI** if any public
`BaseModel` lacks an L3 test:

- [ ] `Asgard_Test/L3_Contract_Meta/test_every_model_has_contract.py`:

  ```python
  def test_every_public_basemodel_has_at_least_one_l3_test():
      models = discover_basemodels(Asgard)
      tested = parse_l3_test_class_names("Asgard_Test")
      missing = [m for m in models if not any(m.__name__ in t for t in tested)]
      assert not missing, f"Models without L3 tests: {missing}"
  ```

- [ ] Allowlist mechanism for genuinely-private models (`_*` prefix or
      explicit decorator).

---

## Acceptance criteria

- [ ] Every public Pydantic model has **at least 2 L3 tests** (one
      valid-construction, one missing-required-field `ValidationError`).
- [ ] The meta-test `test_every_public_basemodel_has_at_least_one_l3_test`
      passes.
- [ ] L3 suite runs in under 30 seconds (these are shape-only tests).
- [ ] 0 L3 failures.

## How to track

```bash
pytest Asgard_Test/ -k L3_Contract -v
python3 _scripts/list_pydantic_models.py | wc -l    # denominator
pytest Asgard_Test/ -k L3_Contract --collect-only | grep "test_" | wc -l
```
