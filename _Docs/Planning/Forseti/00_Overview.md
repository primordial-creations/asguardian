# Forseti Upgrade Plan — Overview

**Scope**: `Asgard/Forseti/` (API & schema validation: OpenAPI, AsyncAPI, GraphQL, JSON Schema, Avro, Protobuf, Contracts, Database, MockServer, CodeGen, Documentation).
**Inputs**: 29 research docs in `_Docs/Research/Forseti/Completed/` (DEEPTHINK_01–12, RESEARCH_01–17), intended-behavior docs in `_Docs/Asgard/Forseti/`, and the current source tree (~22.5k LOC, stdlib+pydantic+yaml only — no third-party schema libraries).

## Executive Summary

Forseti today is **broad but shallow**: it parses and structurally validates six schema formats and diffs three of them, entirely with hand-rolled logic. That breadth is a real asset — few tools cover OpenAPI + AsyncAPI + Avro + Protobuf + GraphQL + SQL in one CLI — but every capability stops at the first tier of what the research defines as state of the art:

1. **Compatibility is binary and fragmented.** Each format module owns a private `BreakingChange` model and pass/fail verdict. The research (DEEPTHINK_01/02/04, RESEARCH_02/03/08/14) is unambiguous that credible compatibility tooling needs directional semantics (input contravariance / output covariance), structural-vs-semantic tiering, transitive modes, and an explainable score — not a boolean.
2. **There is no governance layer.** Rules are hard-coded functions with a single `--strict` flag; no rule ids, profiles, suppressions, baselines, or waivers. Empirical evidence (Coverity, Google Tricorder via DEEPTHINK_10) shows this is the difference between adopted tooling and uninstalled tooling. Worst instance: `deprecated: true` operations are flagged as build-breaking ERRORs — punishing exactly the graceful-lifecycle behavior the tool should reward.
3. **The feedback surfaces are duplicated and impoverished.** Seven modules duplicate text/markdown report generators; no line numbers, no SARIF, no stable machine envelope, inconsistent exit codes.
4. **The drift loop is open.** Forseti can compare spec-to-spec but never spec-to-implementation, while research puts spec drift at up to 41% of APIs within 30 days (RESEARCH_10) — making generated mocks and docs "dangerous liars" (DEEPTHINK_03).
5. **The differentiating opportunity is untouched.** Cross-format entity alignment (Avro↔proto↔OpenAPI↔GraphQL↔SQL consistency, DEEPTHINK_08, RESEARCH_12) is absent from Forseti *and* from the commercial landscape — the highest-leverage novel feature available to this codebase.

The plan deliberately preserves Forseti's two structural strengths — the models/services/utilities three-tier convention and the zero-third-party-dependency posture — and sequences work so that two foundation layers (unified compatibility engine, rule registry + reporting) unlock everything else.

## Gap Analysis: Current vs Intended/Research Target

