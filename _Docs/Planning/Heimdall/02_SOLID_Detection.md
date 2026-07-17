# 02 — SOLID Detection via Common Intermediate Representation

**Sources:** `_Docs/Research/Completed/DEEPTHINK_01_solid_detection_architecture.md`, `DEEPTHINK_02_solid_heuristics_without_types.md`, `RESEARCH_03_sonarqube_solid_detection.md`, `RESEARCH_06_cohesion_coupling_metrics.md`, `RESEARCH_02_treesitter_node_types_per_language.md`.

## Rationale

Current state in `Asgard/Bragi/Architecture/services/`:
- `solid_validator.py` + `_solid_checks.py` + `_solid_detectors.py`: Python-only, `ast`-based.
- `_generic_solid_checks.py`: multi-language via **regex** (`public\s+\w+...` method matching) — precisely the brittle approach the research condemns.
- `_treesitter_solid_checks.py` (755 lines): a start on LCOM4 via tree-sitter, but Python-only queries, manual tree walks, and no shared representation.

DEEPTHINK_01 (top-level) prescribes a **Declarative Normalization Architecture**: one extraction query per language mapping native nodes to a universal taxonomy; a language-agnostic CIR (`ClassInfo`/`MethodInfo` slotted dataclasses); pure-Python SOLID evaluators over the CIR. Adding a language then means writing one `.scm` file, zero core changes. DEEPTHINK_02 (top-level) sets the honest accuracy ceilings and the confidence-tier policy; RESEARCH_03 supplies SonarQube's empirically validated thresholds.

## Target State

```
Asgard/Bragi/Architecture/
    cir/
        models.py            # ClassInfo, MethodInfo, FileInfo (slots=True dataclasses)
        builder.py           # flat captures -> hierarchy (byte-range nesting + receiver linking)
    queries/<lang>/extract.scm   # ONE extraction query per language
    evaluators/
        srp.py  ocp.py  lsp.py  isp.py  dip.py
    solid_validator.py       # orchestrator — keeps public API, routes to CIR when TS available
```

### CIR data model (DEEPTHINK_01 §1)

```python
@dataclass(slots=True)
class MethodInfo:
    name: str; start_line: int; end_line: int
    is_override: bool; is_empty: bool; throws_unimplemented: bool
    type_switches: int = 0
    all_identifiers: set[str] = field(default_factory=set)
    instantiations: set[str] = field(default_factory=set)
    param_types: set[str] = field(default_factory=set)

@dataclass(slots=True)
class ClassInfo:
    name: str; is_interface: bool; filepath: str
    start_line: int; end_line: int
    fields: set[str] = field(default_factory=set)
    methods: list[MethodInfo] = field(default_factory=list)
    implements: set[str] = field(default_factory=set)
    import_roots: set[str] = field(default_factory=set)
```

`slots=True` matters: tens of thousands of methods, ~60% memory reduction (DEEPTHINK_01 §7.2).

### Extraction & assembly

- **One massive `extract.scm` per language**, not per-rule queries: O(N) traversal instead of O(Rules×N), and new languages need zero Python changes (DEEPTHINK_01 §3). Universal capture taxonomy per RESEARCH_02: `@class.def`, `@class.name`, `@interface.def`, `@method.def`, `@method.receiver`, `@field.def`, `@expr.instantiation`, `@expr.typecheck`, `@import`, `@identifier`.
- **Assembly algorithm** (DEEPTHINK_01 §4): lexical byte-range containment stack for Java/C#/TS/Ruby/PHP/Python; explicit `@method.receiver` name-binding for Go/Rust/C++ methods declared outside the type.
- **Parallelism**: workers parse + build CIR + drop the tree; only pickleable CIR crosses process boundaries. Target: 50k LOC in <5s (DEEPTHINK_01 §7.1).

### Evaluators — rules, formulas, thresholds

