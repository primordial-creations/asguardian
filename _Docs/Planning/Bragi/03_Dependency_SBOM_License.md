# Plan 03 — Dependencies: Graph Intelligence, SBOM Fidelity, License Compliance

**Priority: P1** — Dependencies is Bragi's second pillar and currently the most mechanically buggy; it also feeds Plan 01 (license gate) and Plan 02 (Exposure Factor centrality).
**Research basis:** `_Docs/Research/Bragi/Completed/RESEARCH_18` (library/dependency anti-patterns, FQN resolution, deprecated-API tracking, lazy imports), `DEEPTHINK_06` (analysis-scope hierarchy: coupling is a project-wide metric), `DEEPTHINK_09` (sub-quadratic algorithms, scale tiers), `RESEARCH_15` (interface-hash invalidation for dependency graphs), `RESEARCH_02` (CBO/afferent coupling as gold-standard defect predictors; discard DIT/NOC-class metrics).

---

## 1. Rationale (what the research says)

- RESEARCH_02's closing recommendation: **prioritize WMC, CBO, RFC** — coupling metrics have "unparalleled predictive power" for post-release defects, but require "global import topology mapping". Bragi/Dependencies is the only module in Bragi with that topology; it must become the *service provider* of coupling/centrality data to the rest of Bragi (Plan 01 category inputs, Plan 02 Exposure Factor) rather than a standalone report.
- DEEPTHINK_06: afferent coupling (fan-in) is invisible below project-wide scope — Bragi's whole-graph `ModularityAnalyzer` is architecturally correct and should be extended, not replaced. Deep graph work belongs in the *asynchronous* tier (Plan 06), not the PR-blocking path.
- RESEARCH_18: modern dependency analysis is FQN-resolution-based, tracks **deprecated API consumption** against a target runtime version (Ruff `target-version` model, PEP 702 `@typing.deprecated`), and treats **eager import of heavyweight modules used only on rare paths** as an architectural anti-pattern (Meta/Cinder: lazy imports cut startup ~70%, memory ~40%). Bragi already has `Quality/services/lazy_import_scanner.py` and `library_usage_scanner.py`; the Dependencies module should supply them the import-graph and call-site-frequency facts RESEARCH_18 says the heuristics need (import cost × call-site frequency).
- RESEARCH_15: a persisted dependency graph must invalidate by **exported-interface hash**, not file hash, or every internal edit cascades through all dependents; SCC/cycle results and coupling metrics are the canonical "hard to incrementalize" metrics that need this treatment.
- DEEPTHINK_09: `nx.simple_cycles` enumeration is exponential in dense graphs; production systems reduce to **SCC condensation** first and report per-SCC, with targeted edge-break suggestions.

## 2. Current state (gap)

`Asgard/Bragi/Dependencies/` (models 781 lines, services ~2,900 lines):

**SBOM (`sbom_generator.py`, `_sbom_parsers.py`, `sbom_models.py`)**
- Direct dependencies only; `transitive_dependencies=0` is hardcoded even though `SBOMConfig.include_transitive` defaults to `True` — the flag is dead.
- "Version" fields carry raw specs (`>=1.0`) rather than resolved installed versions; `checksum_sha256`, `cpe`, `supplier` are always empty — the SBOM fails the basic NTIA minimum-elements bar it exists to satisfy.
- `make_purl()` normalizes `name.lower().replace("-", "_")` — **backwards**: the purl spec for `pkg:pypi` requires underscores → hyphens. Every emitted purl for a package with a hyphen is invalid.
- License lookup reads only the `License` metadata header; misses PEP 639 `License-Expression` and trove classifiers.

