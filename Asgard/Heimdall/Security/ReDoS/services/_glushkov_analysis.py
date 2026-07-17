"""
Glushkov-NFA ambiguity analysis for ReDoS detection (plan 07.2).

Replaces the "nested quantifier" line-regex heuristic (DEEPTHINK_09: ~40%
FP, "unfit") with a structural analysis of the regex's own syntax tree:

    Phase 1  Parse the pattern string into a small regex-AST (literal,
             char class, ``.``, concat, alternation, group, quantifier).
             Backreferences (``\\1``) are unsupported -> analysis aborts
             for that pattern (documented false negative, per plan).
             Lookarounds are stripped to epsilon (safe over-approximation
             per plan: they can only narrow what matches, so ignoring
             them can only make the ambiguity analysis more conservative,
             never miss a real blow-up. Flags are normalised: DOTALL
             rewrites ``.`` to "any char", IGNORECASE expands literal
             chars/classes to both cases).
    Phase 2  Position-based (Glushkov) NFA construction: every leaf
             symbol becomes a numbered "position" state; standard
             firstpos/lastpos/followpos compiler-construction algorithm
             builds a position graph without epsilon transitions, so
             states map 1:1 onto syntactic symbols (this is what makes
             ambiguity structurally visible on the graph, unlike a
             Thompson NFA).
    Phase 3  Tarjan SCC on the followpos graph.
              - EDA (Exponential Degree of Ambiguity): within one SCC, a
                position has two distinct outgoing edges (back into the
                same SCC) whose character sets overlap -- two ways to
                consume the same character while looping -> catastrophic
                O(2^n) backtracking. Severity HIGH, unconditional.
              - IDA (Ambiguous chained loops / polynomial blow-up): two
                *different* SCCs connected by a followpos edge where the
                exiting SCC's repeatable character set overlaps the
                entering SCC's -- O(n^k) blow-up. Severity LOW, and
                suppressed if the analysis finds a length guard
                dominating the match call in the source line/context
                (``len(x) < N`` or slicing) -- callers pass
                ``length_guarded=True`` for that suppression since guard
                detection requires the call-site AST, not the pattern.

Budget: analysis is O(n^2) in pattern length for followpos + SCC, capped
via ``MAX_PATTERN_LEN``; callers should also enforce the ~25ms/regex,
~100ms/file wall-clock budget from the plan (best done by the caller via
a wall-clock cutoff around ``analyze_pattern``, since pathological input
here is bounded by the same construction size, not exponential).

This module does not itself walk source files -- see
``redos_scanner.py`` for the sink extraction / call-site integration.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

MAX_PATTERN_LEN = 500


# --------------------------------------------------------------------- AST

class _Node:
    __slots__ = ("kind", "children", "charset", "lo", "hi")

    def __init__(self, kind: str, children=None, charset: Optional[FrozenSet[str]] = None,
                 lo: int = 1, hi: int = 1):
        self.kind = kind          # "lit", "concat", "alt", "star", "group"
        self.children = children or []
        self.charset = charset    # for "lit": the (possibly expanded) char set; None = wildcard
        self.lo = lo
        self.hi = hi              # -1 == unbounded


class UnsupportedPatternError(Exception):
    """Raised for backreferences or other constructs the analyzer can't model."""


