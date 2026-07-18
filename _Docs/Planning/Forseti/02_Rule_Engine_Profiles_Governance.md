# 02 — Unified Rule Registry, Validation Profiles & Governance (Priority P0)

## Research-Backed Rationale

- **DEEPTHINK_05** prescribes a **Unified Rule Registry with bifurcated execution**, where every rule carries metadata on three axes — `Target` (schema vs payload), `Cost` (O(1) / O(N) / Network), `Confidence` (deterministic vs heuristic) — and **Validation Profiles** are declarative queries over that metadata plus an execution contract (budget, fail-open/fail-closed, reporter sink).
- **DEEPTHINK_02** demands **tiered immutability**: an inviolable core (parse errors, broken `$ref`s) that is never configurable, with granular *inline suppressions with mandatory reason strings* instead of global toggles, plus **baselines** for static lint and **point-in-time waivers** ("epoch severance") for compatibility breaks.
- **DEEPTHINK_09** requires **fixed objective severity + contextual display filtering** — severity must never be audience-configurable or the "CI Paradox" destroys trust — and telemetry of suppressed findings ("suppression velocity").
- **DEEPTHINK_10** (Coverity, Google Tricorder evidence): false positives are fatal; CI-blocking rules need an effective FP rate < 10%; expose **categorical modalities** (ERROR/WARNING/INFO), never raw confidence percentages.
- **DEEPTHINK_11** (four-tier lifecycle): IDE = warn-only fail-open; pre-commit = soft block, `Cost ≤ O(N)`, deterministic only, 2s budget; CI = context crucible, hard block for security/breaking/structural; deployment gate = dynamic checks. Rulesets must be versioned artifacts pinned via a repo config file so IDE/CI never disagree.
- **DEEPTHINK_12** answers residual ambiguity: uncertainty is usually *lack of codified policy* — a conventions file upgrades low-confidence guesses to 100%-confidence local rules; ambiguous constructs get flagged with a demanded explicit-intent suppression.
- **RESEARCH_01** benchmarks Spectral (~64 permissive rules), Vacuum (~88 rules, OWASP native, granular taxonomy), Redocly and IBM (impact scoring) — establishing the competitive bar for rule coverage and configuration ergonomics.

## Current State (gap)

- Rules are **hard-coded imperative functions** scattered in `_spec_validator_helpers.py`, `_schema_validator_helpers.py` (GraphQL), `_asyncapi_validator_helpers.py`, `_avro_validator_service_helpers.py`, `_protobuf_validator_service_helpers.py`. No rule IDs registry, no metadata, no enable/disable, no config file.
- A single boolean `--strict` per command is the only strictness control (`cli/_parser_flags.py`, `OpenAPIConfig.strict_mode`).
- `OpenAPI/services/_spec_validator_helpers.check_deprecated` flags any `deprecated: true` operation as **ERROR** — exactly the overzealous behavior DEEPTHINK_02/06 warn erodes trust (deprecation is a legitimate lifecycle state).
- No suppressions, no baseline file, no waivers, no profiles, no ruleset versioning.

## Target State

### New module: `Asgard/Forseti/Rules/`

```
Asgard/Forseti/Rules/
├── __init__.py
├── models/
│   ├── rule_models.py        # RuleMeta, RuleResult, Profile, SuppressionEntry, BaselineEntry, WaiverEntry
│   └── _rule_base_models.py
├── services/
│   ├── rule_registry_service.py    # register/query rules by metadata predicate
│   ├── profile_service.py          # load profile, select rules, execution budget
│   ├── baseline_service.py         # .forseti-baseline.json read/write/match
│   ├── waiver_service.py           # .forseti-waivers.yaml (compat epochs)
│   └── _suppression_helpers.py     # x-forseti-ignore parsing (with reason)
└── utilities/
    └── rule_utils.py
```

### Rule contract

```python
class RuleMeta(BaseModel):
    rule_id: str            # namespaced: "oas.paths.kebab-case", "avro.doc.required", "sec.owasp.no-http-basic"
    formats: set[SchemaFormat]
    target: Target          # SCHEMA | PAYLOAD
    cost: Cost              # O1 | ON | NETWORK
    confidence: Confidence  # DETERMINISTIC | HEURISTIC
    severity: Severity      # ERROR | WARNING | INFO | HINT  (fixed; only Platform-level profile files may remap upward)
    category: str           # structure | security | docs | style | compatibility | semantics
    description: str        # one-liner
    rationale: str          # "why this matters" educational payload (DEEPTHINK_09 Rich Finding)

class Rule(Protocol):
    meta: RuleMeta
    def check(self, node_ctx: NodeContext) -> Iterable[Finding]: ...
```

Existing validator helper functions are wrapped one-by-one into `Rule` objects; the registry is a module-level dict populated at import via a `@register_rule` decorator. Rule evaluation walks a parsed document once, dispatching rules by node type (visitor pattern) rather than each rule re-walking the tree — this is the AST-single-pass design RESEARCH_01 credits for Vacuum's performance lead.

