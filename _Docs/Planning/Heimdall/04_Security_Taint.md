# 04 — Security Taint Analysis (Layered Dispatch, Confidence, Inter-procedural)

**Sources:** `_Docs/Research/Heimdall/Completed/DEEPTHINK_01` (layer selection & dispatch), `DEEPTHINK_03` (confidence scoring), `DEEPTHINK_05` (inter-procedural design), `RESEARCH_02` (Python taint SOTA: CodeQL/Pysa/Semgrep/YASA), `RESEARCH_01` (benchmarks); `_Docs/Research/Completed/DEEPTHINK_04_security_taint_analysis_static.md` (CST-only algorithm, multi-language catalogue).

## Rationale

Current `Asgard/Heimdall/Security/TaintAnalysis/` (`taint_analyzer.py`, `_taint_visitor.py`, `_taint_patterns.py`): intra-function forward traversal on Python `ast`, name-list sources/sinks, boolean `sanitizer_detected`, limited cross-function follow. `injection_detection_service.py` and the domain scanners run *in parallel* on regex — no shared dispatch, duplicate findings, no confidence.

Research verdicts driving the design:
- **Layer economics** (DEEPTHINK_01): SQLi/SSRF/path-traversal/hardcoded-AES-key/weak-PRNG-in-security-context require Layer-3 intra-procedural taint; `yaml.load`, missing decorators, ReDoS-pattern extraction need only Layer-2 AST; AWS keys need only Layer-1 regex. Run-all-and-merge blows both latency and dedup budgets — use a **dispatch table with lazy taint**: parse once, evaluate structural rules, scan for trigger nodes (sources/sinks), and only build taint state for functions containing triggers. Import-alias resolution in the dispatch phase is mandatory (else `from requests import get as fetch` silently skips Layer 3).
- **Recall ceiling honesty** (RESEARCH_02): even Pysa/CodeQL score 0–11% recall on real-world PyVul; a CST-heuristic engine lands ~25–40% recall / ~70% precision (DEEPTHINK_04 top-level §7). Ship the documented disclaimer: fast shift-left guardrail, not a deep SAST replacement.
- **Confidence is a first-class output** (DEEPTHINK_03): Bayesian-style multiplicative model, decay per unknown hop, path-length decay, test-file caps, sink-kwarg overrides (`shell=False` → 0.0, `shell=True` → ~1.0).

## Target State

### A. Unified dispatch pipeline (per file)

```
Layer 1  regex sweep (secrets, key prefixes)          — raw text, always
Layer 2  single AST/CST parse                         — structural rules + trigger-node scan
         trigger index: {func_node: {sources:[], sinks:[]}} with alias-resolved names
Layer 3  lazy taint: only functions in trigger index  — env-stack forward traversal
```

Owner: new `Security/engine/dispatch.py`; `StaticSecurityService.scan` and `cli/handlers/taint.py` route through it. Findings deduplicate by `(file, sink_ast_span, cwe)` before reporting (DEEPTHINK_06 dedup rule).

### B. Taint algorithm upgrades (`_taint_visitor.py` → `Security/TaintAnalysis/engine/`)

Keep the existing forward AST traversal core, add (DEEPTHINK_04 top-level §1):
- **Scope stack** of environments (push/pop on blocks); assignment kills taint when RHS is clean.
- **Branch union**: traverse both `if` arms against cloned state, union results (over-approximation — a security tool must over-approximate, DEEPTHINK_05 §2).
- **TaintState carries `confidence: float` and `trace: list[TaintFlowStep]`** instead of a bare set membership.
- **Propagators**: BinOp/JoinedStr/f-string/`.format`/`%`/`str.join`/known formatters propagate with ×0.9 decay per mutation.
- **Sanitizer taxonomy** replaces the boolean: exact-signature sanitizers (`shlex.quote`, parameterized ORM call, `int()`, `uuid.UUID`) → confidence 0.0 (drop); custom `clean_*`/`sanitize_*`/`re.sub` → ×0.4 (keep, downgraded) (DEEPTHINK_03 §1).
- **Sink kwarg semantics**: `subprocess.*(…, shell=False)` → drop; `shell=True` → 1.0; `yaml.load(…, Loader=SafeLoader)` → drop; `requests.*(…, verify=False)` handled by TLS module not taint.

### C. Confidence model (DEEPTHINK_03 §§1–2, DEEPTHINK_04 top-level §5)

