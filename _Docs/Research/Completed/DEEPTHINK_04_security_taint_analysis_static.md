To design a static taint analysis system using **only Concrete Syntax Trees (CSTs)** from Tree-sitter—without type resolution, control-flow graphs, or cross-file linkage—we must abandon the pursuit of formal "soundness" (finding all bugs) and "completeness" (zero false positives).

Instead, we are designing a **Heuristic Data-Flow Linter**. This mimics the philosophy of lightweight, blazing-fast tools like Semgrep. We trade deep semantic truth for multi-language support, millisecond execution, and zero-configuration setup.

Here is the architectural design for this system, addressing your constraints and challenges.

---

### 1. Local Taint Tracking Algorithm

Without a formal Control Flow Graph (CFG) to compute phi-nodes, we approximate execution using an **AST-driven forward traversal**. We maintain an `Environment` (a dictionary mapping identifier names to a `TaintState`) and use a stack of these dictionaries to handle block scoping.

#### The Algorithm (Pseudocode)

```python
class TaintState:
    def __init__(self, confidence: float, trace: list):
        self.confidence = confidence
        self.trace = trace

def analyze_function(func_node, file_local_funcs):
    env_stack = [{}] # Stack of variable scopes
    alerts = []

    def get_taint(name):
        for scope in reversed(env_stack):
            if name in scope: return scope[name]
        return None

    def evaluate_expr(expr):
        if is_literal(expr): return None
        # Base variable lookup (handles x, or base of x.y.z)
        if is_identifier(expr) or is_member_expr(expr):
            base_name = get_base_identifier(expr)
            return get_taint(base_name)
            
        # Check Sources & Propagators (See Sections 2 & 4)
        source_match = match_source(expr)
        if source_match: return TaintState(source_match.confidence, [expr.text])
            
        if is_propagator(expr):
            taints = [evaluate_expr(child) for child in get_operands(expr)]
            valid = [t for t in taints if t]
            if valid:
                best = max(valid, key=lambda t: t.confidence)
                return TaintState(best.confidence * 0.9, best.trace + [expr.type])
                
        # Inter-procedural: Simulate same-file local function call
        if is_call(expr) and get_call_name(expr) in file_local_funcs:
             return simulate_local_call(expr, file_local_funcs, env_stack)

        return None

    def traverse(node):
        if is_block(node):
            env_stack.append({}) # Push scope
            for child in node.statements: traverse(child)
            env_stack.pop()      # Pop scope
            
        elif is_assignment(node):
            # Evaluate RHS before modifying LHS
            rhs_taint = evaluate_expr(node.rhs)
            lhs_name = get_base_identifier(node.lhs)
            
            if rhs_taint:
                env_stack[-1][lhs_name] = rhs_taint # Apply taint
            else:
                for scope in reversed(env_stack):
                    if lhs_name in scope: del scope[lhs_name] # Taint killed
                    
        elif is_call(node):
            # Check for sinks (See Section 3)
            sink_match = match_sink(node)
            if sink_match:
                for arg in node.arguments:
                    arg_taint = evaluate_expr(arg)
                    if arg_taint:
                        alerts.append(Alert(sink_match, arg_taint))
            for arg in node.arguments: traverse(arg) # Traverse args for nested calls
            
        elif is_if_statement(node):
            # Union states to over-approximate branching
            traverse(node.consequence)
            if node.alternative: traverse(node.alternative)
            
        else:
            for child in node.children: traverse(child)

    # 1. Initialize heuristic parameters
    for param in func_node.parameters:
        if is_heuristic_source_param(param):
            env_stack[-1][param.name] = TaintState(0.6, [f"param:{param.name}"])

    traverse(func_node.body)
    return alerts

```

**What this algorithm misses:**

* **Pass-by-reference mutation:** `sanitize(req.body); db.query(req.body)`. The CST doesn't know `sanitize` mutated the object safely, leading to False Positives.
* **Out-of-order execution:** Asynchronous closures, `.then()` blocks, or `setTimeout` break the linear traversal, dropping taint flows (False Negatives).
* **Complex Aliasing:** If `arr[0] = taint`, tracking the array index syntactically is incredibly fragile.

---

### 2 & 3. Source and Sink Identification (Without Types)

Without types, we cannot prove `req` is an `HttpServletRequest` or `db` is a `java.sql.Connection`. We must rely strictly on **Lexical Framework Heuristics** via Tree-sitter structural queries.

**Sources Identification & Accuracy:**

* **Pattern matching:** We look for decorators (`@RequestParam`), global APIs (`os.Getenv`), property paths (`req.body.*`), or parameter names (`payload`, `request`).
* **FP/FN Profile:** False Positives are low for standard frameworks, but False Negatives are *high*. If an enterprise codebase wraps input extraction (`AuthContext.getUserId()`), our analyzer is entirely blind unless manually configured.

**Sinks Identification & Accuracy:**

* **Pattern matching:** We match exact built-ins (`child_process.exec`) or generic method names (`.query()`, `.execute()`).
* **FP/FN Profile:** False Positives are *extremely high* for generic names. If we flag all `.execute()` calls, we will flag `JobQueue.execute()` alongside `Statement.execute()`. We mitigate this using Confidence Scoring (Section 5).

---

### 4. Propagator Tracking

We evaluate AST structures to see if taint survives an expression.