| Principle | Rule | Algorithm / formula | Threshold | Confidence | Expected P/R (DEEPTHINK_02) |
|---|---|---|---|---|---|
| SRP | Disjoint-Domain God Class | Syntactic **LCOM4**: graph over methods+fields, edge if method references field or calls sibling method; count connected components (DFS). Plus lexical verb clustering on method-name prefixes and import-root fan-out | flag if `methods > 20` AND (`LCOM4 > 1` OR `import_roots ≥ 3`) | MEDIUM (report as "Refactor Suggestion") | ~60% / ~80% |
| SRP | Dimensional limits | method count, coupling proxy | 35 methods (SonarQube S1448), 20 distinct referenced types (S1200), cognitive complexity 15 (S3776) — reuse `Bragi/Quality` complexity outputs | HIGH | — |
| OCP | Type-Dispatch Cascade | conditional chains (`switch`/`match`/`if-elif` ≥3 branches) whose condition uses `instanceof`/`typeof`/`is`/`isinstance` OR switches on identifiers named `type/kind/status` | ≥3 branches | HIGH | ~90% / ~15% |
| LSP | Refused Bequest only | overridden method whose body is empty or solely raises `NotImplementedError`/`NotSupportedException`/`panic!` | any | HIGH (P≈99%) | 99% / <2% — **skip semantic LSP entirely and document why** |
| ISP | Stubbed Implementer | class with `implements` where >25% of methods are empty stubs / throw NotImplemented | 25% | HIGH (~85% precision) | 85% / 40% |
| ISP | Fat Interface | interface with >12 methods AND distinct param-type strings >5 (parameter-type entropy) | 12 / 5 | LOW ("Architectural Smell") | — |
| DIP | Lexical Concretion Instantiation | instantiations where target name ends in `Service|Repository|Manager|Controller|Client|Dao|Engine`; suppress when enclosing class ends in `Factory|Builder|Provider|Module|Config` or method is `main`/composition root | deny/allow lists configurable via Profiles | HIGH (~85% precision) | 85% / 60% |

Violation model gains `confidence: Confidence` (HIGH/MEDIUM/LOW enum with explanatory strings) and `evidence: str` (e.g. `"LCOM4 = 3: methods {a,b} | {c} | {d,e} form disjoint components"`). CI filtering: `--fail-on-confidence=HIGH`.

### Explicit non-goals (document in module docstring + user docs, DEEPTHINK_02 final matrix)

- Semantic LSP (contract narrowing) — uncomputable from isolated CSTs.
- Temporal OCP (is the class actually closed) — requires git-churn analysis; optionally a future enhancement joining `Reporting/History` data.
- Distinguishing intentional Facades/Orchestrators from God classes — mitigated by confidence tiers, never by silence.

## Concrete Changes

1. New `cir/` package + `queries/*/extract.scm` (start: python, javascript, typescript, java; then go, csharp, ruby, php, rust, cpp).
2. Rewrite `_treesitter_solid_checks.py` content into `evaluators/*` operating only on CIR; delete its ad-hoc tree walking.
3. `_generic_solid_checks.py` becomes the documented regex fallback behind `@with_ast_fallback` (plan 01); mark as legacy.
4. `solid_validator.py` public API unchanged (`SolidValidator.validate(path)`); internally routes: TS available → CIR path; else → existing Python-`ast` checks for `.py` + regex fallback for others.
5. Thresholds exposed through `Shared/Profiles` `RuleConfig.parameters` (e.g. `srp_max_methods`, `dip_deny_suffixes`).

## Testing

- Fixture classes per principle per language under `benchmarks/solid/<lang>/` with annotated expected violations (including negative cases: DTOs, Facades, composition roots).
- Property test: LCOM4 of a class whose methods all touch one shared field == 1; adding a disconnected method+field island increments it by exactly 1.
- Cross-language consistency test: semantically identical Java/TS/Python fixtures yield identical CIR-level violations.
- Perf test: synthetic 50k LOC tree < 5s wall on 4 cores.