class _Parser:
    """Minimal regex-syntax parser producing a `_Node` tree.

    Deliberately narrow: covers the constructs that actually drive
    catastrophic backtracking (concatenation, alternation, grouping,
    quantifiers, char classes, `.`, escapes). Anything unrecognised is
    treated as an opaque single-char literal so the parser never crashes
    on real-world patterns; only backreferences raise (documented FN).
    """

    def __init__(self, pattern: str, ignorecase: bool, dotall: bool):
        self.p = pattern
        self.i = 0
        self.n = len(pattern)
        self.ignorecase = ignorecase
        self.dotall = dotall

    def parse(self) -> _Node:
        node = self._alt()
        return node

    def _alt(self) -> _Node:
        branches = [self._concat()]
        while self._peek() == "|":
            self.i += 1
            branches.append(self._concat())
        if len(branches) == 1:
            return branches[0]
        return _Node("alt", children=branches)

    def _concat(self) -> _Node:
        parts: List[_Node] = []
        while self.i < self.n and self._peek() not in ("|", ")"):
            parts.append(self._quantified())
        if not parts:
            return _Node("lit", charset=frozenset())
        if len(parts) == 1:
            return parts[0]
        return _Node("concat", children=parts)

    def _quantified(self) -> _Node:
        atom = self._atom()
        c = self._peek()
        if c == "*":
            self.i += 1
            self._maybe_lazy()
            return _Node("star", children=[atom], lo=0, hi=-1)
        if c == "+":
            self.i += 1
            self._maybe_lazy()
            return _Node("star", children=[atom], lo=1, hi=-1)
        if c == "?":
            self.i += 1
            self._maybe_lazy()
            return _Node("star", children=[atom], lo=0, hi=1)
        if c == "{":
            m = re.match(r"\{(\d*)(,?)(\d*)\}", self.p[self.i:])
            if m:
                self.i += m.end()
                self._maybe_lazy()
                lo = int(m.group(1)) if m.group(1) else 0
                if m.group(2) == "":
                    hi = lo
                elif m.group(3):
                    hi = int(m.group(3))
                else:
                    hi = -1
                # {m,n} with m or n > 1 still repeats the SAME atom, so for
                # ambiguity purposes it behaves like a bounded star: model
                # it as star when unbounded/large, else as a small unrolled
                # concat (cheap and exact for realistic n).
                if hi == -1 or hi > 8:
                    return _Node("star", children=[atom], lo=min(lo, 1), hi=-1)
                copies = [atom] * max(hi, 1)
                return _Node("concat", children=copies) if hi > 1 else atom
        return atom

    def _maybe_lazy(self) -> None:
        if self._peek() == "?":
            self.i += 1  # lazy quantifier: same ambiguity profile, ignore

    def _atom(self) -> _Node:
        c = self._peek()
        if c == "(":
            self.i += 1
            # skip non-capturing / named-group / lookaround prefixes
            if self.p[self.i:self.i + 2] == "?:":
                self.i += 2
            elif self.p[self.i:self.i + 2] in ("?=", "?!"):
                self.i += 2
                self._skip_group()
                return _Node("lit", charset=frozenset())  # lookahead -> epsilon
            elif self.p[self.i:self.i + 3] in ("?<=", "?<!"):
                self.i += 3
                self._skip_group()
                return _Node("lit", charset=frozenset())  # lookbehind -> epsilon
            elif self.p[self.i:self.i + 2] == "?P" or self._peek() == "?":
                m = re.match(r"\?P?<[^>]+>", self.p[self.i:])
                if m:
                    self.i += m.end()
            inner = self._alt()
            if self._peek() == ")":
                self.i += 1
            return inner
        if c == "[":
            return self._char_class()
        if c == ".":
            self.i += 1
            return _Node("lit", charset=None)  # None => wildcard
        if c == "\\":
            return self._escape()
        self.i += 1
        return _Node("lit", charset=self._expand({c}))

    def _skip_group(self) -> None:
        depth = 1
        while self.i < self.n and depth:
            ch = self.p[self.i]
            if ch == "\\":
                self.i += 2
                continue
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            self.i += 1

    def _escape(self) -> _Node:
        self.i += 1
        if self.i >= self.n:
            return _Node("lit", charset=frozenset("\\"))
        c = self.p[self.i]
        self.i += 1
        if c.isdigit():
            raise UnsupportedPatternError("backreference")
        classes = {
            "d": frozenset("0123456789"),
            "w": frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"),
            "s": frozenset(" \t\n\r\f\v"),
        }
        if c.lower() in classes and c.islower():
            return _Node("lit", charset=self._expand(classes[c]))
        if c in ("D", "W", "S"):
            return _Node("lit", charset=None)  # negated class ~ treat as wildcard (over-approx)
        return _Node("lit", charset=self._expand({c}))

    def _char_class(self) -> _Node:
        start = self.i
        self.i += 1
        negated = self._peek() == "^"
        if negated:
            self.i += 1
        chars: Set[str] = set()
        while self.i < self.n and self.p[self.i] != "]":
            if self.p[self.i] == "\\" and self.i + 1 < self.n:
                nxt = self.p[self.i + 1]
                mapping = {
                    "d": "0123456789",
                    "w": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_",
                    "s": " \t\n\r\f\v",
                }
                if nxt in mapping:
                    chars.update(mapping[nxt])
                else:
                    chars.add(nxt)
                self.i += 2
                continue
            if self.i + 2 < self.n and self.p[self.i + 1] == "-" and self.p[self.i + 2] != "]":
                lo, hi = self.p[self.i], self.p[self.i + 2]
                try:
                    chars.update(chr(o) for o in range(ord(lo), ord(hi) + 1) if ord(hi) - ord(lo) < 200)
                except ValueError:
                    chars.add(lo)
                self.i += 3
                continue
            chars.add(self.p[self.i])
            self.i += 1
        if self.i < self.n:
            self.i += 1  # consume ']'
        if negated or not chars:
            return _Node("lit", charset=None)  # over-approx: negated class -> wildcard
        return _Node("lit", charset=self._expand(frozenset(chars)))

    def _expand(self, chars: FrozenSet[str]) -> FrozenSet[str]:
        if not self.ignorecase:
            return frozenset(chars)
        expanded = set(chars)
        for c in chars:
            expanded.add(c.lower())
            expanded.add(c.upper())
        return frozenset(expanded)

    def _peek(self) -> str:
        return self.p[self.i] if self.i < self.n else ""


