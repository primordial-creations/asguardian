Here is a comprehensive design for a language-agnostic Import Graph Analysis System that enforces architectural boundaries using static file analysis, Tree-sitter ASTs, and mathematical constraint propagation.

---

### 1. Configuration Model (YAML)

To operate without in-code annotations, the system uses a declarative schema that maps architectural intent to file system heuristics.

Architectures are modeled as **Concentric Levels** (integers). Level `0` is the innermost core (Domain), and Level `N` is the outermost shell (Infrastructure). The fundamental architectural rule is: **Dependencies must point inward or laterally ($Level_{Source} \ge Level_{Target}$)**.

```yaml
# arch-enforcer.yaml
architecture:
  name: "Clean Architecture"
  dependency_direction: "inward" # Outer layers depend on inner layers

layers:
  - name: Domain
    level: 0
    heuristics:
      paths: ["**/domain/**", "**/core/**"]
      suffixes: ["Entity", "ValueObject", "Model"]
      
  - name: Application
    level: 1
    heuristics:
      paths: ["**/application/**", "**/usecases/**"]
      suffixes: ["UseCase", "Service", "Handler"]

  - name: Infrastructure
    level: 2
    heuristics:
      paths: ["**/infrastructure/**", "**/adapters/**", "**/db/**"]
      suffixes: ["RepositoryImpl", "Controller", "Client"]
      # External dependencies pull importing files outward into this layer
      external_imports: ["java.sql.*", "express", "gorm.io/*", "typeorm"]

rules:
  max_module_fan_out: 12
  detect_module_cycles: true

```

---

### 2. Import Graph Construction & Normalization

Different languages have wildly different concepts of modularity (Java packages, Go modules, TypeScript relative paths). Because we lack a compiler, the **Physical File** is our universal abstraction. We fold files into **Modules (Directories)** for macro-analysis.

#### Data Model

```python
class Node:
    id: str               # Absolute physical file path
    module_id: str        # dirname(id) - Used for grouping
    language: str         # e.g., "typescript", "go"
    
    # Layer Bounds
    min_level: int        # Minimum layer it must belong to (Outward gravity)
    max_level: int        # Maximum layer it can belong to (Inward gravity)
    base_level: int | None # Intrinsic level from YAML heuristics

class Edge:
    source_id: str
    target_id: str
    is_external: bool

```

#### Cross-Language Normalization Strategy

