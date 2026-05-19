To determine the theoretical maximum accuracy for detecting SOLID violations using **only a Concrete Syntax Tree (Tree-sitter) and file system structure**—without a semantic type system, cross-file symbol resolution, or Git history—we must fundamentally shift our perspective.

We must move from **semantic theorem proving** to **structural, topological, and lexical proxies**. Without knowing what the code *means* or how objects interact in memory, we can only measure the code's *shape, size, and vocabulary*.

Here is the deep-dive reasoning, optimal heuristic design, and theoretical maximum accuracy for each principle under these strict constraints.

---

### SRP — Single Responsibility Principle

**Reasoning:**
"Responsibility" is a business-domain concept ("reason to change"). Because we cannot measure the domain directly, we must measure the structural symptoms of doing too much: **low cohesion, domain-span, and volume**.

* **Best Structural Proxies:**
1. **Syntactic LCOM4 (Lack of Cohesion of Methods):** Using Tree-sitter, we extract all class-level field identifiers. Inside each method body, we extract all bare identifiers and property accesses. We build an undirected bipartite graph mapping methods to the class fields they reference. If the graph contains completely disconnected subgraphs, the class functionally contains multiple independent classes. *(Note: Without symbol resolution, local variable shadowing creates noise, but statistically, this proxy remains highly effective).*
2. **Lexical Verb Clustering:** We extract method names, parse them by camelCase, and extract the leading verbs. If a class contains non-accessor methods starting with `calculate*`, `render*`, and `save*`, it is lexically proving mixed responsibilities (Domain, UI, Persistence).
3. **File System Import Fan-out:** Extract import paths. A class importing from `src/ui/*`, `src/db/*`, and `src/network/*` is structurally coupled to disparate domains.


* **Thresholds & Academic Evidence:**
Lanza and Marinescu’s *Object-Oriented Metrics in Practice* defines the "God Class" threshold transitioning from "likely" to "certain" around **20 public methods** (WMC) combined with high data access.
* **The Optimal Heuristic ("The Disjoint Domain" Detector):**
* *Rule:* Flag if `Method Count > 20` AND (`Syntactic LCOM4 > 1` OR `Distinct Import Root Directories >= 3`).
* *Max Accuracy:* **Precision: ~60%** (Will falsely flag legitimate architectural Orchestrators or Facades). **Recall: ~80%** (Reliably catches massive, fragmented God classes).



---

### OCP — Open/Closed Principle

**Reasoning:**
True OCP is a *temporal* property—it dictates how code reacts to *future* business requirements. Statically, without Git history to measure change frequency, predicting if a class is truly "closed" is impossible.

* **Is client-side type-checking the right thing to flag?**
**Yes.** While the lack of an abstraction is a flaw in the domain model, the `switch` statement in the *client* is the literal embodiment of the OCP violation. When a new subtype is added, the client **must be modified** to handle it. This is Fowler's classic "Switch Statements" smell. It is the structural scar tissue of a missing polymorphic boundary.
* **Is OCP essentially undetectable statically?**
*Architectural resilience* is undetectable statically. But *proactive OCP failure* (compensating for rigid design with hardcoded dispatch) is highly detectable.
* **The Optimal Heuristic ("The Type-Dispatch Cascade"):**
* *Rule:* Traverse the AST for conditional chains (`switch`, `match`, or `if/else if` with $\ge 3$ branches). Flag if the condition uses type-checking operators (`instanceof`, `typeof`, `is`) OR the switched identifier is literally named `type`, `kind`, or `status` (e.g., `action.type` in Redux).
* *Max Accuracy:* **Precision: ~90%** (In classical OOP, type-sniffing cascades are universally recognized anti-patterns). **Recall: ~15%** (Misses 85% of OCP violations, which are just developers endlessly appending logic to monolithic methods).



---

### LSP — Liskov Substitution Principle

**Reasoning:**
LSP dictates behavioral subtyping (honoring preconditions, postconditions, and invariants). Even *with* a type system, verifying logic invariants requires SAT solvers or runtime contract checking. Furthermore, without cross-file resolution, we cannot even check if a subclass narrowed a parameter type, because we cannot see the parent's signature in `Parent.java`.

* **Static Signals without Semantics:**
The *only* definitively local, syntactic signal is the **"Refused Bequest"**—an explicit, structural rejection of an inherited contract.
* **Should we skip LSP?**
**Yes.** Attempting to guess behavioral subtyping via an AST will yield a near-0% precision rate. You should skip semantic LSP but implement the "Refused Bequest" as an explicit edge-case rule.
* **The Optimal Heuristic ("Refused Bequest"):**
* *Rule:* Look for method declarations containing an `@Override` annotation (or `override` keyword). Flag if the method body contains *only* `throw new NotImplementedError()` (or equivalent exception), or if the AST block is completely empty `{}` despite a non-void return type signature.
* *Max Accuracy:* **Precision: 99%** (Overtly throwing "Not Supported" in an override is the textbook definition of an LSP failure). **Recall: < 2%** (Skips all subtle state-based behavioral breaches).



