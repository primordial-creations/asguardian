"""
Bragi License Policy Engine (Plan 03 Phase A)

Replaces bidirectional substring matching (which flagged LGPL-3.0 as
PROHIBITED because "gpl-3.0" is a substring of "lgpl-3.0") with:

1. Normalization of observed license text to an exact SPDX id.
2. A minimal SPDX expression evaluator (OR / AND / WITH, parentheses):
   - OR  -> compliant if ANY arm is allowed (report the chosen arm).
   - AND -> every arm must pass; the worst verdict wins.
3. Policy evaluation on exact normalized ids only - never substrings.
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


# Ordered longest/most-specific first so e.g. AGPL matches before GPL and
# LGPL before GPL. Each entry: (regex, SPDX id, category).
LICENSE_PATTERNS: List[Tuple[str, str, LicenseCategory]] = [
    (r"AGPL[-\s]*v?(3(\.0)?)?|GNU Affero General Public License", "AGPL-3.0", LicenseCategory.STRONG_COPYLEFT),
    (r"LGPL[-\s]*v?3(\.0)?|GNU Lesser General Public License v?3", "LGPL-3.0", LicenseCategory.WEAK_COPYLEFT),
    (r"LGPL[-\s]*v?2\.1|GNU Lesser General Public License v?2", "LGPL-2.1", LicenseCategory.WEAK_COPYLEFT),
    (r"^LGPL$|GNU Lesser General Public License|GNU Library", "LGPL-2.1", LicenseCategory.WEAK_COPYLEFT),
    (r"GPL[-\s]*v?3(\.0)?|GNU General Public License v?3", "GPL-3.0", LicenseCategory.STRONG_COPYLEFT),
    (r"GPL[-\s]*v?2(\.0)?|GNU General Public License v?2", "GPL-2.0", LicenseCategory.STRONG_COPYLEFT),
    (r"^GPL$|GNU General Public License", "GPL-2.0-or-later", LicenseCategory.STRONG_COPYLEFT),
    (r"SSPL|Server Side Public License", "SSPL-1.0", LicenseCategory.STRONG_COPYLEFT),
    (r"MPL[-\s]*2(\.0)?|Mozilla Public License", "MPL-2.0", LicenseCategory.WEAK_COPYLEFT),
    (r"Apache[-\s]*(License)?,?\s*(Version)?\s*2(\.0)?|Apache Software License", "Apache-2.0", LicenseCategory.PERMISSIVE),
    (r"BSD[-\s]*(3|3-Clause|New|Revised)", "BSD-3-Clause", LicenseCategory.PERMISSIVE),
    (r"BSD[-\s]*(2|2-Clause|Simplified|FreeBSD)", "BSD-2-Clause", LicenseCategory.PERMISSIVE),
    (r"^BSD([-\s]?License)?$", "BSD-3-Clause", LicenseCategory.PERMISSIVE),
    (r"MIT|Expat", "MIT", LicenseCategory.PERMISSIVE),
    (r"ISC", "ISC", LicenseCategory.PERMISSIVE),
    (r"PSF|Python Software Foundation", "PSF-2.0", LicenseCategory.PERMISSIVE),
    (r"Unlicense|Public Domain", "Unlicense", LicenseCategory.PUBLIC_DOMAIN),
    (r"CC0|Creative Commons Zero", "CC0-1.0", LicenseCategory.PUBLIC_DOMAIN),
    (r"WTFPL", "WTFPL", LicenseCategory.PUBLIC_DOMAIN),
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
    "gnu general public license v2": "GPL-2.0",
    "agpl-3.0-only": "AGPL-3.0",
    "agpl-3.0-or-later": "AGPL-3.0",
    "gnu affero general public license v3": "AGPL-3.0",
    "lgpl-3.0-only": "LGPL-3.0",
    "lgpl-3.0-or-later": "LGPL-3.0",
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

# A string looks like an SPDX expression if it contains boolean operators.
_EXPRESSION_TOKEN = re.compile(r"\bOR\b|\bAND\b|\bWITH\b|\(|\)", re.IGNORECASE)
_KNOWN_SPDX_IDS = {spdx_id.lower() for spdx_id in _CATEGORY_BY_ID}


def canonical_spdx_id(text: str) -> Optional[str]:
    """Map a license string/config entry to a canonical SPDX id, or None."""
    if not text:
        return None
    stripped = text.strip()
    lowered = stripped.lower()
    if lowered in _SPDX_ALIASES:
        return _SPDX_ALIASES[lowered]
    if lowered in _KNOWN_SPDX_IDS:
        for spdx_id in _CATEGORY_BY_ID:
            if spdx_id.lower() == lowered:
                return spdx_id
    return None


def normalize_license(text: str) -> Tuple[Optional[str], LicenseCategory]:
    """
    Normalize observed license text to (SPDX id, category).

    Tries exact SPDX id / alias first, then the ordered regex patterns
    (most specific first, so LGPL never falls through to GPL).
    """
    if not text:
        return None, LicenseCategory.UNKNOWN
    canonical = canonical_spdx_id(text)
    if canonical is not None:
        return canonical, _CATEGORY_BY_ID.get(canonical, LicenseCategory.UNKNOWN)
    for pattern, spdx_id, category in LICENSE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
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


class LicensePolicy:
    """Exact-SPDX-id policy engine with OR/AND expression handling."""

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

        if _EXPRESSION_TOKEN.search(license_text) and re.search(
            r"\bOR\b|\bAND\b", license_text, re.IGNORECASE
        ):
            return self._evaluate_expression(license_text)

        spdx_id, category = normalize_license(license_text)
        verdict = self.verdict_for_id(spdx_id)
        return PolicyDecision(
            verdict=verdict, spdx_id=spdx_id, category=category,
            rationale=f"'{license_text.strip()}' normalized to {spdx_id or 'UNKNOWN'}",
        )

    def _evaluate_expression(self, expression: str) -> PolicyDecision:
        """Top-level OR splits (any arm suffices); AND requires all arms."""
        or_arms = self._split_top_level(expression, "OR")
        arm_decisions = [self._evaluate_and_arm(arm) for arm in or_arms]
        arms = [d.spdx_id or a.strip() for a, d in zip(or_arms, arm_decisions)]

        order = [LicenseVerdict.ALLOWED, LicenseVerdict.WARN,
                 LicenseVerdict.UNKNOWN, LicenseVerdict.PROHIBITED]
        best = min(arm_decisions, key=lambda d: order.index(d.verdict))
        return PolicyDecision(
            verdict=best.verdict,
            spdx_id=best.spdx_id,
            category=best.category,
            is_expression=True,
            chosen_arm=best.spdx_id if len(or_arms) > 1 else None,
            arms=arms,
            rationale=(
                f"SPDX expression '{expression.strip()}': "
                + (f"satisfied via {best.spdx_id}" if best.verdict == LicenseVerdict.ALLOWED
                   else f"best arm {best.spdx_id or 'UNKNOWN'} -> {best.verdict.value}")
            ),
        )

    def _evaluate_and_arm(self, arm: str) -> PolicyDecision:
        """AND conjunction: the WORST sub-verdict wins."""
        parts = self._split_top_level(arm, "AND")
        order = [LicenseVerdict.ALLOWED, LicenseVerdict.WARN,
                 LicenseVerdict.UNKNOWN, LicenseVerdict.PROHIBITED]
        worst: Optional[PolicyDecision] = None
        for part in parts:
            cleaned = self._strip_with(part)
            if re.search(r"\bOR\b|\bAND\b", cleaned, re.IGNORECASE):
                # Parenthesized sub-expression: recurse instead of pattern-
                # matching the raw text (which would mis-hit e.g. GPL first).
                decision = self._evaluate_expression(cleaned)
            else:
                spdx_id, category = normalize_license(cleaned)
                decision = PolicyDecision(
                    verdict=self.verdict_for_id(spdx_id), spdx_id=spdx_id, category=category)
            if worst is None or order.index(decision.verdict) > order.index(worst.verdict):
                worst = decision
        return worst or PolicyDecision(verdict=LicenseVerdict.UNKNOWN)

    @staticmethod
    def _strip_with(text: str) -> str:
        """Drop a WITH exception clause and surrounding parentheses."""
        cleaned = re.split(r"\bWITH\b", text, flags=re.IGNORECASE)[0]
        return cleaned.strip().strip("()").strip()

    @staticmethod
    def _split_top_level(expression: str, operator: str) -> List[str]:
        """Split on OR/AND at parenthesis depth zero."""
        tokens = re.split(rf"(\b{operator}\b|\(|\))", expression, flags=re.IGNORECASE)
        arms: List[str] = []
        current = ""
        depth = 0
        for token in tokens:
            if token == "(":
                depth += 1
                current += token
            elif token == ")":
                depth -= 1
                current += token
            elif depth == 0 and token.upper() == operator:
                arms.append(current)
                current = ""
            else:
                current += token
        arms.append(current)
        return [a.strip() for a in arms if a.strip()]


@dataclass
class LicenseGateInput:
    """Summary consumed by Plan 01's non-compensatory license gate."""
    prohibited_count: int = 0
    unknown_count: int = 0
