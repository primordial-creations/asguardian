Transitioning a static analyzer from a purely lexical (regex) engine to a structural (AST) engine is a significant modernization effort. It offers massive improvements in Precision (fewer false positives) but risks regressions in Recall (missing true positives) if not handled systematically.

To meet your constraints—zero test breakages, backward API compatibility, an optional dependency model, and incremental rollouts—you should implement a **Strangler Fig pattern** via a **Dual-Engine Decorator**.

Here is the optimal migration strategy.

---

### 1. Migration Order & Prioritization

Do not migrate language-by-language indiscriminately. Prioritize based on **AST Return on Investment (ROI)**: where syntax fragility causes regex to fail the most.

**Language Priority:**

1. **Pilot: Python.** Your analyzer is built in Python. Bootstrapping the bindings and test harness here is the easiest way to validate the architecture. Furthermore, Python's multi-line strings, decorators, and list comprehensions frequently break regex boundaries.
2. **Highest ROI: JavaScript / TypeScript.** JS/TS syntax is notoriously hostile to regex. Arrow functions, inline JSX, multi-line template literals, and nested anonymous callbacks cause massive False Positive (FP) rates.
3. **High Value: Java / C#.** Verbose, highly structured languages where distinguishing between method declarations, invocations, and annotations is trivial for an AST but impossible for regex.
4. **Moderate Value: Go, PHP, Ruby.** Go is strictly formatted (via `gofmt`), making regex surprisingly effective. Migrate these based on specific user demand.
5. **Lowest ROI: C++ / Rust.** C/C++ macros are notoriously difficult for Tree-sitter to parse without a preprocessor. Rust's strictness makes regex "good enough" for most checks. Migrate these last, or not at all.

**Rule Priority (Within a Language):**

* **High Priority:** Injection flaws (SQLi, Command Exec) where regex cannot differentiate between a safe string literal, a comment, and an executable variable.
* **Low Priority:** Simple exact-match deprecations or keyword searches.

---

### 2. Coexistence Pattern & Architecture

To maintain the exact `analyze()` API and allow incremental execution, implement a **Decorator-driven Coexistence Pattern**.

Parsing an AST for every single rule will destroy performance. Instead, your internal file-loop in `analyze()` should parse the file *once*, passing the tree down via `kwargs`. The decorator intercepts this and routes execution.

**The Architecture (`core/ast_engine.py`):**

```python
import functools
import logging

logger = logging.getLogger(__name__)

# Modern Tree-sitter (>= 0.22) uses pip-installable languages
try:
    import tree_sitter
    import tree_sitter_python
    TS_AVAILABLE = True
except ImportError:
    TS_AVAILABLE = False

def with_ast_fallback(language_name: str, ast_func):
    """Decorator to try AST implementation, gracefully falling back to Regex."""
    def decorator(regex_func):
        @functools.wraps(regex_func)
        def wrapper(file_path, lines, enabled, **kwargs):
            if not enabled: return []
            
            # 1. Attempt AST analysis if dependency is present
            if TS_AVAILABLE:
                tree = kwargs.get("ast_tree")
                source_bytes = kwargs.get("source_bytes")
                
                # If tree wasn't passed by analyze(), parse it locally
                if not tree:
                    source_bytes = "\n".join(lines).encode('utf-8')
                    # Pseudo-code: fetch the language parser dynamically
                    parser = get_parser(language_name) 
                    tree = parser.parse(source_bytes)
                
                try:
                    return ast_func(file_path, tree, source_bytes)
                except Exception as e:
                    logger.debug(f"AST failed for {regex_func.__name__} on {file_path}: {e}. Falling back to Regex.")
            
            # 2. Fallback to legacy Regex
            return regex_func(file_path, lines, enabled)
        return wrapper
    return decorator

```

**Implementation Example (`_python_rules.py`):**

```python
def _check_eval_ast(file_path, tree, source_bytes) -> List[Finding]:
    # Use Tree-sitter's Lisp-like query DSL for high-performance matching
    query = PYTHON_LANG.query('(call function: (identifier) @func (#eq? @func "eval"))')
    findings = []
    for node, _ in query.captures(tree.root_node):
        # Tree-sitter is 0-indexed for rows, your Findings are likely 1-indexed
        findings.append(Finding(id="PY-EVAL", line=node.start_point[0] + 1))
    return findings

@with_ast_fallback("python", _check_eval_ast)
def check_eval(file_path, lines, enabled, **kwargs) -> List[Finding]:
    # Legacy regex logic remains entirely untouched here
    ...

```

---

### 3. Test Strategy & Measuring Improvement

