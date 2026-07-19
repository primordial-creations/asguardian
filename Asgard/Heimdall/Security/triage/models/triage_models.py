"""Data models for the opt-in LLM-assisted triage layer (WS6).

These models are advisory-only annotations. A :class:`TriageVerdict` MUST NEVER be
used to drop a finding, change its ``severity``, or auto-suppress it -- see
``triage_service.triage_findings`` for the enforcement of that invariant.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TriageLabel(str, Enum):
    """Advisory verdict label for a triaged finding.

    ``NOT_AVAILABLE`` is the fail-safe label used whenever the adapter could not
    produce a verdict (error, timeout, missing SDK, opt-in path unreachable) --
    it never implies the finding is safe to drop.
    """

    LIKELY_REAL = "likely_real"
    LIKELY_FALSE_POSITIVE = "likely_false_positive"
    NEEDS_HUMAN = "needs_human"
    NOT_AVAILABLE = "not_available"


class TriageVerdict(BaseModel):
    """Advisory triage annotation attached to a finding's ``triage`` field.

    This is metadata only. Consumers MUST continue to treat the underlying
    finding's ``severity`` as authoritative; ``label`` may only be used to
    re-rank/de-prioritize display ordering, never to filter findings out.
    """

    label: TriageLabel = Field(..., description="Advisory triage verdict label")
    rationale: str = Field("", description="Short human-readable rationale for the verdict")
    confidence: float = Field(
        0.0, ge=0.0, le=1.0, description="Adapter's confidence in this triage verdict (not the finding's severity/confidence)"
    )
    reason: Optional[str] = Field(
        None, description="Set when label is NOT_AVAILABLE: why triage could not be performed"
    )
    from_cache: bool = Field(False, description="True when this verdict was served from the on-disk cache")

    class Config:
        use_enum_values = True
