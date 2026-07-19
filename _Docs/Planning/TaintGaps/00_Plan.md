# Closing the Remaining Taint/Detection Gaps — Plan

Two classes of gap. Class A is closeable engineering. Class B is the fundamental
static-analysis ceiling — not closeable by more static analysis; addressed by
**surfacing** the construct as "needs review" and by **opt-in complementary layers**.
Every security-touching workstream gets an adversarial review before merge, and the
acceptance test is a re-scan of Kairos/Talos/GAIA + fixtures — real findings, not just green tests.

Overriding invariants (from `ASGARD_UPLIFT_GOAL.md`): never mute a real flow; unresolved ≠ safe
(over-approximate); severity ⊥ confidence; nothing network-bound in the DEFAULT path (new
network/LLM layers are strictly opt-in); honest labeling.

---

## WS1 — Whole-project inter-procedural taint (Class A) — HIGH VALUE
**Gap:** cross-file taint is directory-scoped; a call into a helper in a *sub*directory is
not resolved (over-approximated). Plan-04 §D.4 (project-wide index + persistent cache) was deferred.
**Approach:** replace the per-directory `SummaryIndex` build in `dispatch.py` with a
project-rooted index: discover the project root (nearest `.git`/`package.json`/`go.mod`/`pom.xml`,
else the scan root), build/reuse a `SummaryIndex` over ALL same-language files under it, with a
persistent on-disk cache under `.asgard_cache/` keyed by per-file content hash (invalidate only
changed files). Bound total indexed files (configurable, e.g. 5000) and hops (k≤4) to prevent
blowup; log when truncated. Resolution across directories must resolve; unresolved still
over-approximates (×0.5), never a confident clean.
**Acceptance:** `a/main.js` → helper in `b/sub/util.js` flags; second run reuses cache (assert no
rebuild); a 3-file cross-package chain flags; perf bound holds on a 1000-file synthetic tree.
**Owns:** `Heimdall/Security/TaintAnalysis/` (summaries/engine) + `Security/engine/dispatch.py`.

## WS2 — C pointer aliasing + mutating-source follow (Class A)
**Gap:** C taint is identifier-only — `char *p = buf; system(p)` after `fgets(buf,...)` is missed;
struct-field/pointer indirection not modeled.
**Approach:** intra-procedural points-to lite: track simple pointer aliases (`T* p = buf;`,
`p = &x;`, `p = arr;`) in the CST visitor's env so a tainted buffer propagates to its aliases;
follow one level of struct-field taint (`s.field = tainted; sink(s.field)`); extend the
mutating-source model to taint through a pointer alias of the destination. Honestly document the
ceiling (no full alias analysis, no inter-procedural pointer flow).
**Acceptance:** the `char *p = buf; fgets(buf,...); system(p)` case flags; a genuinely-unaliased
safe case stays clean; document residual FN. **Adversarial review.**
**Owns:** `TaintAnalysis/` (C parts of visitor/catalog).

