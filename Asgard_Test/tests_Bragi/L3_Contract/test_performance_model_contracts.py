"""L3 Contract tests for Bragi Performance outcome models.

``AnalyzerOutcome`` records whether one configured performance analyzer
completed, independent of whatever findings it produced -- it is the
completion/skip/failure signal consumers use to decide whether a report's
absence of findings is trustworthy.
"""
import pytest
from pydantic import ValidationError

from Asgard.Bragi.Performance.models._performance_reports import AnalyzerOutcome


class TestAnalyzerOutcomeContract:
    def test_requires_status_and_required(self):
        with pytest.raises(ValidationError):
            AnalyzerOutcome()

    @pytest.mark.parametrize("status", ["succeeded", "failed", "unavailable", "skipped"])
    def test_accepts_every_documented_status(self, status):
        outcome = AnalyzerOutcome(status=status, required=True)
        assert outcome.status == status

    def test_rejects_unknown_status(self):
        with pytest.raises(ValidationError):
            AnalyzerOutcome(status="pending", required=True)

    def test_diagnostic_defaults_to_none_and_round_trips(self):
        outcome = AnalyzerOutcome(status="succeeded", required=False)
        assert outcome.diagnostic is None

        failed = AnalyzerOutcome(
            status="failed", required=True, diagnostic="analyzer crashed"
        )
        assert failed.diagnostic == "analyzer crashed"

    def test_required_flag_is_boolean(self):
        outcome = AnalyzerOutcome(status="skipped", required=False)
        assert outcome.required is False
