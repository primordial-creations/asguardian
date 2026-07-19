"""Entry point for the opt-in LLM-assisted triage layer (WS6).

Invariants (adversarially reviewed -- do not weaken without re-reading
``_Docs/Planning/TaintGaps/00_Plan.md`` WS6):

* ``enable_assist=False`` (the default) makes ZERO adapter/network calls and
  returns the input findings list UNCHANGED (same objects, same order, same
  length).
* Triage NEVER drops a finding. The output always has exactly the same
  findings as the input, in the same order.
* Triage NEVER mutates a finding's ``severity`` (or any other field) --
  low-confidence findings are wrapped in a :class:`TriagedFinding` that
  transparently delegates attribute access to the original finding and adds
  only a `.triage` annotation; the original finding object is untouched.
* Adapter errors/timeouts degrade to ``TriageLabel.NOT_AVAILABLE`` -- the
  finding is still kept, just unannotated with a usable verdict.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, List, Optional

from Asgard.Heimdall.Security.triage.models.triage_models import TriageLabel, TriageVerdict
from Asgard.Heimdall.Security.triage.services.triage_adapter import (
    MockTriageAdapter,
    TriageAdapter,
)
from Asgard.Heimdall.Security.triage.services.triage_cache import TriageCache, fingerprint

DEFAULT_LOW_CONFIDENCE_THRESHOLD = 0.6


class TriagedFinding:
    """Read-through wrapper: delegates all attribute access to the wrapped
    finding and additionally exposes a ``.triage`` verdict annotation.

    The wrapped finding is never mutated -- this class exists specifically so
    we can annotate findings (including immutable/strict pydantic models)
    without risking a change to ``severity`` or any other original field.
    """

    def __init__(self, finding: Any, triage: Optional[TriageVerdict]):
        object.__setattr__(self, "_finding", finding)
        object.__setattr__(self, "triage", triage)

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_finding"), name)

    def __repr__(self) -> str:  # pragma: no cover - debug convenience
        finding = object.__getattribute__(self, "_finding")
        triage = object.__getattribute__(self, "triage")
        return f"TriagedFinding({finding!r}, triage={triage!r})"

    @property
    def raw_finding(self) -> Any:
        """The original, unmodified finding object."""
        return object.__getattribute__(self, "_finding")


def _is_low_confidence(finding: Any, threshold: float) -> bool:
    confidence = getattr(finding, "confidence", None)
    if confidence is None:
        # Unknown confidence: treat conservatively as review-worthy so it can
        # be annotated, never as a reason to skip or drop it.
        return True
    try:
        return float(confidence) < threshold
    except (TypeError, ValueError):
        return True


def triage_findings(
    findings: Iterable[Any],
    *,
    enable_assist: bool = False,
    adapter: Optional[TriageAdapter] = None,
    code_reader: Optional[Callable[[Any], str]] = None,
    cache: Optional[TriageCache] = None,
    low_confidence_threshold: float = DEFAULT_LOW_CONFIDENCE_THRESHOLD,
) -> List[Any]:
    """Annotate low-confidence findings with an advisory triage verdict.

    Args:
        findings: the findings to (optionally) triage.
        enable_assist: OPT-IN flag, default False. When False, this function
            is a pure pass-through: it makes no adapter/network calls and
            returns the input list unchanged.
        adapter: a :class:`TriageAdapter` implementation. Defaults to
            :class:`MockTriageAdapter` (never a real/network adapter) so that
            simply setting ``enable_assist=True`` can never by itself trigger
            network traffic -- callers must explicitly pass a real adapter
            (e.g. ``ClaudeTriageAdapter``) to get real triage.
        code_reader: optional callable(finding) -> str for supplying code
            context; defaults to the finding's own ``code_snippet`` attribute
            (or "" if absent).
        cache: optional :class:`TriageCache`; when omitted a default
            ``.asgard_cache/triage``-backed cache is used (itself a no-op
            when ``ASGARD_NO_CACHE`` is set).
        low_confidence_threshold: findings with ``confidence`` below this are
            considered for triage; others pass through unannotated.

    Returns:
        A list with the SAME findings, same order, same length as the input.
        Low-confidence findings may be wrapped in :class:`TriagedFinding`
        (which transparently proxies all original attributes) carrying a
        ``.triage`` verdict; all other findings are returned as-is.
    """
    findings_list = list(findings)

    if not enable_assist:
        # Default path: zero adapter/network calls, findings unchanged.
        return findings_list

    active_adapter: TriageAdapter = adapter if adapter is not None else MockTriageAdapter()
    active_cache = cache if cache is not None else TriageCache()

    results: List[Any] = []
    for finding in findings_list:
        if not _is_low_confidence(finding, low_confidence_threshold):
            results.append(finding)
            continue

        code_context = code_reader(finding) if code_reader else (getattr(finding, "code_snippet", "") or "")
        key = fingerprint(finding, code_context)

        cached_verdict = active_cache.get(key)
        if cached_verdict is not None:
            results.append(TriagedFinding(finding, cached_verdict))
            continue

        try:
            verdict = active_adapter.triage(finding, code_context)
        except Exception as exc:  # noqa: BLE001 - any adapter failure must degrade, never propagate
            verdict = TriageVerdict(
                label=TriageLabel.NOT_AVAILABLE,
                rationale="",
                reason=str(exc),
            )
        else:
            active_cache.set(key, verdict)

        # NEVER change severity, NEVER drop the finding -- only annotate.
        results.append(TriagedFinding(finding, verdict))

    assert len(results) == len(findings_list), "triage_findings must never drop a finding"
    return results
