# 05 — JSON Schema Core Engine, Draft Coverage & OpenAPI Conversion Fidelity (Priority P1)

## Research-Backed Rationale

- **RESEARCH_05** shows the industry standard is *compiled* validation (Ajv AOT, jsonschema-rs): interpretive tree-walking loses 50–190%+ throughput; and that draft coverage/interoperability (draft-07 vs 2020-12) is the main correctness risk. It also documents the LLM structured-output subset (no `pattern`, restricted `oneOf/allOf`, `additionalProperties: false` required) as an emerging validation target.
- **RESEARCH_17** details the Swagger 2.0 → 3.0 → 3.1 migration pitfalls: 3.1 = full JSON Schema 2020-12 superset (`nullable: true` ⇒ `type: [T, "null"]`, `exclusiveMinimum` boolean ⇒ numeric, `prefixItems`, `unevaluatedProperties`), converters achieving only ~80% baselines, and `allOf`-inheritance / circular-`$ref` failures breaking downstream codegen — plus the recommendation to treat 3.0.3 as the safe interim target.
- **DEEPTHINK_08 §A** requires that *examples validate against their own schema* — which needs a trustworthy validator underneath.
- **RESEARCH_12** notes OpenAPI 3.1 ⇔ JSON Schema harmonization as the lingua-franca pattern for cross-system contracts (extract embedded schemas, register on topics).

## Current State (gap)

- `JSONSchema/services/schema_validator_service.py` + `_schema_validator_service_helpers.py` is a hand-rolled interpreter pinned to draft-07 semantics (`JSONSchemaConfig.schema_version` defaults to draft-07). Gaps found:
  - No `$ref` resolution during validation beyond the standalone `resolve_refs` utility (no `$defs`, no anchors, no remote/file refs, no cycle safety in the validator path).
  - No 2020-12 keywords: `prefixItems`, `unevaluatedProperties`, `dependentRequired`, `dependentSchemas`, `if/then/else` unclear, `$dynamicRef` absent.
  - Format checking is a small regex set; no distinction between `format`-as-annotation (2020-12 default) vs assertion.
  - No compilation/caching: every `validate()` call re-walks the raw schema dict.
- `OpenAPI/services/_spec_converter_2_to_3_helpers.py` / `_3_to_2` exist, but there is no 3.0 ⇄ 3.1 schema-dialect conversion layer, which RESEARCH_17 flags as the highest-risk hop.
- `SchemaInferenceService` exists and is decent (formats, enums, confidence) but its output schemas are draft-07 only.

## Target State

### A. Draft-aware validation core

Keep the zero-dependency stance (the whole package uses only pydantic+yaml — verified by import scan) but restructure into a **compile-then-run** design:

```
JSONSchema/services/
├── schema_compiler_service.py    # NEW: schema dict -> CompiledSchema (closure tree)
├── _compiler_keyword_helpers.py  # keyword -> checker-factory registry, per draft dialect
├── _ref_resolver_helpers.py      # $id/$anchor/$defs registry, JSON Pointer, cycle-safe, file: refs
└── schema_validator_service.py   # existing API; now: compile (cached by schema identity) + run
```

Algorithm (RESEARCH_05 compilation model, adapted to pure Python):
1. **Resolve phase**: walk schema once; build `dict[canonical_uri, subschema]` from `$id`/`$anchor`/`$defs`; detect dialect from `$schema` (default 2020-12; honor draft-07/2019-09).
2. **Compile phase**: for each subschema, produce a list of checker closures (one per present keyword) from a per-dialect keyword registry; `$ref` compiles to a lazy thunk resolved on first call (handles cycles). Result cached in an LRU keyed by `id(schema)`/content hash.
3. **Run phase**: apply closures; collect `JSONSchemaValidationError` with `path`, `schema_path`, `constraint`, `expected` (existing model, unchanged).