1. **Pass 1: Global File Indexing**
Walk the file system and build an in-memory dictionary of all files. Where applicable (Java/C#/Go), use Tree-sitter to parse `package` or `module` declarations at the top of the file and map the logical namespace to the physical absolute path.
2. **Pass 2: Language-Specific Path Resolvers**
Use Tree-sitter to extract raw import strings (`import`, `require`, `use`). Pass them through lightweight Language Resolvers:
* **Relative (JS/TS/Rust/Ruby)**: Resolve mathematically (`../service/User` + current file path), then probe the Global Index for extensions (`.ts`, `.js`, `/index.ts`).
* **Namespace (Java/C#)**: Convert `com.app.Domain` to a path suffix `com/app/Domain.*` and query the Global Index.
* **Module (Go/Python)**: Map the module string to physical directories. An import to a directory creates edges to all exported files within that directory.
* **External Fallback**: If the import string yields no physical local file, mark `is_external = True` and categorize it via the YAML `external_imports` array.



---

### 3. Layer Inference & Architecture Drift Algorithm

To infer layers for ambiguous files (e.g., `utils/helper.ts`) and detect files that have drifted into the wrong layer, we model the graph as a **Constraint Satisfaction Problem (CSP)**.

The universal constraint for any edge $A \rightarrow B$ is: `Level(A) >= Level(B)`.

#### Algorithm: Topological Bound Propagation

1. **Intrinsic Initialization**: Evaluate all nodes against the YAML. If a file matches a rule (e.g., `/domain/`), lock its bounds: `base_level = min_level = max_level = 0`. If no match, initialize to `min_level = 0, max_level = MAX_LEVEL`. External imports are anchored to their configured YAML level.
2. **Iterative Propagation**: Loop through the graph until `min` and `max` bounds stop changing.
* **Rule 1 (Outward Gravity)**: A file must be *at least* as external as the most external thing it imports.

$$A.min\_level = \max(A.min\_level, B.min\_level)$$


* **Rule 2 (Inward Gravity)**: A file can be *at most* as internal as the most internal thing that imports it.

$$B.max\_level = \min(B.max\_level, A.max\_level)$$





#### Assigning Confidence & Detecting Drift

Once the graph stabilizes, we evaluate the bounds of every node:

* **Perfect Match ($min == max$)**: `Confidence = 100%`. Layer is assigned.
* **Ambiguous ($min < max$)**: The file acts as a bridge and sits in a valid range. `Confidence = 1 - ((max - min) / MAX_LEVELS)`. We assign it to $min$ (the lowest valid layer).
* **Architecture Drift Detection ($min > max$)**: **Paradox Detected.**
If a file physically resides in `Domain` (anchoring `max_level = 0`), but imports a Database driver (propagating `min_level = 2`), the bounds cross. $2 > 0$ triggers a Drift Violation:
> *"File `UserRepository.ts` intrinsically looks like Domain (Layer 0) but acts structurally as Infrastructure (Layer 2) due to its dependency on `gorm.io`."*



---

### 4. Violation Detection Algorithms

With the graph mathematically leveled, detecting architectural rule violations becomes deterministic graph traversal.

#### A. Layer Violations

* **Algorithm**: $O(|E|)$ iteration.
* **Logic**: For every edge `A -> B` where both are local files, check if `A.inferred_layer < B.inferred_layer`.
* **Note**: Dependency Inversion (IoC) is naturally supported. If `UserRepoImpl` (Level 2) implements `UserRepoInterface` (Level 0), the physical import is Level 2 $\rightarrow$ Level 0, which correctly validates as $2 \ge 0$.

#### B. Circular Dependencies

File-level cycles inside the same directory are often benign (e.g., mutually recursive types). We detect architectural cycles at the **Module Level**.

* **Algorithm**: Tarjan’s Strongly Connected Components (SCC).
* **Logic**: Collapse the `FileGraph` into a `ModuleGraph` by grouping nodes by their `module_id` (directory). Add a directional edge between Module $M_1$ and $M_2$ if *any* file in $M_1$ imports a file in $M_2$. Run Tarjan's on this Module Graph. Any component where $|SCC| > 1$ represents a circular package dependency.

#### C. Fan-Out Detection

To avoid penalizing files that import many tiny utilities from the *same* package, we calculate Fan-Out based on unique target modules.

* **Algorithm**: Degree Centrality.
* **Logic**: `fan_out = len(set([edge.target.module_id for edge in node.outgoing]))`. If this exceeds `max_module_fan_out`, emit a warning.

---

### 5. Incremental Analysis

Re-parsing thousands of files on every keystroke is unviable. The system maintains graph state in an IDE daemon or `.cache` file, performing targeted updates when a single file, $F$, is modified.

1. **Graph Mutation (O(1))**: Load the cached graph. Delete all *outgoing* edges from $F$. (Incoming edges remain valid, as they belong to the ASTs of the files importing $F$).
2. **Delta Parse (O(1))**: Run Tree-sitter only on $F$. Run the Language Path Resolvers to create new outgoing edges.
3. **Local Propagation (Sub-graph)**: Add $F$ to a Worklist Queue. Recalculate its $min$ and $max$ bounds based on the new edges. If $F$'s bounds change, push $F$'s neighbors into the Queue. Because `max()` and `min()` are monotonic, this localized wave stabilizes almost instantly, touching only affected semantic neighbors.
4. **Targeted Violation Checks**:
* *Layer Checks*: Check the `A >= B` rule *only* on the newly added outgoing edges of $F$.
* *Cycle Checks*: Do not re-run Tarjan's SCC globally. Perform a **Depth-First Search (DFS)** starting from the target modules of $F$'s new edges. If the DFS can reach $F$'s module, a new architectural cycle was introduced. Complexity drops to the localized, reachable subgraph.