You have ~350 unit tests. You must ensure the AST catches everything the regex caught (Recall) while eliminating the false positives (Precision).

**Step 1: Guarantee Zero Regressions (The Parametrization)**
Use `pytest.mark.parametrize` to run your entire existing test suite against both engines. Both must pass identically.

```python
@pytest.fixture(params=["regex", "ast"])
def engine_mode(request, monkeypatch):
    monkeypatch.setattr('core.ast_engine.TS_AVAILABLE', request.param == "ast")
    return request.param

def test_legacy_suite(engine_mode):
    # Runs 700 times (350 * 2). Guarantees AST doesn't drop existing findings.
    ...

```

**Step 2: Measure Precision / Recall (The Benchmark Suite)**
Create a separate `benchmarks/` directory populated with heavily annotated files (similar to OWASP/Bandit fixtures) designed to break regex.

```javascript
// ruleid: JS-EVAL (Both Regex and AST must catch this)
eval(userInput);

// ok: JS-EVAL (Regex fails/flags this, AST must correctly ignore it)
console.log("Never use eval(userInput) in production");

```

**The Acceptance Gate:** A PR migrating a rule to AST is only merged if `Recall(AST) >= Recall(Regex)` AND `Precision(AST) > Precision(Regex)`.

---

### 4. The "Good Enough" Threshold

Tree-sitter introduces parsing overhead. **Do not waste cycles migrating all 80 rules.** Keep the Regex implementation permanently if a rule meets these criteria:

1. **Lexical Secrets:** Finding API keys, passwords, or exact certificates (`-----BEGIN RSA PRIVATE KEY-----`). ASTs treat strings as opaque blobs anyway. Regex is vastly superior for string scanning.
2. **Comment / Metadata Parsing:** Searching for `TODO`, checking license headers, or parsing flat `.env` files.
3. **Simple Exact Matches:** If the vulnerability is triggered by a unique token without context (e.g., detecting `import telnetlib` in Python), regex is $O(N)$ and effectively 100% precise.

*Decision Matrix:* Only migrate if the regex rule historically triggers FPs due to multi-line wrapping, comments, string literals, or variable scoping.

---

### 5. Rollout & Graceful Degradation

**Distribution via Optional Extras:**
Because Tree-sitter historically relied on C-extensions (though newer versions ship wheels), make it an optional extra in your `pyproject.toml` to prevent breaking minimal CI/CD Docker containers.

```toml
[project.optional-dependencies]
ast = ["tree-sitter>=0.22", "tree-sitter-python", "tree-sitter-javascript"]

```

**Graceful Degradation User Experience:**
When a user invokes `analyze(scan_path)`:

1. Check for `TS_AVAILABLE`.
2. If missing, the scan continues exactly as it did yesterday, but prints a *single, prominent* startup message:
> `ℹ️ INFO: Running in standard Regex mode. For higher precision and fewer false positives, enable the AST engine: pip install 'my_analyzer[ast]'`


3. Users explicitly opt-in to the new capability, guaranteeing zero unexpected build breakages for existing users.

---

### 6. Concrete Migration Plan

#### Phase 1: Infrastructure & Python Pilot (Weeks 1-2)

* **Goal:** Establish the architecture, ensure zero regression, and prove ROI.
* **Actions:** Implement the `@with_ast_fallback` decorator, update `pytest` to parameterize all existing tests, and build the `benchmarks/` script. Migrate 3 to 5 complex **Python** rules (e.g., `exec()`, `subprocess.Popen` with multiline args).
* **Success Criteria:** Existing 350 tests pass. Python rules show equal Recall and >20% better Precision on benchmarks.

#### Phase 2: High-Value Expansion (Weeks 3-5)

* **Goal:** Drastically reduce overall analyzer noise by tackling the hardest languages.
* **Actions:** Hook up the `tree-sitter-javascript` package. Migrate all DOM-manipulation, injection, and arbitrary execution rules for **JavaScript/TypeScript** and **Java**.
* **Success Criteria:** JS/TS False Positive rates drop significantly in benchmark testing. End-to-end total scan time does not degrade noticeably.

#### Phase 3: Long-Tail & Pruning (Weeks 6-8)

* **Goal:** Complete the hybrid transition.
* **Actions:** Evaluate Go, C#, PHP, and Ruby. Explicitly tag remaining Regex rules with a comment like `# AST-Migration-Skipped: Regex optimal (Token match)`.
* **Success Criteria:** The core engine is functionally AST-first for complex analysis, while retaining blazing-fast regex for simple lexical checks. The API remains entirely backward compatible and users can upgrade via `[ast]` gracefully.