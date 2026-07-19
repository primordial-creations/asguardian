"""Heimdall Security triage: opt-in LLM-assisted triage layer for low-confidence findings.

Default path (``enable_assist=False``) makes ZERO network/adapter calls and returns
findings unchanged -- see :func:`triage_findings`. This module is independent of the
rest of Security and must never be imported for its side effects to affect a default
scan.
"""

from Asgard.Heimdall.Security.triage.models.triage_models import (
    TriageLabel,
    TriageVerdict,
)
from Asgard.Heimdall.Security.triage.services.triage_adapter import (
    ClaudeTriageAdapter,
    MockTriageAdapter,
    TriageAdapter,
)
from Asgard.Heimdall.Security.triage.services.triage_service import triage_findings

__all__ = [
    "TriageLabel",
    "TriageVerdict",
    "TriageAdapter",
    "MockTriageAdapter",
    "ClaudeTriageAdapter",
    "triage_findings",
]