## WS3 — Alias/summary completeness (Class A)
**Gap:** JS destructured function params (`function f({a,b})`) contribute no tracked param;
Java wildcard imports (`import java.util.*`) produce no alias entries; alias reassignment untracked.
**Approach:** handle object/array destructuring patterns in param extraction (summaries + visitor);
expand Java `.*` wildcard imports to a package prefix so member calls resolve to the package; note
reassignment stays over-approximating (safe). Small, high-precision.
**Acceptance:** destructured-param helper flags cross-function; a `java.util.*` member sink resolves.
**Owns:** `TaintAnalysis/cst_alias.py` + visitor/summaries. (Bundle with WS1's owner to avoid collision.)

## WS4 — Go/C precision hardening (Class A)
**Gap:** Go SQL placeholder detection is textual (`?`/`$N` substring) not query-shape/arg-count aware;
C format-arg index is a fixed table.
**Approach:** make Go SQL parameterization detection count placeholders vs trailing args (flag only
when tainted data is concatenated into the query string, robust to a literal containing a stray `?`);
generalize the C format-family handling. Reduce FPs without muting concat TPs.
**Acceptance:** parameterized Go with a `?` inside a string literal + concatenated taint elsewhere
still flags; correct parameterized stays clean. **Adversarial review (FP/mute balance).**
**Owns:** `TaintAnalysis/catalog/` (bundle with WS2 owner).

## WS5 — Dynamic-construct surfacing (Class B → honest "needs review") — HIGH VALUE
**Gap (fundamental):** reflection / dynamic dispatch / `eval` / dynamic `require`/`import` /
metaprogramming are undecidable for static taint — currently a SILENT blind spot.
**Approach:** do NOT pretend to resolve them. DETECT them and emit an explicit finding class
`DYNAMIC_CONSTRUCT` / confidence bucket "needs review" when a dynamic sink is reached (esp. with any
tainted operand): JS `eval(x)`/`new Function(x)`/`obj[userKey](...)`/`require(userVar)`;
Python `eval`/`exec`/`getattr(o, userinput)(...)`/`__import__(userVar)`/`pickle` of dynamic;
Java `Method.invoke`/`Class.forName(userVar)`/reflection; Go `reflect.*`. Severity from the sink's
worst-case CIA impact, confidence explicitly LOW/"needs review" (never certain — we can't prove it).
This converts silent misses into surfaced uncertainty — the honest closure.
**Acceptance:** `eval(req.query.x)` → a `needs-review` DYNAMIC_CONSTRUCT finding; `obj[k]()` with
tainted `k` flagged; a static-safe `eval("1+1")` (constant) NOT flagged. **Adversarial review.**
**Owns:** `TaintAnalysis/catalog` + visitor + Python taint (bundle with WS2/WS4 owner).

## WS6 — LLM-assisted triage layer (Class B complement) — OPT-IN
**Gap:** the "possible"/"needs-review" bucket has residual FPs and static can't judge semantic
sanitizers/business logic. **Approach:** a strictly OPT-IN (`--assist`/`enable_assist=True`,
default OFF, zero network by default) pluggable LLM-adapter layer that takes low-confidence /
needs-review findings + code context and returns a triage verdict (likely-real / likely-FP /
needs-human) with rationale — advisory only, NEVER auto-suppresses a finding, NEVER raises severity,
only annotates and can re-rank. Adapter is provider-agnostic (interface + a Claude adapter using the
Anthropic SDK per the claude-api reference; no key hardcoded; offline/mock in tests). Consult the
`claude-api` skill for model ids/SDK usage before writing the adapter.
**Acceptance:** default scan makes zero LLM/network calls (asserted); opt-in path annotates a
needs-review finding via a MOCKED adapter; a network/opt-in failure degrades to "not triaged", never
drops a finding. **Adversarial review (default-path leak + never-auto-suppress).**
**Owns:** new `Heimdall/Security/triage/` + a thin annotate hook; independent module.

## WS7 — Runtime/IAST hook interface (Class B complement) — INTERFACE + design
**Gap (fundamental):** static can't see runtime dispatch/config/external data. Full IAST is a
separate product. **Approach:** deliver the INTERFACE + design, not a full agent: a documented
`RuntimeObservation` schema (source→sink events with stack/trace ids) and an ingestion hook that
merges runtime-confirmed flows into a report (confidence "confirmed-at-runtime") and can confirm or
raise static findings; a reference offline replay loader (JSON of observations) + tests; a design doc
for how a language-specific runtime agent would emit these. No live instrumentation in this pass.
**Acceptance:** a JSON of runtime observations merges into a report and marks a matching static
finding "confirmed"; design doc present. **Owns:** new `Heimdall/Security/runtime/` + docs; independent.

---

## Orchestration
- **Wave 1 (parallel):** Agent-A = WS1+WS3 (project-wide taint index + alias completeness, core engine, adversarial review); Agent-C = WS6 (LLM triage, new module); Agent-D = WS7 (runtime interface, new module + design).
- **Wave 2 (after Agent-A merges, same TaintAnalysis subsystem):** Agent-B = WS2+WS4+WS5 (C pointer aliasing + Go/C precision + dynamic-construct surfacing, adversarial review).
- Then: consolidated CLI surfacing for any new finding classes/flags; full gate; Kairos/Talos/GAIA re-scan for the delta; merge to main + push.