# ------------------------------------------------------------- Glushkov NFA

@dataclass
class _Position:
    charset: Optional[FrozenSet[str]]  # None == wildcard (matches "any")


@dataclass
class GlushkovNFA:
    positions: List[_Position]
    firstpos: FrozenSet[int]
    followpos: Dict[int, Set[int]] = field(default_factory=dict)


def _overlaps(a: Optional[FrozenSet[str]], b: Optional[FrozenSet[str]]) -> bool:
    if a is None or b is None:
        return True  # wildcard overlaps everything
    return bool(a & b)


def _build_nfa(root: _Node) -> GlushkovNFA:
    """Cleaner two-pass construction: assign positions first, then compute
    firstpos/lastpos/followpos over the fixed position list (avoids the
    partial re-entrancy issue in a single recursive pass)."""
    positions: List[_Position] = []
    node_pos: Dict[int, int] = {}

    def assign(node: _Node) -> None:
        if node.kind == "lit":
            if node.charset == frozenset():
                return  # epsilon leaf, no position
            node_pos[id(node)] = len(positions)
            positions.append(_Position(node.charset))
            return
        for child in node.children:
            assign(child)

    assign(root)

    followpos: Dict[int, Set[int]] = {i: set() for i in range(len(positions))}

    def compute(node: _Node) -> Tuple[FrozenSet[int], FrozenSet[int], bool]:
        if node.kind == "lit":
            if node.charset == frozenset():
                return frozenset(), frozenset(), True
            p = node_pos[id(node)]
            return frozenset({p}), frozenset({p}), False
        if node.kind == "concat":
            first: FrozenSet[int] = frozenset()
            last: FrozenSet[int] = frozenset()
            nullable = True
            prev_last: FrozenSet[int] = frozenset()
            started = False
            for child in node.children:
                cf, cl, cn = compute(child)
                if not started:
                    first = cf
                    started = True
                elif nullable:
                    first = first | cf
                for p in prev_last:
                    followpos[p].update(cf)
                if cl:
                    last = cl
                elif not cn:
                    last = frozenset()
                else:
                    last = last  # keep previous last if this child nullable+empty
                prev_last = cl if cl else (prev_last if cn else frozenset())
                nullable = nullable and cn
            return first, last, nullable
        if node.kind == "alt":
            firsts, lasts = [], []
            nullable = False
            for child in node.children:
                cf, cl, cn = compute(child)
                firsts.append(cf)
                lasts.append(cl)
                nullable = nullable or cn
            f = frozenset().union(*firsts) if firsts else frozenset()
            l = frozenset().union(*lasts) if lasts else frozenset()
            return f, l, nullable
        if node.kind == "star":
            child = node.children[0]
            cf, cl, cn = compute(child)
            if node.hi == -1 or node.hi > 1:
                for p in cl:
                    followpos[p].update(cf)
            if node.lo == 0:
                return cf, cl, True
            return cf, cl, cn
        return frozenset(), frozenset(), True

    first, _, _ = compute(root)
    return GlushkovNFA(positions=positions, firstpos=first, followpos=followpos)


# --------------------------------------------------------------- Tarjan SCC