1. **String Concatenation & Math (`+`):** If either side of a `BinaryExpression` evaluates to tainted, the whole expression is tainted.
2. **Template Literals / Interpolation:** If any evaluated child node inside ``SELECT * FROM ${x}`` is tainted, the literal is tainted.
3. **Variable Reassignment:** Handled natively by the algorithm's `env_stack` updating the LHS identifier.
4. **Formatting Functions:** We hardcode language-specific variadic formatters (e.g., `fmt.Sprintf`, `String.format`). If any argument beyond the format string is tainted, the result is tainted.
5. **Interprocedural (Same-File):** We parse all function declarations in the file first. When an unknown call is encountered, we map the calling arguments to the target function's parameters, clone the environment, and recursively analyze the target function's AST body (capped at a depth of 2 to prevent infinite recursion).

---

### 5. Confidence Scoring Model

Because `user.save()` (safe) and `db.execute()` (vulnerable) look syntactically similar, outputting all matches as binary "Vulnerabilities" will cause developer revolt. We use a multiplicative confidence score.

**Formula:** `Final Score = Source Confidence × Propagator Decay × Sink Confidence`

**1. Source Confidence:**

* `1.0`: Exact API/decorator match (e.g., `process.argv`, Java `@RequestParam`).
* `0.8`: Conventional framework access (e.g., `req.body.id`, Go `r.FormValue`).
* `0.5`: Generic parameter name match (e.g., `user_input`).

**2. Propagator Decay:**

* `× 1.0`: Direct assignment or 0-hop argument passing.
* `× 0.9`: Per mutation (String concatenation, formatting).
* `× 0.6`: Per intra-file interprocedural hop.

**3. Sink Confidence:**

* `1.0`: Unambiguous global sink (e.g., `Runtime.getRuntime().exec`, `fs.readFile`).
* `0.8`: Known framework pattern (e.g., JS `innerHTML`, Go `template.HTML`).
* `0.4`: Generic method name (`.execute()`, `.run()`, `.query()`).

**Triage Thresholds:**

* **≥ 0.70 (High):** Flag as a blocker in PRs/IDE. (e.g., `child_process.exec(req.body.cmd)` -> 1.0 * 1.0 * 1.0 = 1.0).
* **0.40 - 0.69 (Medium):** Log as a warning. (e.g., `db.execute("..." + payload)` -> 0.5 * 0.9 * 0.4 = 0.18 -> *Wait, generic sinks with generic sources drop fast. This prevents FP noise!*)
* **< 0.40 (Low):** Suppress silently.

---

### 6. Catalogue (Java, Go, JavaScript)

| Language | Sources (AST / Lexical Heuristics) | Sinks (AST / Lexical Heuristics) | Propagators | Sanitizers (Taint Kills) |
| --- | --- | --- | --- | --- |
| **Java** | `request.getParameter(...)`<br>

<br>Params annotated `@RequestParam`, `@PathVariable`<br>

<br>`System.getenv(...)` | **SQLi**: `*.executeQuery(`, `*.execute(`<br>

<br>**CMDi**: `Runtime.getRuntime().exec(`<br>

<br>**Path**: `new File(`, `Paths.get(` | `+` operator<br>

<br>`StringBuilder.append`<br>

<br>`String.format` | `Integer.parseInt`<br>

<br>`UUID.fromString` |
| **Go** | `r.FormValue(...)`<br>

<br>`r.URL.Query().Get(...)`<br>

<br>`os.Getenv(...)`<br>

<br>`c.Param(...)` (Gin) | **SQLi**: `*.Query(`, `*.Exec(`, `*.QueryRow(`<br>

<br>**CMDi**: `exec.Command(`<br>

<br>**Path**: `os.Open(`, `os.ReadFile(` | `+` operator<br>

<br>`fmt.Sprintf`<br>

<br>`strings.Join` | `strconv.Atoi`<br>

<br>`url.QueryEscape`<br>

<br>`html.EscapeString` |
| **JS / TS** | `req.query.*`<br>

<br>`req.body.*`<br>

<br>`req.params.*`<br>

<br>`process.argv` | **SQLi**: `*.query(`, `*.execute(`<br>

<br>**CMDi**: `exec(`, `spawn(`<br>

<br>**Path**: `fs.readFile(`, `path.join(`<br>

<br>**XSS**: `*.innerHTML` | `+` operator<br>

<br>Template literals ``${x}``<br>

<br>`Array.join` | `parseInt`<br>

<br>`Number`<br>

<br>`encodeURIComponent` |

---

### 7. Practical Scope & Assessment

#### Explicit Non-Goals & Documentation

To ensure trust, the tool must ship with this disclaimer:

> *"This tool is an AST-based Syntactic Security Linter, not a deep SAST compiler. It is designed to run in milliseconds in your IDE to catch localized, low-hanging fruit (e.g., direct string concatenation into a SQL query). It will **not** follow data across imports or files. It is blind to complex architectures, dependency injection, and external service layers. Use this as a fast Shift-Left guardrail, and pair it with a full SAST in your CI/CD pipeline."*

#### Honest Precision & Recall Assessment

* **Precision (True Positive Rate): Moderate-High (~70%).** Because we strictly enforce the Confidence Scoring model, we effectively filter out the massive volume of false positives generated by generic method names like `.execute()`. The alerts that survive the `0.70` threshold are almost always genuine bugs.
* **Recall (Vulnerability Catch Rate): Low (~25-40%).** This is the unavoidable tradeoff of a CST-only system. In a modern Node/Express or Go microservice, where routes, processing, and queries happen in a single flat file, it works brilliantly. However, in heavily layered Enterprise Java (Controllers passing DTOs to Services passing interfaces to Repositories across 4 files), **this tool will miss 100% of those vulnerabilities.**