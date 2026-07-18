# 01 — Unified Compatibility Engine (Priority P0)

## Research-Backed Rationale

- **DEEPTHINK_01** establishes that a flat, unified pass/fail compatibility model across Avro, Protobuf, OpenAPI, GraphQL and JSON Schema is "logically incoherent", but that a unified engine is highly viable when built as *format-specific semantic engines projecting onto a shared, multi-dimensional taxonomy* grounded in **input contravariance / output covariance** (Liskov substitution).
- **DEEPTHINK_01 / DEEPTHINK_02** require bifurcating every finding into a **Structural tier** (will the parser crash?) and a **Semantic tier** (will business logic silently corrupt?), with default values treated as "structural bridges but semantic hazards".
- **DEEPTHINK_04** designs a **Unified Compatibility Score** (`100 − Σ(BaseSeverity × BlastRadius × TemporalPenalty × UsageProbability)`) with per-paradigm temporal penalties (REST 1.0, gRPC 1.5, Avro 5.0+) and a "Blast Radius Receipt" explanation.
- **RESEARCH_02** documents Confluent-style compatibility semantics: the two orthogonal dimensions of *directionality* (BACKWARD / FORWARD / FULL) and *temporal depth* (transitive vs non-transitive), plus Avro reader/writer resolution rules.
- **RESEARCH_03** provides the taxonomy of REST breaking changes (universally breaking vs context-dependent) and the state of the art in `oasdiff`-class semantic diffing.
- **RESEARCH_08 / RESEARCH_14** provide the Protobuf taxonomy: wire vs source vs semantic compatibility, wire-type equivalence groups, tag-number anchoring, reserved fields, RPC rename = routing break (`12 UNIMPLEMENTED`), streaming-mode changes as irrecoverable breaks.

## Current State (gap)

Every format module currently ships its **own private diff logic and its own `BreakingChange` model**:

- `Asgard/Forseti/Contracts/services/compatibility_checker_service.py` + `_compatibility_checker_helpers.py` — OpenAPI-only set-diff of paths/methods/parameters; binary `is_compatible`; severity is a free string `"error"|"warning"`; `CompatibilityLevel` is derived only from `removed_endpoints`.
- `Asgard/Forseti/Avro/services/avro_compatibility_service.py` — reader/writer promotion table exists (`_avro_compatibility_service_helpers.types_compatible`) but no FULL/transitive modes beyond a `--mode` flag, no named-type resolution, no aliases support.
- `Asgard/Forseti/Protobuf/services/protobuf_compatibility_service.py` — message/enum/service checks exist but no wire-type equivalence groups (e.g. `int32→uint64` safe-on-wire), no `reserved` enforcement, no distinction wire/source/semantic.
- `Asgard/Forseti/GraphQL/` and `Asgard/Forseti/AsyncAPI/` have **no compatibility checking at all**.
- Request vs response direction is conflated: the OpenAPI checker applies the same rules to request and response schemas, contradicting DEEPTHINK_01's contravariance/covariance split.

## Target State

One engine, `Asgard/Forseti/Compatibility/`, that all format modules feed via a canonical delta model. Format parsers stay format-specific; classification, scoring and reporting are shared.

### New module layout

```
Asgard/Forseti/Compatibility/
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── compat_models.py          # UnifiedChange, CompatReport, CompatScore, Tier enums
│   └── _compat_base_models.py    # AbstractViolation, Direction, ImpactTier
├── services/
│   ├── __init__.py
│   ├── compat_engine_service.py  # orchestrator: parse → delta → classify → score → report
│   ├── _classification_helpers.py
│   ├── _scoring_helpers.py
│   └── _transitive_helpers.py    # N-version (transitive) checking
└── utilities/
    ├── __init__.py
    └── compat_utils.py           # severity merge, dedup, path formatting
```

### Core data structures