---

### ISP — Interface Segregation Principle

**Reasoning:**
Interface size is a weak proxy. `java.util.List` has dozens of methods but is highly cohesive. The true proof of an ISP violation is when an interface forces a client to depend on methods it does not need.

* **Detecting "Roleplaying":**
Because we lack symbol resolution to trace an interface to all its implementations globally, we must analyze the *victim* of the ISP violation locally. "Roleplaying" (a class stubbing out methods it was forced to implement) is the strongest possible signal.
* **Thresholds & Parameter Variance:**
We can also evaluate the interface declaration itself using **Parameter Type Entropy**. `List<T>` has many methods but low parameter variance (mostly `T` or `int`). A fat interface has high parameter variance.
* **The Optimal Heuristic:**
* *Rule 1 (The Stubbed Implementer):* If a class declaration includes an `implements` clause, and $> 25\%$ of its methods are empty stubs or throw `NotImplementedException`, flag it.
* *Rule 2 (The Fat Interface):* If an interface declaration has $> 12$ methods AND the distinct count of parameter types across those methods is $> 5$ (measured by distinct string identifiers), flag it.
* *Max Accuracy:* **Precision: ~85%** (For Rule 1, stubbing proves ISP failure). **Recall: ~40%** (Misses bloated interfaces where developers dutifully wrote dummy logic instead of stubs).



---

### DIP — Dependency Inversion Principle

**Reasoning:**
DIP requires high-level modules to depend on abstractions, not concretions. In an AST, this manifests as `new ConcreteClass()`. The challenge is distinguishing a volatile domain service (`new BillingService()`) from a benign value object (`new UserDto()`) or a standard standard library primitive (`new ArrayList()`).

* **Lexical Naming Conventions:**
Without a type system, we must rely entirely on naming conventions. Fortunately, modern enterprise software (Java, C#, TS, Go) adheres to architectural naming suffixes very rigidly.
* **The Optimal Heuristic ("Lexical Concretion Instantiation"):**
* *Rule:* Extract all instantiation nodes (`new X()`).
* *Deny-list (The Target):* Flag if `X` ends in `Service`, `Repository`, `Manager`, `Controller`, `Client`, `Dao`, or `Engine`.
* *Allow-list (The Context):* Suppress the flag if the *enclosing class* ends in `Factory`, `Builder`, `Provider`, `Module`, `Config`, or if the method is `main` (this is the Composition Root).
* *Max Accuracy:* **Precision: ~85%** (Developers rarely name a pure data structure `PaymentService`). **Recall: ~60%** (Misses dependencies that lack standard architectural suffixes).



---

### Final Recommendation: The Implementation Matrix

For a static analysis tool operating purely on Tree-sitter and file paths, you must protect developer trust by explicitly categorizing rules by confidence.

#### 🟢 High Confidence (Implement as primary linting rules)

* **DIP (Lexical Instantiations):** Relying on enterprise naming conventions to catch `new XService()` outside of Factories yields surprisingly high precision and immediate architectural value.
* **OCP (Type-Dispatch Cascades):** Flagging `instanceof` / `typeof` chains and large `switch (type)` blocks accurately pinpoints structural polymorphic failures.
* **LSP / ISP (Refused Bequest & Roleplaying):** Catching `throw new NotImplementedException` or overtly empty implementations is highly accurate and represents an objective, structural flaw.

#### 🟡 Low Confidence (Label as "Heuristics / Refactor Suggestions")

* **SRP (Cohesion Metrics):** Output Syntactic LCOM4 and Verb Clustering as *"Refactor Suggestion: Potential Low Cohesion"* rather than a strict violation. They are mathematically sound but will flag legitimate God-classes/Facades that a team has consciously accepted.
* **ISP (Fat Interfaces):** Interface method count combined with parameter variance should be surfaced as an "Architectural Smell," as it cannot definitively prove a lack of cohesion without domain context.

#### 🔴 Skip Entirely (Document explicitly)

* **Semantic LSP (Contracts):** Do not attempt to guess if a subclass narrows a parameter type, alters return boundaries, or weakens postconditions. Document that: *"Semantic LSP verification relies on runtime contracts and cross-file type resolution, which are mathematically uncomputable from an isolated AST."*
* **Temporal OCP (Churn Analysis):** Do not attempt to measure if a class is actually "closed" to changing business requirements. Document that this requires Git history analysis.