| Area | Current (`Asgard/Forseti/`) | Intended docs (`_Docs/Asgard/Forseti/`) | Research target | Gap | Plan |
|---|---|---|---|---|---|
| Compatibility checking | Per-format set-diffs; binary result; 3 duplicated `BreakingChange` models; no direction awareness; GraphQL/AsyncAPI have none | `check-compat`, `breaking-changes` with mitigations, levels | Unified IR-projected engine, contravariance/covariance, structural/semantic/empirical tiers, transitive modes, 0–100 explainable score (DEEPTHINK_01/04, RESEARCH_02/03/08/14) | Large | 01 |
| Rule governance | Hard-coded checks; one `--strict` flag; no ids/config/suppressions/baselines/waivers; deprecated-op = ERROR | `--strict` documented only | Metadata-tagged rule registry, validation profiles (ide/pre-commit/ci), fixed severities, inline suppressions w/ reasons, baselines, epoch waivers (DEEPTHINK_02/05/09/10/11/12) | Large | 02 |
| OpenAPI linting | ~12 structural checks; no `$ref` resolution; no security or docs-quality rules | `validate [--strict]` | 60–90 rule parity (Spectral/Vacuum, RESEARCH_01), OWASP static set (RESEARCH_16), semantic-heuristic layer (DEEPTHINK_06) | Large | 03 |
| Completeness scoring | None | Not documented | 4-vector matrix + gated maturity tiers, description-entropy heuristics, examples-validate-against-schema (DEEPTHINK_08, RESEARCH_09) | New | 03 |
| Deprecation & versioning | Changelog text; no lifecycle metadata; no SemVer output | changelog via `--version` | Sunset metadata (`x-sunset-date`, RFC 8594), lifecycle-aware scoring, migration-guide scaffolds, algorithmic SemVer bumps (DEEPTHINK_07, RESEARCH_03) | Medium | 04 |
| JSON Schema engine | Hand-rolled draft-07 interpreter; no `$defs`/anchors/cycles; no 2020-12; no compile cache | draft-07 config default documented | Compile-then-run engine, 2020-12 + draft-07 dialects, official-suite parity, dialect conversion for OAS 3.0⇄3.1, LLM structured-output subset (RESEARCH_05/17) | Large | 05 |
| Live contract testing | None (spec-vs-spec only) | `contract validate` (two files) | Spec-vs-live probing with RESTler-style dependency ordering, negative testing, drift reports (RESEARCH_04/09/15, DEEPTHINK_03) | New | 06 |
| Mock servers / data | Static stubs; uncorrelated random data | `mock generate/data` (in CLI, undocumented in module docs) | Stateful scenarios, validation-proxy mode, semantically correlated data (Luhn, locales), example-first (RESEARCH_10, DEEPTHINK_03) | Medium | 06 |
| Cross-format alignment | None | None | Canonical IR, lexical normalization, type matrix, entity catalog config, direction-aware severity (DEEPTHINK_08, RESEARCH_12) | New | 07 |
| Reporting & outputs | 7 duplicated report generators; no line/col; no SARIF; inconsistent exit codes | `--format text/json/markdown`; exit codes 0/1/2 | Rich Finding model, audience adapters, SARIF/GitHub annotations, source maps, blast-radius receipts (DEEPTHINK_04/09, RESEARCH_01) | Medium | 08 |
| Docs vs code drift | Module docs omit AsyncAPI/Avro/Protobuf/Mock/CodeGen/Docs modules; `Overview.md` omits 6 shipped modules; import paths in docs (`from Forseti...`) don't match code (`from Asgard.Forseti...`) | — | — | Doc refresh rides along each plan's Phase closes | all |

## Plan Index & Priorities

| File | Theme | Priority | Depends on |
|---|---|---|---|
| `01_Unified_Compatibility_Engine.md` | Shared compatibility engine: directional taxonomy, tiers, score, transitive modes, GraphQL/AsyncAPI diffing | **P0** | — |
| `02_Rule_Engine_Profiles_Governance.md` | Rule registry + metadata, validation profiles, suppressions, baselines, waivers | **P0** | — |
| `03_OpenAPI_Linting_Completeness_Security.md` | Ruleset expansion to Spectral/Vacuum parity, completeness vectors + tiers, OWASP static security | **P1** | 02 |
| `04_Breaking_Change_Lifecycle_Versioning.md` | Deprecation/sunset lifecycle, migration guides, SemVer recommendation, consumer dependency audit | **P1** | 01, 02 |
| `05_JSONSchema_Core_and_Conversion.md` | Compiled draft-aware validation core, 2020-12, dialect conversion, LLM subset checks | **P1** | — (feeds 03, 06) |
| `08_Reporting_Output_Architecture.md` | Rich Finding model, source maps, SARIF/GitHub reporters, handler unification, exit-code policy | **P1** | 02 (co-designed) |
| `06_Contract_Testing_Mocking_Drift.md` | Live spec-vs-implementation validation, stateful/semantic mocks, proxy drift detection | **P2** | 05, 08 |
| `07_Cross_Format_Alignment.md` | Canonical IR + entity alignment across all six formats + SQL | **P2** | 01 (IR concepts), 02, 08 |

**Recommended sequencing**: 02 + 08 first (they are co-dependent foundations every other plan emits into), then 01, then 03/04/05 in parallel, then 06/07. Each plan is internally phased so value lands incrementally without breaking the documented public API (`Overview.md` Python examples and CLI reference are treated as compatibility contracts, modulo the `Asgard.Forseti` import-path correction).

## Cross-Cutting Constraints

- **No new hard dependencies**: the import scan shows the package runs on stdlib + pydantic + yaml. All plans respect this; anything network-bound is profile-gated (`Cost: NETWORK`, DEEPTHINK_05) and stdlib-implemented.
- **API stability**: existing service classes, result models and CLI commands keep working through at least one release with deprecation notes; new capability arrives as new fields/subcommands.
- **Severity discipline** (applies to every plan): heuristic rules may never be ERROR (DEEPTHINK_10 <10% FP threshold); core structural rules may never be disabled (DEEPTHINK_02); severity is fixed, display is filtered (DEEPTHINK_09).
- **Testing home**: `Asgard_Test/tests_Forseti/` (L0 mocked → L1 integration → L3 contract → L8 performance → L14 industry corpus); each plan defines its fixtures there.