**License (`license_checker.py`, `license_models.py`)**
- Prohibition matching is bidirectional substring: `"gpl-3.0" in "lgpl-3.0"` → **LGPL-3.0 is flagged PROHIBITED**. Unsound for the one decision that Plan 01 wants to gate a build on.
- No SPDX expression handling (`MIT OR GPL-3.0` should be compliant via the MIT arm; today the string matches the GPL pattern). `LicenseIssueType.MULTIPLE` exists but is never emitted.
- `use_cache`/`cache_expiry_days` config promises a 7-day cache; the implementation is an in-memory dict that dies with the process. Every run re-hits `pip show` (a subprocess per package) and then pypi.org serially.
- No known-vulnerability check at all — the SBOM is generated but never cross-referenced (OSV/PyPA advisory database), and no deprecated/abandoned-package signal (RESEARCH_18's pycrypto-class problem).

**Graph (`cycle_detector.py`, `modularity_analyzer.py`, `dependency_models.py`)**
- `nx.simple_cycles()` on the full graph — exponential blowup risk on tangled codebases (DEEPTHINK_09); the DFS fallback triggers only on exceptions.
- `suggest_breaks` ranks by "source has fewest dependencies" — ignores afferent coupling and edge weight (number of imported symbols), producing suggestions that break the most-used edge as happily as the least-used.
- Cycle severity is length-based (2-cycles HIGH, longer CRITICAL); research (RESEARCH_15 God-class cascade, RESEARCH_02) says severity should follow the *reach* of the SCC (LOC and afferent coupling inside it).
- `DependencyReport.get_module()` is an O(n) list scan called in loops; no centrality percentile export (Plan 02 needs `afferent-coupling percentile` for the Exposure Factor); no persisted graph, so every consumer (cycles, modularity, layering) re-parses the codebase via its own `ImportAnalyzer` instance — three full scans for one CLI report.

## 3. Target state

### 3.1 One graph, many consumers (`DependencyGraphService`)

A single service builds the import graph once per scan and exposes:

```python
class DependencyGraphService:
    def build(scan_path) -> DependencyGraph          # cached, interface-hash invalidated
    def sccs() -> List[SCC]                          # condensation, not simple_cycles
    def centrality() -> Dict[module, CentralityInfo] # Ca, Ce, instability, pagerank, Ca percentile
    def break_suggestions(scc) -> List[EdgeBreak]    # min-weight feedback edges
```

- `CentralityInfo.afferent_percentile` is the documented input for Plan 02's Exposure multiplier and Plan 01's Maintainability cycle input.
- Cycle detection: Tarjan SCC condensation; per SCC report size, member LOC, total afferent coupling of members → severity = f(reach), not f(length). Within an SCC ≤ 12 nodes, enumerate simple cycles for display; above that, report the SCC with the top-3 minimum-weight feedback edges (edge weight = count of imported symbols × dependent count) as `EdgeBreak` suggestions.
- Persistence (RESEARCH_15): store `.asgard_cache/bragi_dep_graph.json` keyed by per-file **interface hash** (hash of sorted export names + import list, not file content). A body-only edit does not invalidate dependents' edges.

### 3.2 SBOM fidelity (`sbom_generator.py` v2)

- **Transitive resolution**: walk `importlib.metadata.distributions()` `Requires-Dist` from the declared roots to build the full installed closure; mark `is_transitive`, populate real `direct_dependencies`/`transitive_dependencies` counts. Degrade gracefully (declared-only SBOM + explicit `resolution: "declared-only"` note) when the environment lacks the packages — never silently emit a partial SBOM as if complete (DEEPTHINK_14 discipline, same as Plan 01 §3.5).
- **Resolved versions & hashes**: version from installed metadata; `checksum_sha256` from the wheel `RECORD` when available.
- **purl fix**: lowercase + `_`→`-` (with a regression test that `typing_extensions` → `pkg:pypi/typing-extensions@...`).
- **License**: read `License-Expression` (PEP 639) first, then trove classifier, then `License` header.
- Format bumps: CycloneDX 1.5 (`serialNumber`, `bom-ref` per component) and SPDX relationships (`DEPENDS_ON` edges from the resolved closure) so the SBOM encodes the graph, not just the set.

### 3.3 License policy engine (`_license_policy.py`, new)

- Normalize every observed license to an SPDX id via the existing `LICENSE_PATTERNS` (kept, ordered longest-match-first), then evaluate policy on **exact normalized ids**, never substrings.
- Minimal SPDX expression parser (`OR`/`AND`/`WITH`, parentheses): `OR` → compliant if any arm allowed (emit `MULTIPLE` info issue naming the chosen arm); `AND` → all arms must pass.
- Policy verdict enum `ALLOWED / WARN / PROHIBITED / UNKNOWN` replaces the three loose booleans on `PackageLicense` (kept as derived properties for backward compat).
- Disk cache honoring the existing config fields: `.asgard_cache/bragi_license_cache.json`, `{package: {version, license, fetched_at}}`, expiry per `cache_expiry_days`. `importlib.metadata` replaces the `pip show` subprocess; PyPI JSON only as fallback, parallelized with a bounded pool.
- Export `LicenseGateInput(prohibited_count, unknown_count)` consumed by Plan 01's gate table ("prohibited license → cap 0.69, max grade D").

### 3.4 Ecosystem health checks (new, opt-in)

Per RESEARCH_18's deprecated/abandoned-library findings:
- `vulnerability_checker.py` (new): query OSV.dev batch API with the SBOM purls (this is why the purl fix matters); offline mode consumes a pre-downloaded PyPA advisory snapshot. Findings feed Plan 01's Reliability/Security inputs with `confidence: MEASURED`.
- `_package_health.py` (new): flag known-abandoned/renamed packages (curated table seeded with the RESEARCH_18 examples: pycrypto→pyca/cryptography, etc.) and requirements pinned to yanked versions.
- Expose the import graph's call-site frequency per imported module (from `dependency_list`) so `Quality`'s lazy-import scanner can apply RESEARCH_18's dual heuristic (import cost × call-site frequency) instead of import cost alone.

## 4. Concrete file/module changes

| File | Change |
|---|---|
| `Dependencies/services/graph_service.py` (new) | `DependencyGraphService` per §3.1; owns the single `ImportAnalyzer` pass; interface-hash cache. |
| `Dependencies/services/cycle_detector.py` | Rewire onto SCC condensation; reach-based severity; weighted `suggest_breaks`. Keep public API (`detect`, `has_cycles`, `suggest_breaks`). |
| `Dependencies/services/modularity_analyzer.py` | Consume `DependencyGraphService` (no second scan); add `centrality()` passthrough with percentiles. |
| `Dependencies/models/dependency_models.py` | Add `SCC`, `CentralityInfo`, `EdgeBreak`; index `DependencyReport.modules` by dict (`get_module` O(1)); add `centrality: Dict[str, CentralityInfo]`. |
| `Dependencies/services/sbom_generator.py` + `_sbom_parsers.py` | Transitive closure, resolved versions, RECORD hashes, PEP 639, purl fix, CycloneDX 1.5/SPDX relationships, `resolution` completeness marker. |
| `Dependencies/models/sbom_models.py` | `bom_ref`, `resolution` field, `dependencies: List[Tuple[ref, ref]]` edges. |
| `Dependencies/services/_license_policy.py` (new) | SPDX normalization + expression evaluation + verdicts; disk cache. |
| `Dependencies/services/license_checker.py` | Delegate classification to `_license_policy`; parallel fetch; emit `MULTIPLE`; export `LicenseGateInput`. |
| `Dependencies/services/vulnerability_checker.py` (new) | OSV batch lookup over SBOM purls; offline snapshot mode. |
| `Dependencies/services/_package_health.py` (new) | Abandoned/renamed package table; yanked-pin detection. |

## 5. Phased implementation

1. **Phase A — correctness fixes** (small, ship first): purl direction, exact-id license matching + SPDX `OR`, `get_module` dict index. These are bug fixes with immediate user-visible impact.
2. **Phase B — graph service**: `DependencyGraphService`, SCC-based cycles, centrality percentiles; Plan 02 Phase C consumes this.
3. **Phase C — SBOM v2**: transitive closure, hashes, format bumps, completeness marker.
4. **Phase D — policy & cache**: expression parser full (`AND`/`WITH`), disk cache, parallel fetch, `LicenseGateInput` → wire Plan 01 gate.
5. **Phase E — health checks**: OSV integration (opt-in flag, network-gated), package-health table, lazy-import fact feed.

## 6. Testing considerations

- Regression: `typing_extensions`/`python-dateutil` purl round-trips; `LGPL-3.0` classified WARN **not** PROHIBITED (the substring bug, as an explicit named test); `MIT OR GPL-3.0` → ALLOWED with `MULTIPLE` info issue.
- Graph: synthetic 3-node cycle and a 50-node dense SCC fixture — assert SCC path returns in bounded time where `simple_cycles` would blow up (time-box the test); break suggestion targets the min-weight edge, not the min-out-degree source.
- Interface-hash cache: edit a function body → dependents' cached edges retained; change an export list → dependents invalidated (RESEARCH_15's TypeScript/GHC behavior, as a property test).
- SBOM: fixture venv with a known 3-level dependency chain — closure complete, `is_transitive` correct, totals match; absent environment → `resolution == "declared-only"`.
- OSV: mocked batch response (L0); one live smoke test behind a network marker (L1).
- Backward compat: existing `Asgard_Test/tests_Bragi` dependency/license/SBOM tests keep passing; `PackageLicense.is_prohibited` etc. still populated.