```python
class Direction(str, Enum):
    INPUT = "input"      # contravariant: new must accept a superset (requests, RPC args, consumer reads)
    OUTPUT = "output"    # covariant: new must emit a subset (responses, events, producer writes)

class AbstractViolation(str, Enum):
    INPUT_CONTRAVARIANCE_VIOLATION = "input_contravariance_violation"
    OUTPUT_COVARIANCE_VIOLATION = "output_covariance_violation"
    OUTPUT_COVARIANCE_MODIFIED = "output_covariance_modified"   # resolved by defaults; semantic hazard
    ROUTING_BREAK = "routing_break"                             # removed path/RPC/channel
    TYPE_CONTRADICTION = "type_contradiction"

class ImpactAssessment(BaseModel):
    structural: TierVerdict      # PASS / HAZARD / FAIL  (parser survival)
    semantic: TierVerdict        # PASS / HAZARD / FAIL  (business-logic corruption, defaults, zero-values)
    empirical: TierVerdict | None  # SAFE_UNUSED / ACTIVE / UNKNOWN (telemetry hook, phase 4)

class UnifiedChange(BaseModel):
    rule_id: str                 # e.g. "OAS-RES-FIELD-REMOVED", "PROTO-FIELD-REMOVED", "AVRO-ENUM-SYMBOL-REMOVED"
    format: SchemaFormat         # openapi | asyncapi | avro | protobuf | graphql | jsonschema
    direction: Direction
    abstract_violation: AbstractViolation
    location: str                # JSONPath / proto path / channel address
    message: str
    old_value: Any | None
    new_value: Any | None
    impact: ImpactAssessment
    base_severity: int           # 0–100 per DEEPTHINK_04
    mitigation: str | None

class CompatReport(BaseModel):
    mode: CompatMode             # BACKWARD | FORWARD | FULL (+ _TRANSITIVE variants per RESEARCH_02)
    status: CompatStatus         # PASSED | CONDITIONALLY_PASSED | FAILED
    score: int                   # 0–100 unified score
    score_receipt: list[str]     # human-readable deduction lines ("Blast Radius Receipt", DEEPTHINK_04)
    changes: list[UnifiedChange]
    structural_breaks: int
    semantic_hazards: int
```

### Scoring algorithm (DEEPTHINK_04)

`score = max(0, 100 − Σ deduction(change))` where
`deduction = base_severity × temporal_penalty(format) × blast_radius`:

- `temporal_penalty`: openapi/graphql = 1.0, protobuf = 1.5, avro/asyncapi = 5.0 (poison-pill immutable logs).
- `blast_radius` (static approximation until telemetry exists): count of operations / RPCs / channels referencing the changed component, computed by walking the `$ref` / message-type dependency graph (graph centrality per DEEPTHINK_04 §1A). Cache reverse-reference index during parse: `dict[component_name, set[operation_id]]`.
- `usage_probability` is fixed at 1.0 in phase 1; phase 4 adds a `TelemetrySource` protocol (see below).

### Directional evaluation (DEEPTHINK_01)

For OpenAPI/AsyncAPI the engine evaluates each schema node twice with its role:
- Request bodies, parameters, subscribe-operations → `Direction.INPUT`: removing an accepted enum value, narrowing a type, adding a required field = `INPUT_CONTRAVARIANCE_VIOLATION` (structural FAIL).
- Response bodies, publish-operations → `Direction.OUTPUT`: removing an emitted field or adding an enum value the old consumer never saw = `OUTPUT_COVARIANCE_VIOLATION`.
- Default-value bridges (Avro defaults, proto3 zero-values): structural PASS + semantic HAZARD, never silently green (DEEPTHINK_01 §2, DEEPTHINK_02 §2 "Operational Directive" wording).

### Transitive modes (RESEARCH_02)

`_transitive_helpers.check_transitive(history: list[Schema], mode)` folds the pairwise check over an ordered version list so `BACKWARD_TRANSITIVE` etc. work against a directory of versioned schema files (`schemas/v1.avsc, v2.avsc, ...`) or a git ref range.

## Concrete Changes to Existing Modules

