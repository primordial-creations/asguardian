# 08 — Reporting & Output Architecture: Rich Findings, SARIF, Audiences (Priority P1)

## Research-Backed Rationale

- **DEEPTHINK_09** mandates **extreme decoupling** of analysis from presentation: a headless engine emitting a standardized **"Rich Finding"** object (coordinates, terse data + rule id, educational payload, remediation data, metadata), with **audience-specific adapters** — dense greppable UNIX lines for seniors (`user-api.yaml:42:10 ERR [fmt-012] Missing email format`), educational payloads for juniors/IDE, aggregate telemetry sinks (SARIF to warehouses) for platform teams. Severity is fixed; only *display filtering* varies by audience.
- **DEEPTHINK_04 §4A** requires "Radical Explainability" — the Blast-Radius Receipt when a gate blocks.
- **DEEPTHINK_10** requires categorical modalities (ERROR/WARNING/INFO/HINT), never raw confidence scores, in all output surfaces.
- **RESEARCH_01** notes SARIF/GitHub-annotation integration and IDE/LSP presence as key adoption drivers among linters; IBM's impact-scoring taxonomy bridges dev output to executive reporting.
- **DEEPTHINK_08 §3** wants radar-style dimensional output (vectors + tiers) rather than composite scores for completeness.

## Current State (gap)

- Report generation is duplicated **per service**: `generate_text_report`/`generate_markdown_report` exist in at least seven `_*_helpers.py` files (OpenAPI, Contracts, Avro, Protobuf, GraphQL, JSONSchema, AsyncAPI) with drifting formats.
- Handlers `print()` directly; `--format {text,json,markdown}` is honored inconsistently (some handlers ignore it).
- No line/column coordinates: YAML is loaded with `yaml.safe_load`, discarding marks, so findings carry only JSONPath-ish strings.
- No SARIF, no GitHub annotations, no machine-stable rule ids, no remediation payloads.

## Target State

### A. Canonical Finding model (`Asgard/Forseti/Reporting/models/finding_models.py`)

```python
class Coordinates(BaseModel):
    file: str | None
    json_path: str            # canonical pointer within the document
    line: int | None          # populated when source-mapped loader used
    column: int | None

class Remediation(BaseModel):
    description: str
    json_patch: list[dict] | None   # RFC 6902 ops for deterministic auto-fix (DEEPTHINK_09 "Quick Fix")

class Finding(BaseModel):
    rule_id: str
    severity: Severity              # ERROR | WARNING | INFO | HINT (fixed, plan 02)
    message: str                    # one sentence, terse
    coordinates: Coordinates
    rationale: str | None           # educational payload (from RuleMeta)
    remediation: Remediation | None
    suppressed: bool = False
    suppression_reason: str | None
    category: str
    format: SchemaFormat
```

All validators/checkers/alignment/compat services emit `Finding` (plan 02 wraps this); legacy result models (`OpenAPIValidationError`, `BreakingChange`, `JSONSchemaValidationError`) become views over findings for one deprecation cycle.

### B. Source-mapped loading

New `Asgard/Forseti/Reporting/utilities/sourcemap_loader.py`: wrap `yaml.compose`/custom constructor to record `(line, column)` per node into a side-table `dict[json_path, (line, col)]`; JSON path via a small tolerant tokenizer (stdlib `json` + manual scanner for positions, or line-tracking on key occurrences — best-effort, `None` when ambiguous). All `load_spec_file`/`load_schema_file`/`load_contract_file` utilities gain an optional `with_sourcemap=True` used by CLI paths. This unlocks the grep-able senior format and IDE integration later.

### C. Reporter adapters (`Reporting/services/`)

| Reporter | Output | Notes |
|---|---|---|
| `TextReporter` | `file:line:col SEV [rule-id] message` one per line; summary footer | default; `--quiet` errors-only (senior profile, DEEPTHINK_09 §B) |
| `ExplainReporter` | text + rationale + remediation per finding | `--explain`; junior/educational surface without an IDE plugin |
| `JsonReporter` | stable envelope `{tool, version, ruleset_version, findings[], summary{}, score?}` | supersedes ad-hoc dicts |
| `MarkdownReporter` | grouped by severity/category; tables | PR-comment ready |
| `SarifReporter` | SARIF 2.1.0 (`runs[].tool.driver.rules[]` from RuleMeta; `results[]` from findings) | GitHub code scanning / warehouse sink (DEEPTHINK_09 §C) |
| `GithubReporter` | `::error file=...,line=...::message` workflow commands | zero-config CI annotations |
| `ReceiptReporter` | compat-gate block receipt: change, blast radius, usage, remediation (DEEPTHINK_04 §4A format) | used by `compat check` on failure |

`--format` global flag extends to `{text,json,markdown,sarif,github}`; `generate_report(result, format=...)` methods delegate to reporters (back-compat preserved).

### D. Handler unification

`cli/handlers_*.py` currently ~680 lines of duplicated load→run→print→exit-code logic. Introduce `cli/_handler_runner.py`:

```python
def run_and_report(service_call, args, *, gate=default_gate) -> int:
    findings, extras = service_call()
    reporter = select_reporter(args.format, args.explain, args.quiet)
    sys.stdout.write(reporter.render(findings, extras))
    return gate(findings, args)   # 0/1/2 mapping, honoring --min-score / --min-tier
```

Exit-code policy centralized: 2 = input/config errors (file missing, unparseable), 1 = gate failure (ERROR findings, score/tier unmet), 0 otherwise — matching the documented contract in `Overview.md` and making it uniform (today some handlers return 1 for missing files).

## Concrete Changes

1. New `Reporting/` package (models/services/utilities).
2. Replace seven per-module `generate_*_report` helper pairs with reporter calls; keep thin wrappers for public API compatibility.
3. `sourcemap_loader` + opt-in wiring in the three loader utilities.
4. `cli/_parser_flags.py`: `--quiet`, `--explain`; extend `--format` choices; `cli/_handler_runner.py` + refactor handlers onto it.
5. Embed `ruleset_version` and tool version in every machine-readable envelope (DEEPTHINK_11 determinism).

## Phased Steps

- **Phase 1**: Finding model + Text/Json reporters + handler runner (pure refactor, golden-file protected).
- **Phase 2**: sourcemap loader (YAML first; JSON best-effort) — line numbers appear in text output.
- **Phase 3**: SARIF + GitHub reporters; Markdown consolidation.
- **Phase 4**: ExplainReporter + Remediation `json_patch` on the top ~15 auto-fixable rules (missing `additionalProperties`, missing description stubs, kebab-case path rename suggestions); groundwork for a future `forseti fix` command.

## Testing Notes

- Golden-file tests per reporter over one shared synthetic finding set (stable ordering: file, line, rule_id).
- SARIF output validated against the SARIF 2.1.0 JSON schema (vendored fixture) using Forseti's own JSONSchema validator — dogfooding test.
- Sourcemap accuracy: fixture YAML with known node positions; assert ±0 line for mapped keys; unmapped ⇒ `None` never wrong.
- Exit-code matrix test across all commands: missing file ⇒ 2; ERROR finding ⇒ 1; warnings-only ⇒ 0 (and ⇒ 1 only with `--strict`/ci profile where documented).
- Round-trip: `json` envelope re-parsed by `JsonReporter.parse` for tooling reuse (schema documented in `_Docs`).
