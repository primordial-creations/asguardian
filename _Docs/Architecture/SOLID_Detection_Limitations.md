# SOLID Detection Limitations

## LSP (Liskov Substitution Principle) — Intentionally Skipped

### Why LSP cannot be detected from syntax alone

LSP requires verifying that a subtype `B` can be substituted everywhere its supertype `A` is expected without altering program correctness. Specifically it requires detecting:

- **Precondition strengthening**: `B.method` requires stricter inputs than `A.method`
- **Postcondition weakening**: `B.method` guarantees less in its return values than `A.method`
- **Invariant violation**: `B` breaks invariants maintained by `A`
- **Behavioral substitutability**: A caller holding a reference typed as `A` is actually holding a `B`, and the program breaks

None of these can be inferred from syntax alone. A tree-sitter query can identify that `B` inherits from `A` and that both define `method`, but it cannot determine:

- Whether the parameter constraints are compatible (requires type inference across call sites)
- Whether the return value semantics are preserved (requires dataflow analysis or specification annotations)
- Whether the subtype is ever used in a context where the supertype is expected (requires whole-program type resolution)

Checking `if isinstance(x, B)` or narrowing casts are OCP signals, not LSP signals — they indicate type dispatch, not substitutability failure.

### Status

LSP detection is intentionally omitted from Heimdall. Adding false-positive LSP detections (e.g. flagging all overriding methods) would produce noise with no actionable signal.

### Future path

Accurate LSP checking requires a running language server:

1. **pyright / pylance** (Python): Use JSON-RPC `textDocument/hover` to resolve inferred types at override sites. Use `textDocument/typeDefinition` to walk the type hierarchy and compare parameter/return types.
2. **rust-analyzer** (Rust): Trait implementation checks via `textDocument/inlayHint` and `workspace/symbol`.
3. **Eclipse JDT / IntelliJ LSP** (Java): Use `textDocument/references` to find substitution sites, then verify behavioral contracts via annotation processors (e.g. `@Override` + `@NonNull` mismatches).

The integration point would be a new `lsp_solid_checks.py` module that opens a language server subprocess, sends JSON-RPC requests, and interprets the responses — separate from the syntax-only tree-sitter pipeline.
