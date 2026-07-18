# 03 — OpenAPI Linting Depth, Completeness Scoring & Static Security (Priority P1)

## Research-Backed Rationale

- **RESEARCH_01** sets the competitive bar: Spectral ~64 rules, Vacuum ~88 with native OWASP category, Redocly with granular config, IBM with business-impact scoring. Forseti's current OpenAPI checker implements roughly a dozen structural checks — far below every benchmarked tool.
- **DEEPTHINK_08** defines completeness as a **multi-dimensional capability matrix** across four vectors — Experiential (descriptions/examples), Schema Precision (bounds/formats/additionalProperties), Operational (4xx/5xx, RFC-7807, auth, rate limits, pagination), Structural — surfaced as a vector score + **gated maturity tiers** (Basic/Standard/Comprehensive), never a single composite number. It also gives anti-gaming heuristics: stop-word filter ("TODO"), tautology penalty via Levenshtein distance between property name and description, length/verb minimums, and *examples must validate against their own schema*.
- **RESEARCH_09** (OASQuali, APIs.guru corpora) confirms the empirical prevalence of missing response schemas, absent security definitions and invalid examples, and ties completeness vectors to KPIs (TTFSC ↔ example validity; support tickets ↔ error completeness; SDK bugs ↔ schema precision).
- **RESEARCH_16** maps the OWASP API Security Top 10 (2023) to static detectability: API2 (auth schemes, no HTTP Basic, no API keys in URLs) = High; API3 BOPLA (`additionalProperties: false`) = High; API4 (bounds, maxItems, maxLength, pagination) = High; API1/BOLA partially (mandate UUID formats over sequential integer IDs); API8 misconfig (HTTPS-only servers) = High.
- **DEEPTHINK_06** governs semantic heuristics: protocol semantics (POST→201, GET without body), financial-float anti-pattern, lexical-to-type heuristics (`*At` ⇒ date-time, `is*` ⇒ boolean, `email` ⇒ format) must be Suggestions/Hints — "forcing the developer to lie about their API" is fatal; internal cross-schema consistency (same identifier, divergent types) is the low-FP proxy for intent.

## Current State (gap)

- `OpenAPI/services/_spec_validator_helpers.py`: required-field presence, path-parameter definition, response non-emptiness, direct self-`$ref` — and the mis-designed `check_deprecated` ERROR. No security rules, no completeness metrics, no `$ref` resolution (nested/remote refs unchecked), no examples-vs-schema validation.
- No lint categories/taxonomy, no OWASP coverage anywhere in the codebase.
- `Documentation/` module generates docs but nothing measures documentation *quality*.

## Target State

Three deliverables layered on the Rules engine (plan 02):

### A. Expanded lint ruleset (`Asgard/Forseti/OpenAPI/rules/`)

```
OpenAPI/rules/
├── __init__.py            # registers all rules
├── structure_rules.py     # ref-resolution, component orphan detection, operationId uniqueness, duplicate params
├── docs_rules.py          # descriptions, summaries, tags-defined, contact/license info
├── style_rules.py         # kebab-case paths, camelCase properties, no trailing slash, versioned basePath
├── semantics_rules.py     # POST→201, GET-no-body, 204-no-content-body, financial-float, lexical hints (HINT only)
├── security_rules.py      # OWASP set — see C
└── examples_rules.py      # every example validated against its schema via JSONSchema module
```

Structural prerequisite: a real **reference resolver** in `OpenAPI/utilities/_openapi_spec_utils.py` — build a document graph resolving local `#/components/...` pointers (cycle-safe, memoized `dict[str, node]`), with `NETWORK`-cost optional resolution for external file refs (profile-gated per DEEPTHINK_05). Every rule then operates on resolved nodes with original source paths retained for reporting.

Rule severities follow DEEPTHINK_06's three layers exactly: Compiler (structure) = ERROR; Linter (protocol/org policy) = WARNING with suppression; Pair-programmer (lexical inference) = HINT, never emitted in `ci` profile output.

### B. Completeness scoring (`OpenAPI/services/completeness_service.py`)

```python
class CompletenessVector(BaseModel):
    experiential: float   # % operations+params+leaf-properties with non-trivial descriptions; % schemas with ≥1 valid example
    precision: float      # % strings with format/pattern/length; % numbers with min/max; % arrays with maxItems; % objects with explicit additionalProperties
    operational: float    # % ops with ≥1 4xx and ≥1 5xx; unified error schema detection (RFC 7807); auth documented; pagination params on list ops
    structural: float     # parse success, zero broken refs, required OAS fields

class MaturityTier(str, Enum):
    NONE = "none"; BASIC = "basic"; STANDARD = "standard"; COMPREHENSIVE = "comprehensive"
```

