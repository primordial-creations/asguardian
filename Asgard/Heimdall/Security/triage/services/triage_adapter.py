"""Provider-agnostic triage adapter interface + Mock and Claude implementations.

Importing this module MUST NEVER require the ``anthropic`` package or perform any
network I/O -- the ``anthropic`` SDK is an optional import used only inside
:class:`ClaudeTriageAdapter`, and only when that adapter is actually invoked from the
opt-in path (``enable_assist=True``).
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from Asgard.Heimdall.Security.triage.models.triage_models import TriageLabel, TriageVerdict

try:  # Optional dependency -- must never be a hard import failure.
    import anthropic  # type: ignore
except ImportError:  # pragma: no cover - exercised implicitly whenever SDK absent
    anthropic = None  # type: ignore


class TriageAdapter(ABC):
    """Abstract interface for a pluggable LLM-assisted triage backend.

    Implementations are advisory-only: a verdict returned here is never used to
    drop a finding, change its severity, or auto-suppress it (that invariant is
    enforced by ``triage_service.triage_findings``, not by adapters).
    """

    @abstractmethod
    def triage(self, finding: Any, code_context: str) -> TriageVerdict:
        """Return a :class:`TriageVerdict` for a single finding + surrounding code.

        Implementations should raise on unrecoverable failure; callers are
        responsible for catching exceptions and degrading to NOT_AVAILABLE.
        """
        raise NotImplementedError


class MockTriageAdapter(TriageAdapter):
    """Deterministic offline adapter for tests. Makes no network calls.

    Verdict is derived from a simple, deterministic rule so tests can assert
    exact output: findings whose ``title``/``description``/``vulnerability_type``
    contains "constant" or "literal" are labelled likely-false-positive; all
    others are labelled needs-human. This is intentionally simplistic -- it
    exists only to exercise the annotate/never-drop plumbing in tests.
    """

    def __init__(self, fixed_label: Optional[TriageLabel] = None, calls: Optional[list] = None):
        self.fixed_label = fixed_label
        # Optional call-spy list; each triage() call appends (finding, code_context).
        self.calls = calls if calls is not None else []

    def triage(self, finding: Any, code_context: str) -> TriageVerdict:
        self.calls.append((finding, code_context))
        if self.fixed_label is not None:
            label = self.fixed_label
        else:
            text = " ".join(
                str(getattr(finding, attr, "") or "")
                for attr in ("title", "description", "vulnerability_type")
            ).lower()
            if "constant" in text or "literal" in text:
                label = TriageLabel.LIKELY_FALSE_POSITIVE
            else:
                label = TriageLabel.NEEDS_HUMAN
        return TriageVerdict(
            label=label,
            rationale="mock adapter deterministic verdict (offline, no network)",
            confidence=0.5,
        )


class ClaudeTriageAdapter(TriageAdapter):
    """Real triage adapter backed by the Anthropic Messages API.

    Optional dependency: requires the ``anthropic`` package to be installed and
    ``ANTHROPIC_API_KEY`` to be set in the environment. Neither is required to
    import this module or the rest of the ``triage`` package -- construction
    (not import) is where the SDK is actually needed, and callers should treat
    a missing SDK/key as a normal degrade-to-``not_available`` path, not a
    crash.
    """

    # Per the claude-api skill's "Current Models" table (cached 2026-06-24):
    # default flagship model id absent an explicit user override.
    # verify model id
    MODEL_ID = "claude-opus-4-8"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        if anthropic is None:
            raise RuntimeError(
                "assist unavailable (SDK not installed): the 'anthropic' package "
                "is not installed; run `pip install anthropic` to enable "
                "ClaudeTriageAdapter, or continue using MockTriageAdapter."
            )
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "assist unavailable: ANTHROPIC_API_KEY is not set in the environment."
            )
        self._client = anthropic.Anthropic(api_key=key)
        self._model = model or self.MODEL_ID

    def triage(self, finding: Any, code_context: str) -> TriageVerdict:
        prompt = (
            "You are assisting a static-analysis triage step. Given a low-confidence "
            "security finding and its surrounding code, return ONLY a JSON object "
            '{"label": "likely_real"|"likely_false_positive"|"needs_human", '
            '"rationale": "<short reason>", "confidence": <0..1 float>}.\n\n'
            f"Finding: {getattr(finding, 'title', '')} - {getattr(finding, 'description', '')}\n"
            f"Code:\n{code_context}\n"
        )
        response = self._client.messages.create(
            model=self._model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        data: Dict[str, Any] = json.loads(text)
        return TriageVerdict(
            label=TriageLabel(data["label"]),
            rationale=str(data.get("rationale", "")),
            confidence=float(data.get("confidence", 0.0)),
        )