```
final = source_conf × Π(propagator_decay) × Π(hop_decay) × sink_conf × context_modifiers
source_conf : 1.0 exact framework API (request.args, @RequestParam-style, process.argv)
              0.8 conventional access (req.body.*, r.FormValue)
              0.6 heuristic param name on router-decorated function
              0.5 generic suspicious param name
hop decay   : ×0.85 per resolved inter-procedural hop; ×0.5 through unknown/3rd-party call
sink_conf   : 1.0 unambiguous global sink; 0.8 framework pattern; 0.4 generic name (.execute)
context     : test path → cap 0.1 (see plan 08); variable named mock_/test_/dummy_ → ×0.3
```
Buckets (display only, DEEPTHINK_03 §4): Certain >0.85 (may block CI), Probable 0.50–0.85 (PR warn), Possible 0.25–0.49 (never blocks), Unlikely <0.25 (hidden; audit dashboards only). Add `confidence` + `confidence_bucket` to `TaintFlow` and `SecurityFinding` (field exists on the base model — populate it everywhere).

### D. Inter-procedural extension (DEEPTHINK_05, phased)

1. **Function summaries** (flow-insensitive, over-approximated): per function, `param_index → {returns_taint: bool, mutates_params: set[int], reaches_sinks: [SinkRef]}` serialized as JSON.
2. **Call graph without types**: module-import resolution for plain calls; Class-Hierarchy-style name resolution scoped to imported files for `obj.method()` (union summaries of all imported classes defining `method`). **Framework stubs** in YAML (`Security/TaintAnalysis/stubs/{django,flask,fastapi,sqlalchemy}.yml`) model decorator routing and ORM sinks/sanitizers — RESEARCH_02 shows framework-native modeling is where Semgrep Pro wins.
3. **Bottom-up summary computation** from dependency-graph leaves; **top-down bounded propagation with k=4 hops max**, dropping paths at depth 5 (empirically >80% of true injection paths span ≤4 hops; deeper traversal destroys precision).
4. **Incremental cache**: SQLite `~/.asgard/taintcache.db`: `file_hash → AST-summary`, `function_hash → summary`, plus a reverse dependency graph. Invalidate upstream callers only when a function's *summary signature* changes, cascading to convergence (correctness argument in DEEPTHINK_05 §3).

### E. Multi-language (after plan 01 waves)

Port the engine to the CST via the DEEPTHINK_04 (top-level) catalogue: Java (`getParameter`/`executeQuery`/`Runtime.exec`, `Integer.parseInt` sanitizer), Go (`r.FormValue`/`db.Query`/`exec.Command`, `strconv.Atoi`), JS/TS (`req.query|body|params` → `.query(`, `exec(`, `innerHTML`; template-literal propagator; `parseInt`/`encodeURIComponent` sanitizers).

## Concrete Changes

| File | Change |
|---|---|
| `Security/engine/dispatch.py` | NEW: 3-layer dispatch, alias resolver, trigger index, dedup |
| `Security/TaintAnalysis/services/_taint_visitor.py` | scope stack, branch union, TaintState{confidence,trace} |
| `Security/TaintAnalysis/services/_taint_patterns.py` | split into `sources.py`/`sinks.py`/`sanitizers.py` with per-entry confidence + kwarg rules |
| `Security/TaintAnalysis/summaries.py` | NEW: summary computation + SQLite cache + RDG invalidation |
| `Security/TaintAnalysis/stubs/*.yml` | NEW: framework models |
| `Security/services/injection_detection_service.py` | becomes Layer-2 pre-filter feeding dispatch; regex path kept as fallback (plan 01) |
| `Security/models/taint_models.py` | add confidence fields, hop count, sanitizer records |

## Phases

1. **P1 (Python, intra-procedural):** dispatch + confidence + sanitizer taxonomy + branch union. Target on fixture corpus: precision ≥60% at Certain+Probable, alert density ≤2 FP/10k LOC (DEEPTHINK_06 Profile A).
2. **P2 (summaries):** same-file then cross-file summaries, k=4, cache. Measure recall uplift on decoupled source/sink fixtures.
3. **P3 (frameworks):** Django/Flask/FastAPI stubs; route-decorator sources; ORM sink/sanitizer semantics (`select_for_update`, parameterized calls).
4. **P4 (multi-language):** JS/TS then Java, riding plan 01 waves.

## Testing

- Fixture pairs per DEEPTHINK_01 category list (f-string SQLi decoupled across lines, `.format` SQLi, safe `os.path.join(BASE, 'templates')`, weak-PRNG-into-jwt vs weak-PRNG-into-backoff…), each with expected bucket.
- Determinism test: two consecutive scans on identical input yield byte-identical findings (gate prerequisite, DEEPTHINK_12 §4).
- Latency test: 50 changed files < 3s end-to-end on dispatch path (DEEPTHINK_01 SLA).
- Cache-correctness test: remove a sanitizer in file B, assert caller in unchanged file A is re-analyzed and now reports the flow.