### Profiles (`.forseti.yaml` in target repo, or `--profile` flag)

```yaml
version: 1
ruleset_version: "1.0.0"        # pinned per DEEPTHINK_11 §2 — same rules in IDE, hook and CI
profile: ci                     # ide | pre-commit | ci | audit  (built-in) or custom
rules:
  oas.docs.description-required: warning   # may strengthen, never weaken core (DEEPTHINK_11 federated hub/spoke)
  oas.style.kebab-case-paths: off          # only non-core rules can be disabled
overrides:
  - path: "legacy/**"
    rules: { oas.docs.*: off }
```

Built-in profile semantics (DEEPTHINK_05 §3, DEEPTHINK_11 §1):

| Profile | Rule selector | Budget | Bailout | Blocking |
|---|---|---|---|---|
| `ide` | all | 200 ms/file | fail-open | never |
| `pre-commit` | `cost ≤ O(N)` and `confidence == deterministic` | 2 s | fail-open, warn "deferring to CI" | soft (exit 1, bypassable) |
| `ci` | all (network rules cached) | 30 s | fail-closed | ERROR ⇒ exit 1; WARNING/INFO annotate only |
| `audit` | all | none | fail-closed | reports only |

Core rules (parse failure, broken `$ref`, structural impossibility) carry `core: true` and cannot be disabled or downgraded by any profile — DEEPTHINK_02 §"Inviolable Core".

### Suppressions, baselines, waivers

1. **Inline suppression** (DEEPTHINK_02 §3, DEEPTHINK_10 §4, DEEPTHINK_12 §4): `x-forseti-ignore: [{rule: "oas.docs.description-required", reason: "legacy downstream crashes on format"}]` in OpenAPI/AsyncAPI; `// forseti:ignore <rule> <reason>` comment for proto/GraphQL/SQL. A missing `reason` string is itself a WARNING. Suppressed findings are still counted and emitted in JSON output with `status: "suppressed"` so suppression-velocity dashboards are possible (DEEPTHINK_09 §C).
2. **Baseline** (`forseti baseline update <path>` → `.forseti-baseline.json`): hashes each existing finding as `sha1(rule_id + normalized_location + message_kind)`; subsequent runs report only net-new findings. Editing a baselined node revokes its exemption (Boy-Scout rule, DEEPTHINK_02 §4) — implemented by including the node's content hash in the entry.
3. **Waivers** (`.forseti-waivers.yaml`) apply **only** to compatibility rules and are scoped to an old→new version pair: `{rule: FIELD_REMOVED, location: User.address, from: v1.5, to: v2.0, reason: "...", expires: 2026-09-01}`. Once merged, the epoch is severed and strict enforcement resumes (DEEPTHINK_02 §4 Epoch Waiver Model). Baselines are explicitly rejected for compat checks — "you cannot baseline away a runtime exception".

## Concrete Changes

1. New `Rules/` package as above.
2. Refactor each `*_validator_service.py` to: parse → build `NodeContext` tree → `rule_registry.run(profile, tree)` → findings. The services' public `validate()`/`validate_file()` signatures and result models are preserved; results gain `findings: list[Finding]` while keeping `errors`/`warnings` as filtered views.
3. Fix `check_deprecated`: severity becomes `INFO` (`oas.lifecycle.deprecated-operation`), never a build-breaking ERROR.
4. `cli/_parser_flags.py`: add global `--profile`, `--config`, `--baseline`, `--no-baseline`; keep `--strict` as an alias mapping to profile `ci`.
5. `cli/_parser_commands.py` + new handler: `forseti baseline update|show`, `forseti rules list [--format json]` (rule catalog with metadata — the documentation surface juniors need per DEEPTHINK_09).

## Phased Steps

- **Phase 1**: `Rules/` models + registry + profile loading; wrap OpenAPI validator rules; inline suppression for OpenAPI.
- **Phase 2**: Baseline service + CLI; wrap GraphQL/AsyncAPI/Avro/Protobuf/JSONSchema validators.
- **Phase 3**: Waiver service wired into the Compatibility engine (plan 01); suppression telemetry in JSON output.
- **Phase 4**: Ruleset versioning (`ruleset_version` embedded in output, warning on mismatch between config pin and installed package).

## Testing Notes

- Unit-test the registry predicate queries (select by cost/confidence/format) and that `core: true` rules survive any profile.
- Round-trip tests: baseline created → rerun is clean → introduce new violation → only the new one reported → edit baselined node → its old violation resurfaces.
- Waiver expiry test with frozen clock; waiver applies only to the exact from/to pair.
- Regression: `forseti openapi validate --strict` output remains parseable by existing consumers (compare against golden files in `Asgard_Test/tests_Forseti/L1_Integration`).
- FP-rate guard: the L14_Industry fixture corpus (real-world specs) must produce zero ERROR-level findings from `heuristic` rules — heuristics may only ever be WARNING/INFO/HINT (DEEPTHINK_10 §2).