def _tarjan_scc(followpos: Dict[int, Set[int]]) -> List[List[int]]:
    index_counter = [0]
    stack: List[int] = []
    lowlink: Dict[int, int] = {}
    index: Dict[int, int] = {}
    on_stack: Dict[int, bool] = {}
    result: List[List[int]] = []

    def strongconnect(v: int) -> None:
        index[v] = index_counter[0]
        lowlink[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack[v] = True

        for w in followpos.get(v, ()):
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif on_stack.get(w):
                lowlink[v] = min(lowlink[v], index[w])

        if lowlink[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                comp.append(w)
                if w == v:
                    break
            result.append(comp)

    import sys
    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old_limit, len(followpos) * 2 + 1000))
    try:
        for v in followpos:
            if v not in index:
                strongconnect(v)
    finally:
        sys.setrecursionlimit(old_limit)
    return result


# ------------------------------------------------------------------- verdict

def _leaf_charsets(node: _Node) -> List[Optional[FrozenSet[str]]]:
    if node.kind == "lit":
        return [] if node.charset == frozenset() else [node.charset]
    out: List[Optional[FrozenSet[str]]] = []
    for child in node.children:
        out.extend(_leaf_charsets(child))
    return out


def _find_nested_unbounded_quantifier(node: _Node, in_unbounded: bool = False) -> Optional[str]:
    """Depth-first search for `(X*|X+)*|+` where an unbounded-repeat
    subtree sits *directly* (unanchored) inside another unbounded-repeat
    subtree and their leaf character sets overlap (the `(a+)+` /
    `(\\d+)*` / `(a|a)*` shape).

    MAJOR-4 fix: this supplementary structural check exists only to catch
    the cases Glushkov position-collapse misses (nested same-symbol
    quantifiers fold onto one self-loop position). It must NOT fire when
    the *inner* unbounded repeat is only one branch of a multi-part
    ``concat`` alongside a literal/separator -- e.g. ``(a+b)+``,
    ``(a+,)+``, ``(\\d+\\.)+`` are anchored/linear (the trailing literal
    forces each outer iteration to consume a distinct, non-overlapping
    suffix, so there is no ambiguous overlap), and were being wrongly
    flagged HIGH by propagating the "inside an unbounded repeat" flag
    straight through the concat to the inner star regardless of its
    anchoring siblings.

    Fix: the "in_unbounded" flag is only propagated into a `concat`'s
    children when that concat is the *sole, unwrapped* body of the outer
    unbounded repeat AND has exactly one child (i.e. no other literal
    branches share the loop body) -- concretely, once inside any
    multi-part concat, the flag resets to False, since a concat with more
    than one part inherently means something other than the bare inner
    repeat is being consumed each outer iteration (an anchor). Genuine
    unanchored shapes -- the inner repeat sitting directly as the star's
    whole body (`(a+)+`), or as one alternation branch with no
    intervening concat (`(a|a)*`) -- still propagate normally."""
    if node.kind == "star" and node.hi == -1:
        if in_unbounded:
            outer_syms = _leaf_charsets(node)
            if any(_overlaps(a, b) for i, a in enumerate(outer_syms)
                   for b in outer_syms[i + 1:]) or len(set(map(str, outer_syms))) <= 1:
                if outer_syms:
                    return f"repeat of {outer_syms[0]!r}-like symbols nested in another repeat"
        for child in node.children:
            found = _find_nested_unbounded_quantifier(child, in_unbounded=True)
            if found:
                return found
        return None
    if node.kind == "concat" and len(node.children) > 1:
        # A literal/other branch shares this loop body alongside any
        # unbounded repeat here -- that anchors each outer iteration, so
        # do not treat the repeat below as "nested in an unbounded loop"
        # even if we arrived here with in_unbounded=True.
        for child in node.children:
            found = _find_nested_unbounded_quantifier(child, in_unbounded=False)
            if found:
                return found
        return None
    for child in node.children:
        found = _find_nested_unbounded_quantifier(child, in_unbounded=in_unbounded)
        if found:
            return found
    return None


@dataclass
class AmbiguityResult:
    verdict: str  # "safe" | "eda" | "ida" | "unsupported"
    detail: str = ""


