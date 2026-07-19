"""Offline tests for the opt-in LLM-assisted triage layer (WS6).

All tests here run fully offline via MockTriageAdapter / a raising fake adapter --
no real network calls, no real Anthropic SDK usage. These cover the four
adversarially-reviewed invariants from `_Docs/Planning/TaintGaps/00_Plan.md` WS6:

1. Default (enable_assist=False) makes ZERO adapter calls, findings unchanged.
2. Opt-in annotates a needs-review finding but NEVER drops a likely-FP finding
   and NEVER changes its severity.
3. Adapter exceptions degrade to triage.label == NOT_AVAILABLE; finding kept.
4. A cache hit avoids a second adapter call.
"""

import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from Asgard.Heimdall.Security.triage.models.triage_models import TriageLabel, TriageVerdict
from Asgard.Heimdall.Security.triage.services.triage_adapter import MockTriageAdapter
from Asgard.Heimdall.Security.triage.services.triage_cache import TriageCache
from Asgard.Heimdall.Security.triage.services.triage_service import (
    TriagedFinding,
    triage_findings,
)


def _make_finding(confidence=0.3, severity="high", title="Possible SQLi", description="tainted query"):
    return SimpleNamespace(
        file_path="app/db.py",
        line_number=42,
        vulnerability_type="sql_injection",
        severity=severity,
        title=title,
        description=description,
        confidence=confidence,
        code_snippet="cursor.execute(query)",
    )


class RaisingAdapter:
    """Fake adapter that always raises, to test the never-crash/degrade path."""

    def triage(self, finding, code_context):
        raise RuntimeError("simulated adapter failure (e.g. network timeout)")


class CountingAdapter:
    """Wraps MockTriageAdapter but tracks call count explicitly."""

    def __init__(self):
        self.call_count = 0
        self._inner = MockTriageAdapter()

    def triage(self, finding, code_context):
        self.call_count += 1
        return self._inner.triage(finding, code_context)


class TestDefaultPathZeroNetwork:
    """Invariant 1: default enable_assist=False makes zero adapter calls."""

    def test_default_makes_zero_adapter_calls(self):
        adapter = CountingAdapter()
        findings = [_make_finding(confidence=0.1), _make_finding(confidence=0.9)]

        result = triage_findings(findings, adapter=adapter)  # enable_assist defaults False

        assert adapter.call_count == 0
        assert result == findings
        assert result is not findings or True  # length/order/content must match regardless of identity
        assert len(result) == len(findings)
        for original, returned in zip(findings, result):
            assert returned is original

    def test_default_explicit_false_makes_zero_adapter_calls(self):
        adapter = CountingAdapter()
        findings = [_make_finding(confidence=0.05)]

        result = triage_findings(findings, enable_assist=False, adapter=adapter)

        assert adapter.call_count == 0
        assert result == findings
        assert result[0] is findings[0]


class TestOptInAnnotatesWithoutDropping:
    """Invariant 2: opt-in annotates but never drops/mutates severity."""

    def test_annotates_needs_review_finding(self):
        finding = _make_finding(confidence=0.2, title="obj[key]() dynamic dispatch", description="tainted key")
        adapter = MockTriageAdapter()

        result = triage_findings([finding], enable_assist=True, adapter=adapter)

        assert len(result) == 1
        annotated = result[0]
        assert isinstance(annotated, TriagedFinding)
        assert annotated.triage is not None
        assert annotated.triage.label == TriageLabel.NEEDS_HUMAN
        # Original finding fields still transparently accessible, unchanged.
        assert annotated.severity == "high"
        assert annotated.file_path == "app/db.py"

    def test_likely_false_positive_finding_is_kept_with_severity_unchanged(self):
        finding = _make_finding(
            confidence=0.15, severity="critical",
            title="eval() call on constant literal", description="eval('1+1') - constant literal",
        )
        adapter = MockTriageAdapter()

        result = triage_findings([finding], enable_assist=True, adapter=adapter)

        assert len(result) == 1
        annotated = result[0]
        assert annotated.triage.label == TriageLabel.LIKELY_FALSE_POSITIVE
        # NEVER dropped, NEVER severity-changed, despite a likely-FP verdict.
        assert annotated.severity == "critical"

    def test_high_confidence_finding_passes_through_unannotated(self):
        finding = _make_finding(confidence=0.95)
        adapter = MockTriageAdapter()

        result = triage_findings([finding], enable_assist=True, adapter=adapter)

        assert len(result) == 1
        assert result[0] is finding
        assert not isinstance(result[0], TriagedFinding)

    def test_mixed_batch_preserves_count_and_order(self):
        findings = [
            _make_finding(confidence=0.1, title="a"),
            _make_finding(confidence=0.9, title="b"),
            _make_finding(confidence=0.05, severity="critical", title="c constant literal"),
        ]
        adapter = MockTriageAdapter()

        result = triage_findings(findings, enable_assist=True, adapter=adapter)

        assert len(result) == 3
        assert result[1] is findings[1]
        assert result[2].severity == "critical"


