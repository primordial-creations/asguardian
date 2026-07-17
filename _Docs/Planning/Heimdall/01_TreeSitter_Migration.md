# 01 — Tree-sitter Migration (Engine Foundation)

**Sources:** `_Docs/Research/Completed/DEEPTHINK_05_treesitter_migration_strategy.md`, `RESEARCH_01_treesitter_python_bindings.md`, `RESEARCH_02_treesitter_node_types_per_language.md`, `RESEARCH_04_semgrep_treesitter_internals.md`, `RESEARCH_08_treesitter_vs_alternatives.md`, `_Docs/Research/Heimdall/Completed/DEEPTHINK_01`.

## Rationale

Regex is mathematically incapable of parsing context-free grammars (RESEARCH_01); Heimdall's multi-language rules (`Security/SSRF`, `Security/ReDoS`, `Bragi/Architecture/_generic_solid_checks.py`, `Bragi/Quality/languages/*`) all operate on raw lines and inherit regex's failure modes: comments/strings trigger FPs, multi-line constructs trigger FNs, aliased imports are invisible. The scaffold in `Asgard/Heimdall/treesitter/` (`_language_loader.py`, `_parser_pool.py`, `_query_runner.py`, `_queries/<lang>_queries.py` for 10 languages) already implements graceful loading of PyPI grammar wheels (`tree-sitter>=0.22` era API, matching RESEARCH_01's recommendation of individual `tree-sitter-<lang>` packages over aggregators). What's missing is the *consumption architecture*.

Key research decisions adopted:
- **Strangler-Fig dual engine** via decorator with regex fallback (DEEPTHINK_05 §2). Zero test breakage; AST path is additive.
- **Parse once per file per scan** and pass the tree down — crossing the Python/C boundary repeatedly is the bottleneck (DEEPTHINK_01 top-level §3, RESEARCH_04 "aggressive memory caching").
- **Do NOT migrate lexical rules**: secrets, comment/TODO scanning, `.env` parsing, exact-token deprecations stay regex forever (DEEPTHINK_05 §4 — AST *hurts* secrets recall because trees drop nothing but scanning strings is regex's home turf).
- **Migration order by AST-ROI**: Python pilot → JS/TS → Java/C# → Go/PHP/Ruby → C++/Rust last (macros/strictness make ROI low) (DEEPTHINK_05 §1).
- **Fault tolerance**: handle `ERROR`/`MISSING` nodes without crashing; enforce UTF-8 gateways before `parser.parse()` (RESEARCH_04 pitfalls; RESEARCH_07 top-level notes error recovery keeps scans running on broken code).

## Target State

```
Asgard/Heimdall/treesitter/
    _language_loader.py      # exists — keep
    _parser_pool.py          # exists — add per-worker pools (nodes are not picklable)
    _query_runner.py         # exists — add compiled-query cache {(lang, query_text): Query}
    _queries/                # exists — extend with per-rule captures as needed
    ast_engine.py            # NEW — @with_ast_fallback decorator + ScanContext
    file_context.py          # NEW — FileParseContext: source_bytes, tree, lang, error_ranges
```

### The decorator contract (DEEPTHINK_05 §2, adapted to Heimdall signatures)

```python
def with_ast_fallback(language: str, ast_impl):
    def decorator(regex_impl):
        @functools.wraps(regex_impl)
        def wrapper(file_path, lines, enabled, **kwargs):
            if not enabled:
                return []
            ctx = kwargs.get("parse_context")           # FileParseContext or None
            if ctx is None and is_available(language):
                ctx = FileParseContext.parse(file_path, lines, language)
            if ctx is not None and ctx.tree is not None:
                try:
                    return ast_impl(file_path, ctx)
                except Exception:
                    logger.debug("AST rule %s failed on %s; regex fallback",
                                 regex_impl.__name__, file_path)
            return regex_impl(file_path, lines, enabled)
        return wrapper
    return decorator
```

- Scanner orchestrators (`StaticSecurityService.scan`, `BugDetector.scan`, SOLID/hexagonal analyzers) construct **one** `FileParseContext` per file and thread it through `kwargs["parse_context"]`.
- `FileParseContext` records `error_node_ranges`; rules should skip findings whose span intersects an ERROR region (prevents garbage matches on broken code).
- Memory discipline (RESEARCH_01): contexts are scoped to the per-file loop; drop the tree before moving to the next file. In `ProcessPoolExecutor` workers, parse inside the worker and return only pickleable finding dataclasses (DEEPTHINK_01 top-level §7.1 — TS nodes hold C pointers and cannot cross process boundaries).

### Packaging

`pyproject.toml`:
```toml
[project.optional-dependencies]
ast = ["tree-sitter>=0.23", "tree-sitter-python", "tree-sitter-javascript",
       "tree-sitter-typescript", "tree-sitter-java", "tree-sitter-go",
       "tree-sitter-ruby", "tree-sitter-php", "tree-sitter-c-sharp",
       "tree-sitter-cpp", "tree-sitter-rust"]
```
On scan start without the extra, print once: `INFO: Regex mode. Install 'asguardian[ast]' for AST-precision scanning.`

## Migration Order & Rule Selection

| Wave | Language(s) | Rules to migrate | Rules to keep regex |
|------|-------------|------------------|---------------------|
| 1 (pilot) | Python | `eval/exec` detection, `yaml.load` loader-kwarg check, `subprocess` `shell=True`, decorator presence checks (`@login_required`), injection sink pre-filter (feeds plan 04) | secrets (`_secret_patterns.py`), TODO/comment scanners, `.env`/requirements parsing |
| 2 | JavaScript/TypeScript | SSRF/XXE patterns in `Security/SSRF`, injection sinks, `innerHTML` XSS, `Quality/languages/javascript` bug rules | none new |
| 3 | Java/C# | SQLi concat-in-`execute*` (S-expression from RESEARCH_07 top-level: `method_invocation` + `binary_expression operator:"+"` in args, with `prepareStatement(string_literal)` suppression), XXE `DocumentBuilder`/`XmlDocument` feature checks | — |
| 4 | Go/PHP/Ruby | on demand; Go regex is near-adequate due to gofmt | — |
| 5 | C++/Rust | `unsafe_block`, `unwrap/expect`, `transmute` (queries in RESEARCH_07 top-level) — advisory only | macro-heavy C++ rules |

Decision rule per DEEPTHINK_05 §4: migrate only if the regex rule historically FPs on multi-line wrapping, comments, string literals, or scoping.

## Testing & Acceptance Gates

1. **Parametrized legacy suite** (DEEPTHINK_05 §3): a pytest fixture toggling `ast_engine.TS_AVAILABLE` runs every existing test under both engines; both must pass identically before any rule PR merges.
2. **Benchmark fixtures**: new `Heimdall_Test/benchmarks/<lang>/` files with `# ruleid:` / `# ok:` annotations (Semgrep-style). Acceptance gate per rule: `Recall(AST) ≥ Recall(Regex)` AND `Precision(AST) > Precision(Regex)`.
3. **Performance budget**: end-to-end scan time on the Asgard repo itself must not regress >10%; single-file parse+query budget ≤ 25ms typical (RESEARCH_08: cold parsing is fast; skip incremental-parse caching — batch scanners shouldn't persist trees).

## Phased Steps

1. **Phase A (infra):** `ast_engine.py`, `file_context.py`, compiled-query cache in `_query_runner.py`, dual-engine pytest fixture, benchmark directory + scoring script. No rule changes.
2. **Phase B (Python pilot):** migrate the 5 pilot rules; wire `FileParseContext` through `StaticSecurityService` and `cli/handlers/scan_steps_*.py`. Prove ≥20% precision gain on fixtures.
3. **Phase C (JS/TS + Java):** waves 2–3; migrate `Security/SSRF` and injection rules per plan 07 recipes.
4. **Phase D (long tail + pruning):** tag intentionally-unmigrated rules with `# AST-Migration-Skipped: Regex optimal (lexical)`; document engine status per rule in `Profiles` metadata so users can see which rules are AST-backed.

## Notes / Risks

- TS grammar for Python relies on an external C scanner for indentation (RESEARCH_08) — treat parse failures as fallback triggers, never crashes.
- TSX/TypeScript need the dedicated `language_typescript()`/`language_tsx()` entry points (loader already handles typescript; add tsx routing by extension).
- Avoid hard-coding S-expressions per rule where the CIR (plan 02) can serve — security sink queries are fine as S-expressions; structural analysis (classes/methods/fields) must go through the CIR extraction layer to avoid the "combinatorial explosion of language-specific logic" (RESEARCH_04 synthesis).
