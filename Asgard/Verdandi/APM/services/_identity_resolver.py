"""
Service Identity Resolution (DEEPTHINK_10)

Two safe, general-purpose canonicalization strategies for raw service
names, plus an operator-controlled alias registry for merges the
resolvers deliberately refuse to make automatically:

- ``resolve_identity``: composite key ``env:namespace:canonical_name``
  when infra resource attributes (``k8s.namespace.name``, a deployment
  environment attribute) are present; otherwise lexical canonicalization
  only.
- ``canonicalize_lexical``: lowercase, unify ``_``/space/camelCase
  boundaries to ``-``. Never strips suffixes (``-api``/``-worker`` stay
  distinct) and never merges version segments — those are explicit
  non-goals, enforced by omission (the function does nothing beyond
  separator/case normalization).
- ``AliasRegistry``: dict-in/dict-out registry of operator-approved merges.
  ``suggest_merges()`` proposes (never applies) candidates sharing
  identical upstream+downstream neighbor sets in a given ``ServiceMap``.
"""

import re
from typing import Dict, List, Optional, Tuple

from Asgard.Verdandi.APM.models.apm_models import ServiceIdentity, ServiceMap

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_SEPARATORS = re.compile(r"[_\s]+")
_MULTI_HYPHEN = re.compile(r"-+")

# Resource attribute keys checked, in priority order, for namespace/env.
_NAMESPACE_KEYS = ("k8s.namespace.name",)
_ENV_KEYS = (
    "deployment.environment.name",
    "deployment.environment",
    "deployment",
    "env",
)


def canonicalize_lexical(name: str) -> str:
    """
    Lowercase, unify ``_``/space/camelCase word boundaries to ``-``.

    Deliberately does NOT strip suffixes or version segments:
    ``payment-api`` and ``payment-worker`` remain distinct;
    ``payment-service-v2`` is not merged with ``payment-service``.
    """
    if not name:
        return name
    s = _CAMEL_BOUNDARY.sub("-", name)
    s = _SEPARATORS.sub("-", s)
    s = s.lower()
    s = _MULTI_HYPHEN.sub("-", s).strip("-")
    return s


def resolve_identity(
    raw_name: str,
    resource_attrs: Optional[Dict[str, object]] = None,
) -> ServiceIdentity:
    """
    Resolve a raw service name to a ``ServiceIdentity``.

    Uses composite key ``env:namespace:canonical_name`` when a namespace
    resource attribute is present (env defaults to "unknown" if only
    namespace is known); otherwise falls back to lexical canonicalization
    only, with ``composite_key == canonical_name``.
    """
    resource_attrs = resource_attrs or {}
    canonical_name = canonicalize_lexical(raw_name)

    namespace = None
    for key in _NAMESPACE_KEYS:
        if resource_attrs.get(key):
            namespace = resource_attrs[key]
            break

    env = None
    for key in _ENV_KEYS:
        if resource_attrs.get(key):
            env = resource_attrs[key]
            break

    if namespace:
        composite_key = f"{env or 'unknown'}:{namespace}:{canonical_name}"
    else:
        composite_key = canonical_name

    return ServiceIdentity(
        raw_name=raw_name,
        canonical_name=canonical_name,
        composite_key=composite_key,
        env=str(env) if env else None,
        namespace=str(namespace) if namespace else None,
    )


class AliasRegistry:
    """
    Operator-approved service-name merge registry (dict-in, dict-out).

    Resolvers never auto-merge names beyond safe lexical canonicalization;
    an ``AliasRegistry`` is how an operator explicitly says "these two
    canonical names are actually the same service".
    """

    def __init__(self, aliases: Optional[Dict[str, str]] = None):
        self._aliases: Dict[str, str] = dict(aliases or {})

    def register(self, alias: str, canonical: str) -> None:
        """Register `alias` to resolve to `canonical`."""
        self._aliases[alias] = canonical

    def resolve(self, name: str) -> str:
        """Follow alias chains (cycle-safe) to the final canonical name."""
        seen = set()
        current = name
        while current in self._aliases and current not in seen:
            seen.add(current)
            current = self._aliases[current]
        return current

    def to_dict(self) -> Dict[str, str]:
        """Return the raw alias -> canonical mapping."""
        return dict(self._aliases)

    @classmethod
    def from_dict(cls, aliases: Dict[str, str]) -> "AliasRegistry":
        """Construct a registry from a plain alias -> canonical dict."""
        return cls(aliases)

    def suggest_merges(self, service_map: ServiceMap) -> List[Tuple[str, str]]:
        """
        Propose (never apply) merge candidates: services that share an
        identical set of upstream callers AND downstream callees in
        ``service_map``. Returns a list of (candidate, suggested_canonical)
        pairs; the operator must call ``register()`` to actually apply one.
        """
        upstream: Dict[str, set] = {s: set() for s in service_map.services}
        downstream: Dict[str, set] = {s: set() for s in service_map.services}
        for dep in service_map.dependencies:
            downstream.setdefault(dep.source_service, set()).add(dep.target_service)
            upstream.setdefault(dep.target_service, set()).add(dep.source_service)

        signature_groups: Dict[Tuple[frozenset, frozenset], List[str]] = {}
        for s in service_map.services:
            key = (frozenset(upstream.get(s, set())), frozenset(downstream.get(s, set())))
            if key == (frozenset(), frozenset()):
                continue  # isolated service: no relational signature to compare
            signature_groups.setdefault(key, []).append(s)

        suggestions: List[Tuple[str, str]] = []
        for group in signature_groups.values():
            if len(group) > 1:
                ordered = sorted(group)
                base = ordered[0]
                for other in ordered[1:]:
                    suggestions.append((other, base))
        return suggestions