1. **Deduplicate `BreakingChange`**: `Contracts/models/contract_models.py`, `Avro/models/avro_models.py`, `Protobuf/models/protobuf_models.py` each define near-identical `BreakingChange`/`BreakingChangeType`. Keep them as thin aliases re-exporting `Compatibility.models.UnifiedChange` for one deprecation cycle (public API preserved), then remove.
2. **Adapters per format** (each existing service becomes a producer of `UnifiedChange`):
   - `Contracts/services/_compatibility_checker_helpers.py` → emit `UnifiedChange` with direction awareness; split `check_request_body_compatibility` (contravariant rules) from `check_responses_compatibility` (covariant rules) instead of the current shared property check.
   - `Avro/services/_avro_compatibility_service_helpers.py` → keep promotion matrix; add named-type registry (record/enum/fixed by fullname), alias resolution, and default-value semantic-hazard emission.
   - `Protobuf/services/_protobuf_compatibility_service_helpers.py` → add wire-type equivalence groups (varint / 64-bit / length-delimited / 32-bit per RESEARCH_08 §1.1), `reserved` range enforcement (removing a field without reserving its tag = HAZARD), RPC rename/streaming-mode change = `ROUTING_BREAK` FAIL (RESEARCH_14).
   - **New** `GraphQL/services/schema_diff_service.py`: field/type/enum/argument removal detection over the existing SDL parse (`GraphQL/utilities/_graphql_parse_utils.py`); removed field = input-contravariance break per DEEPTHINK_01 §1 (server stops accepting a previously valid query).
   - **New** `AsyncAPI/services/asyncapi_diff_service.py`: channel/message/payload diff reusing the JSON-schema payload walker from the OpenAPI checker; publish=OUTPUT, subscribe=INPUT.
3. **CLI**: add `forseti compat check <old> <new> --format-hint {auto,openapi,avro,proto,graphql,asyncapi} --mode {backward,forward,full}[-transitive] --min-score N` in `cli/_parser_commands.py` + a new `cli/handlers_compat.py`. Existing `contract check-compat`, `avro check-compat`, `protobuf check-compat` delegate to the engine (behavior-compatible output, plus new `score` field in JSON output).
4. **Exit codes** stay 0/1/2 per `Overview.md`, with `--min-score` mapping score < N → exit 1.

## Phased Steps

- **Phase 1**: Create `Compatibility/` models + scoring/classification helpers; port the OpenAPI checker onto it (highest existing coverage). Keep old output shapes via adapter properties.
- **Phase 2**: Port Avro + Protobuf; add wire-type groups, reserved handling, named-type/alias resolution, transitive mode.
- **Phase 3**: New GraphQL and AsyncAPI diff services.
- **Phase 4**: `TelemetrySource` protocol (`get_usage(location) -> UsageStats`) with a JSON-file provider (`--usage-report usage.json`) so CI can downgrade `FAILED` → `CONDITIONALLY_PASSED` for demonstrably unused elements (DEEPTHINK_04 §2, DEEPTHINK_01 §3). Include the **Confidence Index** field (telemetry window < 30 days ⇒ low confidence, DEEPTHINK_04 §4B).

## Testing Notes

- Extend `Asgard_Test/tests_Forseti/` with a `compat/` fixture corpus: pairs of (old, new) specs per format with expected `rule_id`, tier verdicts, and score bounds.
- Golden tests for the directional split: the same field removal must FAIL in a response and PASS-with-note in a request (added-optional case), mirroring DEEPTHINK_01's example report.
- Property test: score is monotonic — adding a breaking change to the delta never increases the score.
- Avro cases lifted from RESEARCH_02 semantics: removed-field-with-default = COMPATIBLE + semantic hazard warning text (DEEPTHINK_02 §2 verbatim style); int→long promotion OK backward, not forward.
- Protobuf cases from RESEARCH_14: method rename ⇒ FAIL; unary→server-streaming ⇒ FAIL; field rename ⇒ wire PASS + source/JSON HAZARD.