def analyze_pattern(
    pattern: str,
    ignorecase: bool = False,
    dotall: bool = False,
    length_guarded: bool = False,
) -> AmbiguityResult:
    """Run the Glushkov-NFA EDA/IDA analysis on one regex pattern string.

    Returns ``verdict="unsupported"`` for backreferences or patterns
    exceeding ``MAX_PATTERN_LEN`` (both documented false negatives, not
    silently-safe results -- callers must not report these as "safe").
    """
    if len(pattern) > MAX_PATTERN_LEN:
        return AmbiguityResult("unsupported", "pattern exceeds analysis length budget")
    try:
        root = _Parser(pattern, ignorecase, dotall).parse()
        nfa = _build_nfa(root)
    except (UnsupportedPatternError, RecursionError, IndexError):
        return AmbiguityResult("unsupported", "backreference or unparseable construct")

    # Structural pre-check: nested unbounded quantifiers over the same
    # symbol set, e.g. `(a+)+`, `(\d+)*` -- the classic EDA shape.
    # Documented limitation: pure Glushkov positions are per symbol
    # OCCURRENCE, not per quantifier nesting level, so `(a+)+` collapses
    # onto the same single self-looping position as `a+` and is
    # structurally invisible to the SCC analysis below (Weideman's
    # "orbit" extension fixes this via a product construction, out of
    # scope here). This direct AST check catches that specific shape
    # without the full construction.
    nested = _find_nested_unbounded_quantifier(root)
    if nested is not None:
        return AmbiguityResult(
            "eda", f"nested unbounded quantifier over overlapping symbols: {nested}"
        )

    sccs = _tarjan_scc(nfa.followpos)
    scc_of: Dict[int, int] = {}
    for i, comp in enumerate(sccs):
        for p in comp:
            scc_of[p] = i

    # EDA: within one non-trivial SCC, a position has >=2 outgoing edges
    # back into the SAME SCC whose char sets overlap.
    for comp in sccs:
        comp_set = set(comp)
        if len(comp) < 1:
            continue
        for p in comp:
            targets_in_scc = [t for t in nfa.followpos.get(p, ()) if t in comp_set]
            # self-loop plus another intra-SCC edge, or two distinct
            # intra-SCC edges, with overlapping charsets => ambiguous loop
            for a in range(len(targets_in_scc)):
                for b in range(a + 1, len(targets_in_scc)):
                    ta, tb = targets_in_scc[a], targets_in_scc[b]
                    if ta == tb:
                        continue
                    if _overlaps(nfa.positions[ta].charset, nfa.positions[tb].charset):
                        return AmbiguityResult(
                            "eda",
                            f"exponential ambiguity: position {p} has two "
                            f"overlapping intra-loop paths ({ta}, {tb})",
                        )
            if len(comp) > 1 and len(targets_in_scc) >= 1:
                # loop re-enters via a different position than itself with
                # an overlapping charset on the loop edge and the entry
                # edge -> still ambiguous (classic (a+)+ shape spans 2 pos)
                for t in targets_in_scc:
                    if t != p and _overlaps(nfa.positions[p].charset, nfa.positions[t].charset):
                        # confirm there are >=2 distinct ways to traverse
                        # the SCC consuming the same class (heuristic:
                        # SCC has an internal branch, i.e. some node with
                        # out-degree >=2 inside it)
                        branchy = any(
                            len([x for x in nfa.followpos.get(q, ()) if x in comp_set]) >= 2
                            for q in comp
                        )
                        if branchy:
                            return AmbiguityResult(
                                "eda",
                                f"exponential ambiguity: branching loop in SCC "
                                f"containing positions {sorted(comp)}",
                            )

    # A "real loop" SCC is either size > 1, or a single position with a
    # self-edge (followpos[p] contains p itself) -- e.g. a bare `\d+`.
    def _is_loop_scc(idx: int) -> bool:
        comp = sccs[idx]
        if len(comp) > 1:
            return True
        p = comp[0]
        return p in nfa.followpos.get(p, ())

    # IDA: sequential (chained) SCC loops with overlapping char sets.
    for p, targets in nfa.followpos.items():
        p_scc = scc_of.get(p)
        for t in targets:
            t_scc = scc_of.get(t)
            if p_scc is None or t_scc is None or p_scc == t_scc:
                continue
            if not _is_loop_scc(p_scc) or not _is_loop_scc(t_scc):
                continue  # only real loops count
            if _overlaps(nfa.positions[p].charset, nfa.positions[t].charset):
                if length_guarded:
                    continue
                return AmbiguityResult(
                    "ida",
                    f"polynomial ambiguity: chained loops (SCC {p_scc} -> "
                    f"SCC {t_scc}) share overlapping character classes",
                )

    return AmbiguityResult("safe")
