"""
Bragi License Policy Engine (Plan 03 Phase A)

Replaces bidirectional substring matching (which flagged LGPL-3.0 as
PROHIBITED because "gpl-3.0" is a substring of "lgpl-3.0") with:

1. Normalization of observed license text to an exact SPDX id using
   word-boundary-anchored token matching (never bare substrings), with a
   conservative UNKNOWN fallback for long free text.
2. A recursive-descent SPDX expression parser (OR / AND / WITH, balanced
   parentheses, depth-guarded). "X or later" is a version suffix, never an
   OR expression.
3. Policy evaluation on exact normalized ids only. OR semantics: the best
   verdict among *known* arms wins; if every arm is unknown the result is
   UNKNOWN; a prohibited license can never be laundered through unknown
   arms. AND semantics: the worst verdict wins.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Sequence, Tuple

from Asgard.Bragi.Dependencies.models.license_models import LicenseCategory


class LicenseVerdict(str, Enum):
    """Policy verdict for a license or license expression."""
    ALLOWED = "allowed"
    WARN = "warn"
    PROHIBITED = "prohibited"
    UNKNOWN = "unknown"


# Ordered most-specific first (AGPL before GPL, LGPL before GPL, versioned
# before unversioned). Every alternative is word-boundary anchored so that
# e.g. "permit" can never match MIT and "discretion" can never match ISC.
LICENSE_PATTERNS: List[Tuple[str, str, LicenseCategory]] = [
    (r"\bAGPL[-\s]*v?(3(\.0)?)?\b|\bGNU Affero General Public License\b", "AGPL-3.0", LicenseCategory.STRONG_COPYLEFT),
    (r"\bLGPL[-\s]*v?3(\.0)?\b|\bGNU Lesser General Public License v?3\b", "LGPL-3.0", LicenseCategory.WEAK_COPYLEFT),
    (r"\bLGPL[-\s]*v?2(\.1)?\b|\bGNU Lesser General Public License v?2(\.1)?\b", "LGPL-2.1", LicenseCategory.WEAK_COPYLEFT),
    (r"\bLGPL\b|\bGNU Lesser General Public License\b|\bGNU Library\b", "LGPL-2.1", LicenseCategory.WEAK_COPYLEFT),
    (r"\bGPL[-\s]*v?3(\.0)?\b|\bGNU General Public License v?3\b", "GPL-3.0", LicenseCategory.STRONG_COPYLEFT),
    (r"\bGPL[-\s]*v?2(\.0)?\b|\bGNU General Public License v?2\b", "GPL-2.0", LicenseCategory.STRONG_COPYLEFT),
    (r"\bGPL\b|\bGNU General Public License\b", "GPL-2.0-or-later", LicenseCategory.STRONG_COPYLEFT),
    (r"\bSSPL\b|\bServer Side Public License\b", "SSPL-1.0", LicenseCategory.STRONG_COPYLEFT),
    (r"\bMPL[-\s]*2(\.0)?\b|\bMozilla Public License\b", "MPL-2.0", LicenseCategory.WEAK_COPYLEFT),
    (r"\bApache[-\s]*(License[,\s]*)?(Version\s*)?2(\.0)?\b|\bApache Software License\b|\bApache\b", "Apache-2.0", LicenseCategory.PERMISSIVE),
    (r"\bBSD[-\s]*(3([-\s]Clause)?|New|Revised)\b", "BSD-3-Clause", LicenseCategory.PERMISSIVE),
    (r"\bBSD[-\s]*(2([-\s]Clause)?|Simplified|FreeBSD)\b", "BSD-2-Clause", LicenseCategory.PERMISSIVE),
    (r"\bBSD\b", "BSD-3-Clause", LicenseCategory.PERMISSIVE),
    (r"\bMIT\b|\bExpat\b", "MIT", LicenseCategory.PERMISSIVE),
    (r"\bISC\b", "ISC", LicenseCategory.PERMISSIVE),
    (r"\bPSF\b|\bPython Software Foundation\b", "PSF-2.0", LicenseCategory.PERMISSIVE),
    (r"\bUnlicense\b|\bPublic Domain\b", "Unlicense", LicenseCategory.PUBLIC_DOMAIN),
    (r"\bCC0\b|\bCreative Commons Zero\b", "CC0-1.0", LicenseCategory.PUBLIC_DOMAIN),
    (r"\bWTFPL\b", "WTFPL", LicenseCategory.PUBLIC_DOMAIN),
]

# Aliases mapping policy-config strings and SPDX variants to canonical ids.
_SPDX_ALIASES = {
    "gpl-3.0-only": "GPL-3.0",
    "gpl-3.0-or-later": "GPL-3.0",
    "gpl-3.0+": "GPL-3.0",
    "gplv3": "GPL-3.0",
    "gnu general public license v3": "GPL-3.0",
    "gnu general public license v3 (gplv3)": "GPL-3.0",
    "gpl-2.0-only": "GPL-2.0",
    "gpl-2.0-or-later": "GPL-2.0",
    "gplv2": "GPL-2.0",
    "gnu general public license v2": "GPL-2.0",
    "agpl-3.0-only": "AGPL-3.0",
    "agpl-3.0-or-later": "AGPL-3.0",
    "agplv3": "AGPL-3.0",
    "gnu affero general public license v3": "AGPL-3.0",
    "lgpl-3.0-only": "LGPL-3.0",
    "lgpl-3.0-or-later": "LGPL-3.0",
    "lgplv3": "LGPL-3.0",
    "gnu lesser general public license v3": "LGPL-3.0",
    "lgpl-2.1-only": "LGPL-2.1",
    "lgpl-2.1-or-later": "LGPL-2.1",
    "sspl": "SSPL-1.0",
    "server side public license": "SSPL-1.0",
    "mit license": "MIT",
    "apache software license": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "bsd license": "BSD-3-Clause",
    "isc license": "ISC",
    "python software foundation license": "PSF-2.0",
    "mozilla public license 2.0": "MPL-2.0",
    "public domain": "Unlicense",
}

_CATEGORY_BY_ID = {spdx_id: category for _, spdx_id, category in LICENSE_PATTERNS}
_CATEGORY_BY_ID.setdefault("SSPL-1.0", LicenseCategory.STRONG_COPYLEFT)
_CATEGORY_BY_ID.setdefault("GPL-2.0-or-later", LicenseCategory.STRONG_COPYLEFT)

_KNOWN_SPDX_IDS = {spdx_id.lower(): spdx_id for spdx_id in _CATEGORY_BY_ID}

# Free text longer than this is never pattern-matched: license *fields* are
# short; a paragraph of proprietary prose must stay UNKNOWN, not become MIT
# because the word "MIT" appears somewhere.
_MAX_MATCHABLE_LENGTH = 100

# Depth guard for the expression parser.
_MAX_EXPRESSION_DEPTH = 10

# "GPLv3 or later" is a version suffix, not an OR expression.
_OR_LATER_SUFFIX = re.compile(r"[-\s]+or[-\s]+later\b", re.IGNORECASE)


def canonical_spdx_id(text: str) -> Optional[str]:
    """Map a license string/config entry to a canonical SPDX id, or None."""
    if not text:
        return None
    lowered = text.strip().lower()
    if lowered in _SPDX_ALIASES:
        return _SPDX_ALIASES[lowered]
    if lowered in _KNOWN_SPDX_IDS:
        return _KNOWN_SPDX_IDS[lowered]
    # "-or-later"/"+" version suffixes reduce to the base id.
    base = re.sub(r"(-or-later|-only|\+)$", "", lowered)
    if base != lowered:
        if base in _SPDX_ALIASES:
            return _SPDX_ALIASES[base]
        if base in _KNOWN_SPDX_IDS:
            return _KNOWN_SPDX_IDS[base]
    return None


def normalize_license(text: str) -> Tuple[Optional[str], LicenseCategory]:
    """
    Normalize observed license text to (SPDX id, category).

    Exact SPDX id / alias first; then word-boundary-anchored patterns
    (most specific first, so LGPL never falls through to GPL). Long free
    text is conservatively UNKNOWN.
    """
    if not text:
        return None, LicenseCategory.UNKNOWN
    collapsed = _OR_LATER_SUFFIX.sub("-or-later", text.strip())
    canonical = canonical_spdx_id(collapsed)
    if canonical is not None:
        return canonical, _CATEGORY_BY_ID.get(canonical, LicenseCategory.UNKNOWN)
    if len(collapsed) > _MAX_MATCHABLE_LENGTH:
        return None, LicenseCategory.UNKNOWN
    for pattern, spdx_id, category in LICENSE_PATTERNS:
        if re.search(pattern, collapsed, re.IGNORECASE):
            return spdx_id, category
    return None, LicenseCategory.UNKNOWN


@dataclass
class PolicyDecision:
    """Outcome of evaluating a license (expression) against a policy."""
    verdict: LicenseVerdict
    spdx_id: Optional[str] = None
    category: LicenseCategory = LicenseCategory.UNKNOWN
    is_expression: bool = False
    chosen_arm: Optional[str] = None       # OR: the arm that satisfied policy
    arms: List[str] = field(default_factory=list)
    rationale: str = ""


class _ParseError(Exception):
    """Raised for malformed or too-deep license expressions."""


class _ExpressionParser:
    """Recursive-descent parser for SPDX expressions with balanced parens.

    Grammar:
        expr     := and_expr (OR and_expr)*
        and_expr := primary (AND primary)*
        primary  := '(' expr ')' | license_id (WITH exception_id)?
    """

    def __init__(self, expression: str):
        self.tokens = re.findall(r"\(|\)|[^\s()]+", expression)
        self.pos = 0

    def _peek(self) -> Optional[str]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _next(self) -> str:
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def parse(self) -> tuple:
        node = self._parse_or(0)
        if self._peek() is not None:
            raise _ParseError(f"unexpected token '{self._peek()}'")
        return node

    def _parse_or(self, depth: int) -> tuple:
        if depth > _MAX_EXPRESSION_DEPTH:
            raise _ParseError("expression nesting too deep")
        arms = [self._parse_and(depth)]
        while self._peek() is not None and self._peek().upper() == "OR":
            self._next()
            arms.append(self._parse_and(depth))
        return arms[0] if len(arms) == 1 else ("OR", arms)

    def _parse_and(self, depth: int) -> tuple:
        arms = [self._parse_primary(depth)]
        while self._peek() is not None and self._peek().upper() == "AND":
            self._next()
            arms.append(self._parse_primary(depth))
        return arms[0] if len(arms) == 1 else ("AND", arms)

    def _parse_primary(self, depth: int) -> tuple:
        token = self._peek()
        if token is None:
            raise _ParseError("expected license id or '('")
        if token == "(":
            self._next()
            node = self._parse_or(depth + 1)
            if self._peek() != ")":
                raise _ParseError("unbalanced parentheses")
            self._next()
            return node
        if token == ")":
            raise _ParseError("unbalanced parentheses")
        # A license id: consecutive non-operator tokens joined by spaces.
        parts: List[str] = []
        while (t := self._peek()) is not None and t not in ("(", ")") \
                and t.upper() not in ("OR", "AND", "WITH"):
            parts.append(self._next())
        if not parts:
            raise _ParseError("empty license id")
        if (t := self._peek()) is not None and t.upper() == "WITH":
            self._next()
            if self._peek() is None or self._peek() in ("(", ")"):
                raise _ParseError("WITH missing exception id")
            self._next()  # exception id is recorded but not policy-relevant
        return ("ID", " ".join(parts))


class LicensePolicy:
    """Exact-SPDX-id policy engine with OR/AND expression handling."""

    # Preference order among KNOWN verdicts (OR chooses the leftmost hit).
    _OR_PREFERENCE = [LicenseVerdict.ALLOWED, LicenseVerdict.WARN, LicenseVerdict.PROHIBITED]
    # Badness order for AND (rightmost is worst).
    _AND_ORDER = [LicenseVerdict.ALLOWED, LicenseVerdict.WARN,
                  LicenseVerdict.UNKNOWN, LicenseVerdict.PROHIBITED]

    def __init__(
        self,
        allowed: Sequence[str],
        prohibited: Sequence[str],
        warn: Sequence[str],
    ):
        self.allowed_ids = self._canonicalize(allowed)
        self.prohibited_ids = self._canonicalize(prohibited)
        self.warn_ids = self._canonicalize(warn)

    @staticmethod
    def _canonicalize(entries: Sequence[str]) -> set:
        ids = set()
        for entry in entries:
            canonical = canonical_spdx_id(entry)
            if canonical is not None:
                ids.add(canonical)
        return ids

    # ---------------------------------------------------------------- single

    def verdict_for_id(self, spdx_id: Optional[str]) -> LicenseVerdict:
        """Exact-id policy check; substrings are never consulted."""
        if spdx_id is None:
            return LicenseVerdict.UNKNOWN
        if spdx_id in self.prohibited_ids:
            return LicenseVerdict.PROHIBITED
        if spdx_id in self.warn_ids:
            return LicenseVerdict.WARN
        if spdx_id in self.allowed_ids:
            return LicenseVerdict.ALLOWED
        # Known SPDX id that the policy does not mention: warn on copyleft,
        # allow permissive/public-domain, unknown otherwise.
        category = _CATEGORY_BY_ID.get(spdx_id)
        if category in (LicenseCategory.PERMISSIVE, LicenseCategory.PUBLIC_DOMAIN):
            return LicenseVerdict.ALLOWED
        if category in (LicenseCategory.WEAK_COPYLEFT, LicenseCategory.STRONG_COPYLEFT):
            return LicenseVerdict.WARN
        return LicenseVerdict.UNKNOWN

    # ------------------------------------------------------------ expression

    def evaluate(self, license_text: str) -> PolicyDecision:
        """Evaluate a license string or SPDX expression against the policy."""
        if not license_text or not license_text.strip():
            return PolicyDecision(verdict=LicenseVerdict.UNKNOWN, rationale="no license metadata")

        # "X or later" is a version suffix, never an OR expression.
        collapsed = _OR_LATER_SUFFIX.sub("-or-later", license_text.strip())

        if re.search(r"\bOR\b|\bAND\b", collapsed, re.IGNORECASE):
            try:
                node = _ExpressionParser(collapsed).parse()
            except _ParseError as error:
                return PolicyDecision(
                    verdict=LicenseVerdict.UNKNOWN,
                    is_expression=True,
                    rationale=f"malformed license expression '{license_text.strip()}': {error}",
                )
            decision = self._evaluate_node(node)
            decision.is_expression = True
            decision.rationale = (
                f"SPDX expression '{license_text.strip()}': "
                + (f"satisfied via {decision.spdx_id}"
                   if decision.verdict == LicenseVerdict.ALLOWED and decision.spdx_id
                   else f"-> {decision.verdict.value}"
                     + (f" via {decision.spdx_id}" if decision.spdx_id else ""))
            )
            return decision

        spdx_id, category = normalize_license(collapsed)
        verdict = self.verdict_for_id(spdx_id)
        return PolicyDecision(
            verdict=verdict, spdx_id=spdx_id, category=category,
            rationale=f"'{license_text.strip()}' normalized to {spdx_id or 'UNKNOWN'}",
        )

    def _evaluate_node(self, node: tuple) -> PolicyDecision:
        kind = node[0]
        if kind == "ID":
            spdx_id, category = normalize_license(node[1])
            return PolicyDecision(
                verdict=self.verdict_for_id(spdx_id), spdx_id=spdx_id,
                category=category, arms=[spdx_id or node[1]],
            )
        children = [self._evaluate_node(child) for child in node[1]]
        arms = [arm for child in children for arm in child.arms]
        if kind == "OR":
            return self._combine_or(children, arms)
        return self._combine_and(children, arms)

    def _combine_or(self, children: List[PolicyDecision], arms: List[str]) -> PolicyDecision:
        """
        OR = best of the KNOWN arms. All-unknown -> UNKNOWN. A PROHIBITED
        arm with no allowed/warn alternative stays PROHIBITED - unknown
        arms can never launder it.
        """
        known = [c for c in children if c.verdict != LicenseVerdict.UNKNOWN]
        if not known:
            return PolicyDecision(verdict=LicenseVerdict.UNKNOWN, arms=arms)
        best = min(known, key=lambda c: self._OR_PREFERENCE.index(c.verdict))
        return PolicyDecision(
            verdict=best.verdict, spdx_id=best.spdx_id, category=best.category,
            chosen_arm=best.spdx_id, arms=arms,
        )

    def _combine_and(self, children: List[PolicyDecision], arms: List[str]) -> PolicyDecision:
        """AND = the worst arm wins (PROHIBITED > UNKNOWN > WARN > ALLOWED)."""
        worst = max(children, key=lambda c: self._AND_ORDER.index(c.verdict))
        return PolicyDecision(
            verdict=worst.verdict, spdx_id=worst.spdx_id, category=worst.category,
            arms=arms,
        )


@dataclass
class LicenseGateInput:
    """Summary consumed by Plan 01's non-compensatory license gate."""
    prohibited_count: int = 0
    unknown_count: int = 0
