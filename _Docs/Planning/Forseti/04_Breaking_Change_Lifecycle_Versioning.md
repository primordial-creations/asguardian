# 04 — Breaking-Change Lifecycle, Deprecation Orchestration & SemVer (Priority P1)

## Research-Backed Rationale

- **DEEPTHINK_07** reframes breaking changes from *binary CI failures* to *lifecycle events*: a state machine of Declaration → Deprecation → Verification → Execution; auto-generated migration guides scaffolded from the AST diff; spec-held contract metadata (`deprecated: true`, `x-sunset-date` driving RFC 8594 `Sunset` headers, `x-replaced-by` JSON pointer, `x-migration-guide` URL) vs control-plane-held logistics; and consumer-side dependency audit ("npm-audit for APIs": fail consumer CI when a consumed endpoint sunsets within 30 days).
- **DEEPTHINK_04 §C** rewards time-decaying deprecations: deleting a field immediately tanks the score; deleting it after its declared sunset restores 100 — "mathematically rewards graceful lifecycle management".
- **RESEARCH_03** documents algorithmic SemVer enforcement as the end-state of breaking-change tooling (breaking ⇒ forced major bump; `0.x` pre-stability downgrade to minor; ecosystem-aware exceptions like Go import-path costs), and `oasdiff`-class changelog generation.
- **DEEPTHINK_02 §4** supplies the waiver/epoch mechanism that gates *intentional* breaks (implemented in plan 02; consumed here).

## Current State (gap)

- `Contracts/services/breaking_change_detector_service.py` already produces categorized changes, `suggest_mitigations`, `estimate_impact`, and `generate_changelog` — a good skeleton, but:
  - No deprecation awareness at all: removing an operation that has been `deprecated: true` for a year is scored identically to removing a live one.
  - No sunset metadata conventions; nothing reads or emits `x-sunset-date` / `x-replaced-by`.
  - No SemVer recommendation output.
  - Changelog is flat text; no migration-guide scaffold.
  - `check_deprecated` in the OpenAPI validator actively punishes the deprecation state (ERROR), inverting the desired incentive.

## Target State

### A. Lifecycle metadata conventions (spec-held, per DEEPTHINK_07 §2)

Forseti recognizes and lints these extensions on operations, schemas, properties, GraphQL fields (`@deprecated(reason:)`), proto fields (`deprecated = true`), Avro (`doc` convention `@deprecated(since=..., sunset=...)`):

```yaml
deprecated: true
x-sunset-date: "2026-12-01"        # ISO date; drives lint + lifecycle scoring
x-replaced-by: "#/paths/~1v2~1users"
x-migration-guide: "https://..."
```

New lint rules (registered per plan 02):
- `lifecycle.deprecated-needs-sunset` (WARNING): `deprecated: true` without `x-sunset-date`.
- `lifecycle.sunset-passed` (WARNING): sunset date in the past but element still present — nudges execution of removal.
- `lifecycle.replacement-missing` (INFO): deprecated without `x-replaced-by`.

### B. Lifecycle-aware compatibility classification

Extend the plan-01 engine's classification step:

```python
def lifecycle_adjust(change: UnifiedChange, old_node_meta: LifecycleMeta, today: date) -> UnifiedChange:
    if change.abstract_violation in REMOVAL_KINDS and old_node_meta.deprecated:
        if old_node_meta.sunset and today >= old_node_meta.sunset:
            change.base_severity = 0                      # graceful removal ⇒ score untouched (DEEPTHINK_04 §C)
            change.impact.semantic = TierVerdict.PASS
            change.message += " (deprecated since {since}, sunset {sunset} elapsed)"
        else:
            change.base_severity //= 2                    # deprecated but sunset not reached ⇒ halved deduction
            change.mitigation = "Wait for sunset {sunset} or record a waiver"
    return change
```

### C. Migration-guide scaffolding & structured changelog

`BreakingChangeDetectorService.generate_migration_guide(changes, version)` emits Markdown scaffolds from the mechanical diff, leaving the human "why" as TODO blocks (DEEPTHINK_07 §1):

```markdown
## Migrating to v2.0.0
### Removed: `GET /users/{id}` field `legacy_id`
- Replaced by: `user_uuid` (`x-replaced-by`)
- Mechanical change: string(int64-as-string) ⇒ format: uuid
- <!-- TODO(author): business context -->
```

`generate_changelog` upgraded to grouped, Keep-a-Changelog-style Markdown with sections Breaking / Deprecated / Added / Fixed, each entry carrying `rule_id` and location — consumable by Bragi/docs pipelines.

### D. SemVer recommendation (RESEARCH_03 §7)

```python
class VersionRecommendation(BaseModel):
    current: str | None
    recommended_bump: Bump      # MAJOR | MINOR | PATCH
    recommended_version: str | None
    reasons: list[str]          # rule_ids that forced the bump
```

Algorithm: any structural-FAIL change ⇒ MAJOR; additive-only (new endpoints/optional fields) ⇒ MINOR; docs/description-only ⇒ PATCH. Pre-1.0 (`0.x`) downgrades MAJOR→MINOR per RESEARCH_03's pre-stability convention. Emitted by `forseti contract breaking-changes --current-version 1.4.2` and in JSON output.

### E. Consumer-side dependency audit (DEEPTHINK_07 §3) — stretch

`forseti contract audit-deps deps.yaml`: a config lists consumed spec URLs/paths + the subset of operations the consumer uses; Forseti fetches/loads each spec, and fails (exit 1) if any used operation is deprecated with sunset < N days (`--horizon 30`). Uses only local/file specs in phase 1; HTTP fetch is `Cost: NETWORK` and CI-profile-only.

## Concrete Changes

1. `Contracts/models/contract_models.py`: add `LifecycleMeta`, `VersionRecommendation`, extend changelog models.
2. `Contracts/services/breaking_change_detector_service.py`: add `generate_migration_guide`, `recommend_version`; thread lifecycle metadata through detection (parse `deprecated`/`x-sunset-date` from old spec when walking).
3. New `Contracts/services/_lifecycle_helpers.py`: metadata extraction per format (OpenAPI extensions, GraphQL `@deprecated`, proto options, Avro doc tags).
4. OpenAPI validator: replace `check_deprecated` ERROR with the three lifecycle lint rules above.
5. CLI (`cli/_parser_commands.py`): `contract breaking-changes` gains `--current-version`, `--migration-guide out.md`, `--changelog out.md`; new `contract audit-deps <config> [--horizon N]`.

## Phased Steps

- **Phase 1**: lifecycle metadata parsing + lint rules + lifecycle-aware severity adjustment (OpenAPI only).
- **Phase 2**: SemVer recommendation + structured changelog + migration-guide scaffold.
- **Phase 3**: extend lifecycle extraction to GraphQL/proto/Avro via the unified engine.
- **Phase 4**: `audit-deps` consumer-side check.

## Testing Notes

- Time-travel tests (freeze `today`): same removal fixture scored three ways — not deprecated (full deduction), deprecated pre-sunset (halved + mitigation text), post-sunset (zero deduction, PASS).
- SemVer matrix: fixtures asserting MAJOR/MINOR/PATCH classification, plus `0.x` downgrade behavior.
- Migration guide golden-file tests (stable ordering; TODO markers present).
- `audit-deps` with a fixture registry: one dependency sunsetting in 10 days ⇒ exit 1 with named operation; horizon 5 ⇒ exit 0.
- Ensure `lifecycle.sunset-passed` is WARNING not ERROR — must not block CI (deletion is the producer's choice; the tool nudges).