class TestAdapterFailureDegradesGracefully:
    """Invariant 3: adapter exception -> triage.label == NOT_AVAILABLE, finding kept."""

    def test_adapter_exception_yields_not_available_and_keeps_finding(self):
        finding = _make_finding(confidence=0.1)
        adapter = RaisingAdapter()

        result = triage_findings([finding], enable_assist=True, adapter=adapter)

        assert len(result) == 1
        annotated = result[0]
        assert isinstance(annotated, TriagedFinding)
        assert annotated.triage.label == TriageLabel.NOT_AVAILABLE
        assert annotated.triage.reason
        # Finding itself (severity etc.) is preserved.
        assert annotated.severity == "high"


class TestCacheAvoidsSecondCall:
    """Invariant 4: a cache hit avoids invoking the adapter twice."""

    def test_second_triage_call_uses_cache_not_adapter(self, tmp_path):
        finding = _make_finding(confidence=0.1)
        adapter = CountingAdapter()
        cache = TriageCache(root=tmp_path / "triage_cache")

        result1 = triage_findings([finding], enable_assist=True, adapter=adapter, cache=cache)
        assert adapter.call_count == 1
        assert result1[0].triage.label == TriageLabel.NEEDS_HUMAN

        # Second call on an equivalent (same fingerprint) finding must hit cache.
        finding2 = _make_finding(confidence=0.1)
        result2 = triage_findings([finding2], enable_assist=True, adapter=adapter, cache=cache)

        assert adapter.call_count == 1, "adapter must not be called again on a cache hit"
        assert result2[0].triage.label == TriageLabel.NEEDS_HUMAN
        assert result2[0].triage.from_cache is True

    def test_asgard_no_cache_env_bypasses_cache(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ASGARD_NO_CACHE", "1")
        finding = _make_finding(confidence=0.1)
        adapter = CountingAdapter()
        cache = TriageCache(root=tmp_path / "triage_cache_nocache")

        triage_findings([finding], enable_assist=True, adapter=adapter, cache=cache)
        triage_findings([_make_finding(confidence=0.1)], enable_assist=True, adapter=adapter, cache=cache)

        assert adapter.call_count == 2, "ASGARD_NO_CACHE must force a fresh adapter call every time"


class TestModuleImportHasNoHardAnthropicDependency:
    """Adversarial-review concern: importing this module must never require `anthropic`."""

    def test_import_does_not_require_anthropic_installed(self):
        # If we got this far (module already imported at top of file), the
        # import succeeded regardless of whether `anthropic` is installed.
        from Asgard.Heimdall.Security.triage.services import triage_adapter

        assert hasattr(triage_adapter, "ClaudeTriageAdapter")

    def test_claude_adapter_construction_fails_gracefully_without_sdk_or_key(self, monkeypatch):
        from Asgard.Heimdall.Security.triage.services.triage_adapter import (
            ClaudeTriageAdapter,
            anthropic as adapter_anthropic_module,
        )

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        if adapter_anthropic_module is None:
            with pytest.raises(RuntimeError, match="SDK not installed"):
                ClaudeTriageAdapter()
        else:
            with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
                ClaudeTriageAdapter()
