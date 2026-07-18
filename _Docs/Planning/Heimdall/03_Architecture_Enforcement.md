# 03 — Architecture Enforcement (Import Graph, Layer Inference, Drift)

**Sources:** `_Docs/Research/Completed/DEEPTHINK_03_import_graph_architecture_enforcement.md`, `RESEARCH_05_hexagonal_architecture_detection.md`, `RESEARCH_06_cohesion_coupling_metrics.md` (Ca/Ce), `architecture.yml` (repo root).

## Rationale

Current: `Bragi/Architecture/services/hexagonal_analyzer.py` + `_hexagonal_rule_checks.py` map files to layers purely by glob `path_patterns` from `architecture.yml` and check `allowed_imports`/`forbidden_imports`. `Bragi/Dependencies` builds a NetworkX import graph with file-level cycle detection. Gaps identified by research:

- **No layer inference**: files not matching any glob (e.g. `utils/helper.py`) are unclassified and silently unchecked.
- **No drift detection**: a file *placed* in `domain/` that imports SQLAlchemy passes glob classification but is architecturally infrastructure — the paradox DEEPTHINK_03 (top-level) detects via bound-crossing.
- **File-level cycles are noisy**: mutually recursive types in one directory are benign; architectural cycles live at module (directory) granularity (DEEPTHINK_03 §4B).
- **Regex/glob layering is the "lexical scanning" anti-pattern** RESEARCH_05 documents: blind to aliased imports and interface realization; tools like ArchUnit/dependency-cruiser/Boundary all moved to dependency-graph semantics, with Reflexion Models (convergence/divergence/absence) as the formal grounding.

## Target State

### 1. Configuration model — extend `architecture.yml` (backward compatible)

```yaml
architecture:
  name: "Clean Architecture"
layers:
  - name: domain
    level: 0                      # NEW: concentric integer levels; 0 = innermost
    heuristics:
      paths: ["*/domain/*", "*/models/*"]
      suffixes: ["Entity", "ValueObject", "Model"]      # NEW
  - name: application
    level: 1
    heuristics: { paths: ["*/services/*", "*/use_cases/*"], suffixes: ["UseCase", "Service", "Handler"] }
  - name: infrastructure
    level: 2
    heuristics:
      paths: ["*/infrastructure/*", "*/adapters/*", "*/repositories/*"]
      external_imports: ["sqlalchemy", "psycopg2", "requests", "boto3", "django.db"]  # NEW: anchors
rules:
  max_module_fan_out: 12
  detect_module_cycles: true
```

Universal invariant: for edge A→B, `Level(A) ≥ Level(B)` (dependencies point inward/laterally). Explicit `allowed_imports`/`forbidden_imports` remain supported as overrides but become derivable from levels.

### 2. Graph construction & normalization (DEEPTHINK_03 §2)

Node: `{id: abs_file_path, module_id: dirname, language, min_level, max_level, base_level}`. Edge: `{source, target, is_external}`.

Two-pass, language-agnostic:
1. **Global file index** — walk tree; for Java/C#/Go parse `package`/`module` declarations via tree-sitter to map namespaces → paths.
2. **Language path resolvers** — tree-sitter extracts raw import strings; resolvers handle relative (JS/TS/Rust/Ruby), namespace (Java/C#), module (Go/Python) forms; unresolved imports become `is_external=True` and are categorized against `external_imports` anchors.

For Python reuse `Bragi/Dependencies/services/import_analyzer.py` outputs; add the resolver layer for other languages.

### 3. Layer inference — Topological Bound Propagation (CSP)

```
init: matched files -> min=max=base level; unmatched -> min=0, max=MAX
      external imports -> anchored at their configured level
iterate until fixpoint (monotonic, guaranteed to converge):
  Rule 1 (outward gravity): A.min = max(A.min, B.min) for each A->B
  Rule 2 (inward gravity):  B.max = min(B.max, A.max) for each A->B
```

Post-fixpoint classification:
- `min == max` → assigned, confidence 100%.
- `min < max` → bridge file; assign `min`; `confidence = 1 − (max−min)/MAX_LEVELS`.
- `min > max` → **Architecture Drift Violation** — report: *"File X intrinsically looks like Domain (level 0) but acts as Infrastructure (level 2) via dependency on sqlalchemy."* This is the highest-value new finding class.

### 4. Violation detectors

| Check | Algorithm | Output |
|---|---|---|
| Layer violation | O(E) scan: flag `A.layer < B.layer` on local edges. IoC naturally passes (Impl level 2 → interface level 0 is 2≥0) | `LayerViolation` (exists — extend with inferred levels + confidence) |
| Drift | bound paradox above | NEW `ArchitectureDriftViolation` |
| Module cycles | collapse file graph to module graph by `module_id`; Tarjan SCC; report components with size>1 | upgrade `Bragi/Dependencies/services/cycle_detector.py` with `--granularity=module` (default) |
| Fan-out | `len({target.module_id for e in node.out})` > `max_module_fan_out` | warning |
| Hexagonal anti-patterns (RESEARCH_05, "Boundary" tool) | Missing Ports: adapter class in infrastructure with no `implements` of a domain/ports interface (needs CIR from plan 02). Anemic Domain Model: `ClassInfo` in domain with fields but zero non-accessor methods. Infrastructure Leak: framework decorators/attributes on domain entities | NEW findings in `hexagonal_analyzer.py` |

### 5. Incremental mode (DEEPTHINK_03 §5)

Persist the graph (nodes+edges+bounds) in `~/.asgard/archgraph/<project-hash>.json` keyed by file content hashes. On change of file F: delete F's outgoing edges, re-parse F only, re-propagate bounds via worklist from F (monotone → localized), check layer rules on new edges only, and run a targeted DFS from F's new edge targets to detect newly introduced module cycles (no global Tarjan re-run).

## Concrete Changes

1. New `Bragi/Architecture/graph/` package: `nodes.py`, `resolvers.py` (per-language import resolution), `propagation.py` (CSP fixpoint), `drift.py`.
2. `hexagonal_analyzer.py`: keep public API; add level-based mode when `level:` present in YAML; keep glob-only mode otherwise.
3. `_architecture_config.py`: parse extended schema; validate levels are unique and monotone.
4. `cycle_detector.py`: module-granularity SCC default, file-granularity behind flag.
5. CLI (`cli/handlers/oop_arch.py`): `heimdall arch layers <path> --explain <file>` prints a file's inferred bounds and which imports pinned them (essential for trust in inference).
6. Reflexion-model summary in reports (RESEARCH_05): counts of convergences / divergences / absences (declared allowed edges never observed).

## Testing

- Fixture project with domain/application/infrastructure trees + a deliberately drifted file; assert paradox detection with exact pin explanation.
- Convergence test: random DAGs — propagation reaches fixpoint ≤ |V| iterations; no oscillation.
- IoC test: interface in domain implemented in infrastructure produces zero violations.
- Module-cycle fixture: two directories importing each other through different files; file-level cycle absent, module-level present.
- Incremental equivalence: full rebuild vs incremental update after a random edit produce identical bounds/violations.