Dialect differences handled in the registry, not in checkers: e.g. `items`(array-form)+`additionalItems` for draft-07 vs `prefixItems`+`items` for 2020-12; boolean vs numeric `exclusiveMinimum`. `format` runs as annotation by default in 2020-12, assertion when `check_formats=True` (existing config flag keeps meaning).

Expected outcome: correctness parity for the official JSON-Schema-Test-Suite core cases, and ~5–10x throughput on repeat validation via compilation caching (mock-data generation and completeness example-checking both call validate in loops).

### B. Schema-dialect conversion (`JSONSchema/services/dialect_converter_service.py`)

Deterministic, lossless-where-possible transforms per RESEARCH_17:
- 3.0→3.1 (draft-07-ish → 2020-12): `nullable: true` ⇒ `type: [..., "null"]`; `exclusiveMinimum: true` + `minimum: N` ⇒ `exclusiveMinimum: N`; `example` ⇒ `examples: [...]`.
- 3.1→3.0 (lossy, report each loss): `type` arrays with "null" ⇒ `nullable`; `prefixItems` ⇒ `items` array-form; `unevaluatedProperties` ⇒ **dropped with WARNING** (no 3.0 equivalent); `const` ⇒ single-value `enum`.
- Output: `ConversionResult {converted, lossy_changes: list[LossRecord]}` — surfacing loss explicitly, since RESEARCH_17's core finding is that silent conversion loss breaks SDK generation downstream.

Wire into `OpenAPI/services/spec_converter_service.py` so `forseti openapi convert --target-version 3.1` actually converts embedded schema dialects (today it only restructures the document skeleton).

### C. LLM structured-output profile (RESEARCH_05 §7) — small, high-value

`forseti jsonschema check-llm <schema> [--provider openai|anthropic|gemini]`: lints a schema against the strict structured-output subsets (all properties required, `additionalProperties: false`, no `pattern` where unsupported, bounded nesting/enum sizes). Implemented as plan-02 rules (`llm.openai.*`, `llm.anthropic.*`) — pure metadata-selected ruleset, no engine changes.

### D. Inference upgrades

- Emit 2020-12 by default (`$schema` configurable, keep draft-07 option).
- Optional `--closed` flag: emit `additionalProperties: false` when all samples agree (feeds the security posture of plan 03).

## Concrete Changes

1. New compiler/resolver services as above; `schema_validator_service.validate()` signature unchanged, adds `dialect` to the result model.
2. `_jsonschema_validation_utils.validate_schema_syntax` extended to 2020-12 keyword vocabulary and to reject keyword/dialect mismatches (e.g. `prefixItems` under draft-07 ⇒ WARNING).
3. New `dialect_converter_service.py`; converter service integration; `LossRecord` model in `jsonschema_models.py`.
4. CLI: `jsonschema validate` gains `--dialect`; new `jsonschema check-llm`; `jsonschema infer` gains `--dialect`, `--closed`.
5. `MockServer/services/mock_data_generator.py` and plan-03 example validation switch to the compiled validator (shared cache).

## Phased Steps

- **Phase 1**: ref resolver + compile/run split at existing draft-07 feature level (no behavior change, perf win).
- **Phase 2**: 2020-12 keyword registry + dialect detection + syntax-lint vocabulary.
- **Phase 3**: dialect converter + OpenAPI convert integration.
- **Phase 4**: LLM profile rules + inference dialect options.

## Testing Notes

- Vendor a curated subset (~300 cases) of the official JSON-Schema-Test-Suite for draft-07 and 2020-12 into `Asgard_Test/tests_Forseti/fixtures/jsonschema_suite/`; parametrized runner asserts pass/fail parity. This is the single highest-leverage correctness harness (RESEARCH_05 §"correctness and interoperability").
- Cycle tests: self-referencing `$defs` (linked list schema) must validate without recursion errors.
- Conversion round-trip property: 3.0 → 3.1 → 3.0 is idempotent for the lossless subset; every lossy transform yields exactly one `LossRecord`.
- Perf smoke (L8_Performance suite): 10k validations of a mid-size schema; compiled path ≥ 5x uncached interpreter baseline.
