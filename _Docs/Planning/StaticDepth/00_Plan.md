# Deterministic Static-Analysis Deepening — close the gaps with static analysis

> **STATUS: DELIVERED (all four workstreams merged to main).**
> - **SA1 + SA2** (Wave 1) — field/attribute/dict-key/list-index sensitivity + static resolution of
>   determinable dynamic constructs (getattr/setattr/eval/import with constant/foldable operands) +
>   constant/string propagation, across Python + CST (JS/TS/Java/Go/C). `needs_review` reserved for
>   genuinely non-determinable operands only. Adversarial review caught 1 critical mute (`_CLEARED`
>   sentinel erasing prior non-constant-index taint) — fixed + regression-tested.
> - **SA3** (Wave 2) — Steensgaard-style union-find C points-to: multi-level deref, struct-pointer
>   field aliasing, array decay, unresolved-pointer over-approximation. Adversarial review caught 1
>   critical mute (strong-update pop orphaning field taint under a stale canonical key) + 1
>   contamination bug (allocator callee name unioning independent pointers) — both fixed.
> - **SA4** (Wave 2) — call-site-sensitive summaries (context) + whitelist-only path-sensitive guard
>   clearing (only provably domain-restricting predicates: str.isdigit/isalnum/isnumeric/isdecimal,
>   isinstance(int,float), JS Number.isInteger/isFinite; joins union; unguarded keeps taint).
>   Adversarial review clean (no mute across 20+ probes).
>
> Every wave: adversarial mute-hunt review + full Security/taint/benchmark suites green + real-repo
> (Talos) scan clean. Residual `needs_review` is now only the genuinely-unbounded/attacker-controlled
> dispatch — the honest, irreducible residue, exactly as intended.
> Honest remaining ceilings: inter-procedural C pointer flow (intra-procedural only); SA4 guard
> clearing is Python/JS-only (Java/Go/C get sound branch-join, no guard narrowing) — both sound
> (never mute), just less precise; documented in code + manifests.

---


Asgard is a deterministic static tool. The prior "needs review / opt-in layers" framing over-conceded:
most of what was punted is resolvable with established, deterministic static techniques. This plan
pushes the taint/dataflow engine toward CodeQL/Infer/SVF-class precision. The opt-in LLM/runtime layers
stay (merged, harmless, off by default) but are NOT the answer to these gaps — static is.

## The honest boundary (what stays irreducible, and why it's not a cop-out)
- **Rice's theorem**: no static analysis is both sound (no FN) and complete (no FP) for non-trivial
  semantic properties. We therefore do *sound over-approximation* with honest confidence — deterministic,
  reproducible, never a guess. "close all gaps" = maximize the deterministic engine, not achieve perfection.
- **Runtime VALUES of external input** are unknowable statically — but taint doesn't need them
  (untrusted-source → sink is fully static). No gap for the core mission.
- **Truly-unbounded dynamic dispatch** (`obj[fullyAttackerControlled]()` with no determinable target set):
  the deterministic finding is "attacker controls the dispatch target" (a real vuln, flagged) — we cannot
  and need not name the exact method. This is the ONLY legitimate residue of "needs review", and this plan
  SHRINKS it to only that residue by resolving everything determinable.

Everything below is deterministic (same input → same output), reproducible, and adversarially reviewed.
Acceptance = fixtures + Kairos/Talos/GAIA re-scan (real findings, not just green tests).

## SA1 — Field/attribute/container sensitivity (Wave 1)
Track taint at sub-object granularity, all languages:
- Object fields/attributes: `x.a = taint; sink(x.b)` must NOT flag; `x.a = taint; sink(x.a)` must flag.
- Dict/map keys, list/array/slice elements: `m["a"]=taint; sink(m["b"])` clean; `sink(m["a"])` flags;
  container-level over-approximation retained only when the index is non-constant (unknown index → whole
  container tainted, sound). Generalize the one-level C struct handling already present.

## SA2 — Static resolution of "dynamic" constructs (Wave 1) — directly answers "these should be static"
Resolve, don't punt, whenever the operand is statically determinable; keep "needs review" ONLY for the
genuinely-unbounded residue:
- `obj[key](...)` / `obj[key]` where `key` is a literal/const/enum → resolve to `obj.key` and continue taint.
- `getattr(o, name)` / `setattr` where `name` is a literal/const → treat as `o.name`.
- `eval("..." + CONST)` / dynamic `require(x)` / `__import__(x)` / `import(x)` where the string is a literal
  or constant-foldable → resolve the constructed value; analyze/attribute accordingly (a constant `require`
  is a normal import, NOT a finding). Only a NON-determinable operand stays DYNAMIC_CONSTRUCT/needs-review,
  and a TAINTED operand is a concrete injection finding (already handled).
- Constant/string propagation pass to support the above (fold literal concatenation, const bindings, enums).

## SA3 — C points-to analysis (Wave 2)
Replace "points-to lite" with a real (Steensgaard unification-based, near-linear, deterministic) points-to
so multi-level pointer taint and aliasing follow soundly: `char *p = buf; char **pp = &p; ... system(*pp)`;
struct-pointer field aliasing; array-decay. Honestly bound inter-procedural pointer flow; document residue.

## SA4 — Context- & path-sensitivity (Wave 2)
- Context-sensitivity: call-site-sensitive summaries (k-CFA-lite / bounded call-string) so a helper that's
  clean on one call site and sinking on another isn't conflated — cuts FPs from flow-insensitive merging.
- Path-sensitivity for the common guard patterns: `if (isValid(x)) sink(x)` vs `if (!isValid(x)) return; sink(x)`
  — model sanitizer/validator guards so a proven-guarded path clears and an unguarded path flags, without the
  sticky-over-approximation FP. Straight-line strong updates already partly done; generalize to branch joins
  with a sound meet.

## Orchestration
Sequential (all touch the one taint/dataflow subsystem — parallel would collide):
- **Wave 1**: SA1 + SA2 in one coherent slice (field-sensitivity + dynamic resolution + constant prop — they
  interlock). Adversarial review (does field-sensitivity MUTE a real cross-field flow? does dispatch resolution
  wrongly resolve-and-clear a tainted-key case?). Merge.
- **Wave 2**: SA3 (C points-to) then SA4 (context/path-sensitivity). Adversarial review each. Merge.
- After each wave: CLI-surface check + Kairos/Talos/GAIA re-scan. Then merge to main + push.
This is iterative: each wave is a real, testable deterministic precision gain. "Needs review" shrinks to the
unbounded-dispatch residue only.