Tier gates (DEEPTHINK_08 §3): BASIC = structural 100% ∧ experiential > 60% ∧ auth documented; STANDARD = BASIC ∧ experiential > 85% ∧ all examples validate ∧ error coverage > 80%; COMPREHENSIVE = STANDARD ∧ precision > 90% ∧ unified error schema ∧ rate limits documented.

Description-quality algorithm (deterministic, DEEPTHINK_08 §2):
1. reject stop-words {TODO, TBD, fixme, n/a, test};
2. tautology check — normalized Levenshtein similarity(field name tokens, description tokens) > 0.85 ⇒ zero credit;
3. minimum 15 chars, ≥ 3 words. (Simple `difflib.SequenceMatcher` suffices; no new dependency.)

CLI: `forseti openapi completeness <spec> [--profile dx|secops] [--min-tier standard]`; `--profile secops` weights precision/operational and ignores experiential (DEEPTHINK_08 §3 context-aware profiles). Exit 1 when `--min-tier` unmet. Also fold the vector into `forseti audit` output.

### C. Static security ruleset (RESEARCH_16 mapping)

| Rule id | OWASP | Check |
|---|---|---|
| `sec.auth.scheme-defined` | API2 | global `securitySchemes` present; every operation covered by `security` or explicit opt-out suppression |
| `sec.auth.no-http-basic` | API2 | forbid `type: http, scheme: basic` |
| `sec.auth.no-apikey-in-query` | API2 | `in: query` API keys forbidden |
| `sec.transport.https-only` | API8 | all `servers[].url` schemes https (localhost exempt) |
| `sec.bopla.additional-properties` | API3 | request-body objects must set `additionalProperties: false` (WARNING; suppressible for webhook payloads per DEEPTHINK_12) |
| `sec.dos.bounded-strings` / `bounded-arrays` / `bounded-integers` | API4 | maxLength / maxItems / max on request inputs |
| `sec.dos.pagination-required` | API4 | array-returning GET ops must define limit/cursor params |
| `sec.bola.uuid-ids` | API1 | path params named `*id` with `type: integer` ⇒ WARNING recommend UUID (heuristic ⇒ never ERROR) |
| `sec.info.no-verbose-errors` | API8 | 5xx response schemas exposing stack/trace fields |

CLI: `forseti openapi security <spec>` = validate with only `category: security` rules selected (a registry predicate — no new engine code).

## Concrete Changes

1. New `OpenAPI/rules/` package registering into the plan-02 registry; `spec_validator_service.py` keeps its API, delegating to registry execution.
2. `_openapi_spec_utils.py`: `resolve_references(spec) -> ResolvedSpec` with cycle detection (visited-stack) and source-location map.
3. New `OpenAPI/services/completeness_service.py` + `_completeness_helpers.py` (leaf-walk counters, description entropy, tier gates).
4. Example validation reuses `JSONSchema.services.schema_validator_service` — OpenAPI 3.1 schemas pass through directly (full JSON Schema 2020-12 per RESEARCH_17), 3.0 schemas via the existing nullable-conversion shim in the converter helpers.
5. `cli/_parser_commands.py`: `openapi completeness`, `openapi security` sub-commands; wire into `audit`.

## Phased Steps

- **Phase 1**: reference resolver + structure/docs/style rules (parity with Spectral core ~60 rules).
- **Phase 2**: completeness vectors + tiers + CLI.
- **Phase 3**: security ruleset (Vacuum-style native OWASP — RESEARCH_01 notes this as a key differentiator).
- **Phase 4**: semantic/lexical HINT rules + AsyncAPI reuse (channels/messages walk the same JSON-schema payload rules).

## Testing Notes

- Fixture specs per tier: craft `basic.yaml`, `standard.yaml`, `comprehensive.yaml` and assert exact tier assignment; mutate one gate condition at a time and assert tier demotion (gates are lowest-common-denominator, DEEPTHINK_08).
- Description-entropy table tests: ("billingAddress", "The billing address") ⇒ 0 credit; ("billingAddress", "Postal address used on invoices; ISO country code required") ⇒ full credit.
- Security rules verified against intentionally-vulnerable fixture (basic auth, apikey-in-query, unbounded arrays, http server URL) — expect all 9 rule ids exactly once.
- Corpus regression: run over `L14_Industry` fixtures; assert no ERROR from heuristic rules and runtime < 1 s per MB of spec (Vacuum-inspired single-pass budget, RESEARCH_01).
