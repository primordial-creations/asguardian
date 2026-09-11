"""L3 Contract tests for Freya Responsive outcome and hover-evidence models.

``MobileCheckOutcome`` is the completion signal for a required mobile
observation, separate from any ``MobileCompatibilityIssue`` findings it
produced. ``HoverCandidate``/``HoverInventory`` are the strict, bounded
evidence models the hover/focus-visibility crawler produces -- both use
``ConfigDict(strict=True)``, so type coercion (e.g. int-for-str) must be
rejected, and both fields are capped via ``max_length`` to bound crawl cost.
"""
import pytest
from pydantic import ValidationError

from Asgard.Freya.Responsive.models.responsive_models import MobileCheckOutcome
from Asgard.Freya.Responsive.services._hover_evidence import (
    HoverCandidate,
    HoverInventory,
)


class TestMobileCheckOutcomeContract:
    def test_requires_status(self):
        with pytest.raises(ValidationError):
            MobileCheckOutcome()

    @pytest.mark.parametrize("status", ["succeeded", "failed", "incomplete"])
    def test_accepts_every_documented_status(self, status):
        outcome = MobileCheckOutcome(status=status)
        assert outcome.status == status

    def test_rejects_unknown_status(self):
        with pytest.raises(ValidationError):
            MobileCheckOutcome(status="pending")

    def test_diagnostic_and_limitations_default_and_round_trip(self):
        outcome = MobileCheckOutcome(status="succeeded")
        assert outcome.diagnostic is None
        assert outcome.limitations == []

        incomplete = MobileCheckOutcome(
            status="incomplete",
            diagnostic="viewport emulation unavailable",
            limitations=["no touch emulation"],
        )
        assert incomplete.diagnostic == "viewport emulation unavailable"
        assert incomplete.limitations == ["no touch emulation"]

    def test_limitations_lists_are_isolated_between_instances(self):
        first = MobileCheckOutcome(status="succeeded")
        second = MobileCheckOutcome(status="succeeded")

        first.limitations.append("mutated")
        assert second.limitations == []


def _candidate(**overrides):
    payload = {
        "trigger": ".menu-item:hover",
        "target": ".submenu",
        "rule": ":hover { display: block; }",
        "declared_alternative": False,
    }
    payload.update(overrides)
    return HoverCandidate(**payload)


class TestHoverCandidateContract:
    def test_requires_every_field(self):
        with pytest.raises(ValidationError):
            HoverCandidate()

    def test_accepts_valid_candidate(self):
        candidate = _candidate()
        assert candidate.trigger == ".menu-item:hover"
        assert candidate.declared_alternative is False

    def test_strict_mode_rejects_type_coercion(self):
        with pytest.raises(ValidationError):
            _candidate(declared_alternative="false")

    def test_rejects_overlong_string_fields(self):
        with pytest.raises(ValidationError):
            _candidate(trigger="x" * 4097)


class TestHoverInventoryContract:
    def test_requires_candidates_and_limitations(self):
        with pytest.raises(ValidationError):
            HoverInventory()

    def test_accepts_valid_inventory(self):
        inventory = HoverInventory(candidates=[_candidate()], limitations=[])
        assert inventory.candidates[0].target == ".submenu"
        assert inventory.limitations == []

    def test_empty_inventory_round_trips(self):
        inventory = HoverInventory(candidates=[], limitations=["dom traversal capped"])
        assert inventory.candidates == []
        assert inventory.limitations == ["dom traversal capped"]

    def test_rejects_more_than_twenty_candidates(self):
        with pytest.raises(ValidationError):
            HoverInventory(candidates=[_candidate() for _ in range(21)], limitations=[])

    def test_rejects_more_than_twenty_limitations(self):
        with pytest.raises(ValidationError):
            HoverInventory(candidates=[], limitations=["capped"] * 21)

    def test_strict_mode_rejects_non_list_candidates(self):
        with pytest.raises(ValidationError):
            HoverInventory(candidates=(_candidate(),), limitations=[])
