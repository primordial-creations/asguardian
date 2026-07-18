# 06 — Live Contract Testing, Mock Fidelity & Drift Detection (Priority P2)

## Research-Backed Rationale

- **RESEARCH_04**: contract-testing adoption sits at 17% vs 67% functional testing — the maturity gap Forseti can fill; Schemathesis-style *generative specification validation* scales better than Pact-style CDC for spec-first shops; Arazzo (workflow spec) turns static specs into executable multi-step state machines.
- **RESEARCH_09 / RESEARCH_10**: **API drift** is the systemic killer — up to 41% of APIs drift from spec within 30 days; mocks generated from drifted specs are "dangerous liars"; the mitigation loop is provider-side spec-vs-live validation (Prism proxy mode, Dredd/Schemathesis in CI).
- **DEEPTHINK_03**: decision framework spec-mocks (intent) vs recorded mocks (reality); spec mocks are *unsafe unless paired with provider-side contract testing*; "data poverty" (`"email": "string"`) breaks semantic consumer validation; recorded tapes need sanitization and TTL governance.
- **RESEARCH_10**: competitive bar for mocks — WireMock stateful scenarios (finite state machines), Prism dynamic generation + **validation proxy mode**, Microcks multi-protocol; open problems: semantically-correlated data (Luhn-valid cards, coherent addresses), auth state machines.
- **RESEARCH_15**: RESTler's producer-consumer dependency inference (POST returns id → PUT consumes id) enables stateful test sequencing from the spec alone; property-based negative testing (CATS-style) finds unhandled 5xx.

## Current State (gap)

- `MockServer/services/mock_server_generator.py` generates static Flask/FastAPI/Express stubs with `MOCK_RESPONSES` dictionaries — no statefulness, no request validation, no proxy/record mode.
- `mock_data_generator.py` produces schema-conformant randoms but exhibits exactly the "data poverty" problem (uncorrelated fields, no semantic formats beyond basic strings).
- `Contracts/services/contract_validator_service.py` compares **two spec files** — there is no capability anywhere to exercise a *live implementation* against its spec (the drift-closing loop is absent).
- No traffic capture, no Arazzo/workflow awareness.

## Target State

### A. Live contract validation (`Asgard/Forseti/LiveContract/`) — the drift closer

```
LiveContract/
├── models/  (ProbeConfig, ProbePlan, ProbeResult, DriftReport)
├── services/
│   ├── probe_planner_service.py     # spec -> ordered request plan (dependency inference)
│   ├── live_validator_service.py    # executes plan against base URL; validates responses vs spec
│   ├── _dependency_helpers.py       # RESTler-style producer/consumer graph (RESEARCH_15)
│   └── _response_check_helpers.py   # status-code presence, schema conformance (uses compiled JSONSchema, plan 05)
└── utilities/
```

Algorithm (RESEARCH_15 §producer-consumer, simplified deterministic subset):
1. Parse spec; for each operation, record produced fields (2xx response properties, esp. `*id`) and consumed parameters (path/query/body required fields).
2. Topologically order operations so producers precede consumers (`POST /users` before `GET /users/{id}`); cycle fallback = ignore edge, log.
3. Execute with a value store: extract produced values via JSONPath into `dict[param_name, value]`; inject into consumers; synthesize remaining values from schema (plan-05 generator).
4. Validate each response: undocumented status code ⇒ `drift.undocumented-status`; body fails response schema ⇒ `drift.schema-mismatch`; documented-but-never-seen elements reported as coverage stats.
5. Optional negative pass (`--negative`, CATS-style): mutate one constraint per request (wrong type, over-max, missing required) and assert 4xx-not-5xx.

CLI: `forseti contract test <spec> --base-url http://localhost:8080 [--negative] [--max-requests N] [--auth-header ...]`. Uses stdlib `urllib`/`http.client` (keeps the no-dependency posture; timeouts + no TLS verification opt-out flags). Exit 1 on any drift ERROR.

### B. Mock server upgrades (`MockServer/`)

1. **Stateful scenarios** (WireMock model, RESEARCH_10): generated servers gain an in-memory resource store keyed by path template — `POST /users` stores the payload under a generated id; `GET /users/{id}` returns it; `DELETE` removes (404 afterward). Implemented in the generated code template (`_mock_server_generator_helpers.py`), toggle `--stateful`.
2. **Validation proxy mode** (Prism model): `forseti mock proxy <spec> --upstream https://real-api` generates/runs a pass-through server that forwards requests, validates both request and live response against the spec, and logs violations as a `DriftReport` — turning any staging test run into drift telemetry (RESEARCH_10 §drift, DEEPTHINK_03 mitigation).
3. **Semantic data** (`mock_data_generator.py`): add a name→generator heuristic table consistent with DEEPTHINK_06 lexicon (`email`, `*_at`/`*Date` ⇒ ISO 8601, `phone`, `url`, `country` ⇒ ISO 3166, `currency` ⇒ ISO 4217, `card`/`pan` ⇒ Luhn-valid via checksum computation, `postcode+city` drawn from one coherent locale row). Correlated-row tables live in a small bundled dataset module (`_mock_semantic_data.py`, ~50 rows/locale). Directly addresses RESEARCH_10's "open problem" list at pragmatic depth.
4. **Example-first responses**: prefer spec `examples` over synthetic data when present (DEEPTHINK_03 hybrid: spec skeleton + curated examples), with `--synthetic` to force generation.

### C. Workflow-aware testing (Arazzo-lite) — stretch

Accept a minimal workflow YAML (`steps: [{operationId, extract: {token: $.body.access_token}, expect: {status: 201}}]`) executed by the live validator — the Arazzo direction RESEARCH_04 identifies, without committing to full spec support yet. File format documented as forward-compatible subset of Arazzo step semantics.

## Concrete Changes

1. New `LiveContract/` package (models/services/utilities per Asgard three-tier convention).
2. `MockServer/services/_mock_server_generator_helpers.py`: stateful store template blocks per framework; `mock_server_generator.py` gains `stateful: bool`, `proxy: ProxyConfig` options.
3. `MockServer/services/_mock_data_generator_helpers.py`: semantic lexicon table + Luhn + locale rows; seedable (existing `--seed` respected).
4. CLI: `contract test`, `mock proxy`, `mock generate --stateful`; `mock data` unchanged but semantically richer.
5. `Contracts/__init__.py` re-exports `LiveContractValidatorService` for the documented Python API surface.

## Phased Steps

- **Phase 1**: semantic mock data + example-first responses (no new I/O surface, immediate quality win).
- **Phase 2**: live validator with dependency-ordered probing + drift report.
- **Phase 3**: stateful mock generation; negative-testing pass.
- **Phase 4**: proxy mode; workflow-lite runner.

## Testing Notes

- Self-referential harness: generate a stateful FastAPI mock from a fixture spec, run it in-process (TestClient/threaded server), then point `forseti contract test` at it — the two features verify each other; a conformant pair must produce zero drift findings.
- Drift injection tests: serve a mutated implementation (extra field, wrong type, undocumented 500) and assert exactly the expected `drift.*` rule ids.
- Dependency-inference unit tests: petstore-style fixture asserts topological order (`POST /pets` < `GET /pets/{petId}` < `DELETE /pets/{petId}`).
- Luhn generator property test: 1000 generated PANs all pass checksum; seeded runs reproducible.
- Negative pass: mock that echoes invalid input as 200 must be flagged (`negative.expected-4xx`).
