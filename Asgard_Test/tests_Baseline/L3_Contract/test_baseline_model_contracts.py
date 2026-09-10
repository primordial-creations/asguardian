"""L3 contracts for the persisted baseline-file model boundary."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from Asgard.Baseline.models import BaselineEntry, BaselineFile, BaselineStats


def _entry(**overrides: object) -> BaselineEntry:
    payload = {
        "file_path": "src/payment.py",
        "line_number": 17,
        "violation_type": "heimdall_secret",
        "violation_id": "secret-17",
        "message": "sha256:stored-identity",
    }
    payload.update(overrides)
    return BaselineEntry(**payload)


class TestBaselineEntryContract:
    def test_requires_persisted_identity_fields(self):
        for missing in (
            "file_path",
            "line_number",
            "violation_type",
            "violation_id",
        ):
            payload = _entry().model_dump()
            payload.pop(missing)

            with pytest.raises(ValidationError):
                BaselineEntry.model_validate(payload)

    @pytest.mark.parametrize(
        ("field", "value"),
        (("line_number", "not-a-line"), ("expires_at", "not-a-timestamp")),
    )
    def test_rejects_values_that_cannot_cross_the_typed_boundary(
        self, field: str, value: object
    ):
        payload = _entry().model_dump()
        payload[field] = value

        with pytest.raises(ValidationError):
            BaselineEntry.model_validate(payload)

    def test_json_round_trip_preserves_identity_and_expiry(self):
        expires_at = datetime(2035, 5, 1, 12, 30, tzinfo=timezone.utc)
        entry = _entry(expires_at=expires_at, reason="accepted risk")

        restored = BaselineEntry.model_validate_json(entry.model_dump_json())

        assert restored == entry
        assert restored.expires_at == expires_at
        assert restored.violation_id == "secret-17"

    def test_expired_entries_cannot_match_at_the_suppression_boundary(self):
        entry = _entry(
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
        )
        restored = BaselineEntry.model_validate_json(entry.model_dump_json())

        assert restored.is_expired
        assert not restored.matches(
            restored.file_path,
            restored.line_number,
            restored.violation_type,
            violation_id=restored.violation_id,
        )

    def test_naive_expiry_remains_backward_compatible(self):
        expired = _entry(expires_at=datetime.now() - timedelta(seconds=1))
        active = _entry(expires_at=datetime.now() + timedelta(minutes=1))

        assert expired.is_expired
        assert not active.is_expired

    def test_aware_expiry_is_normalized_across_timezone_offsets(self):
        offset = timezone(timedelta(hours=10))
        expired = _entry(
            expires_at=datetime.now(offset) - timedelta(seconds=1)
        )
        active = _entry(expires_at=datetime.now(offset) + timedelta(minutes=1))

        assert expired.is_expired
        assert not active.is_expired


class TestBaselineStatsContract:
    def test_default_payload_is_a_zeroed_backward_compatible_shape(self):
        stats = BaselineStats.model_validate({})

        assert stats.model_dump(mode="json") == {
            "total_entries": 0,
            "entries_by_type": {},
            "entries_by_file": {},
            "expired_entries": 0,
            "active_entries": 0,
        }

    def test_rejects_non_numeric_counts(self):
        with pytest.raises(ValidationError):
            BaselineStats.model_validate({"total_entries": "many"})

    def test_json_round_trip_preserves_grouped_counts(self):
        stats = BaselineStats(
            total_entries=2,
            entries_by_type={"heimdall_secret": 2},
            entries_by_file={"src/payment.py": 2},
            active_entries=2,
        )

        assert BaselineStats.model_validate_json(stats.model_dump_json()) == stats


class TestBaselineFileContract:
    def test_legacy_minimal_payload_receives_format_defaults(self):
        baseline = BaselineFile.model_validate({"entries": [_entry().model_dump()]})

        assert baseline.version == "1.0.0"
        assert baseline.project_path == ""
        assert baseline.metadata == {}
        assert len(baseline.entries) == 1
        stored_entry = baseline.entries[0].model_dump(exclude={"created_at"})
        expected_entry = _entry().model_dump(exclude={"created_at"})
        assert stored_entry == expected_entry

    def test_rejects_malformed_nested_entries(self):
        with pytest.raises(ValidationError):
            BaselineFile.model_validate(
                {
                    "entries": [
                        {
                            "file_path": "src/payment.py",
                            "line_number": "not-a-line",
                            "violation_type": "heimdall_secret",
                            "violation_id": "secret-17",
                        }
                    ]
                }
            )

    def test_json_round_trip_preserves_nested_entries_and_metadata(self):
        baseline = BaselineFile(
            project_path="/workspace/project",
            entries=[_entry()],
            metadata={"schema_owner": "heimdall"},
        )

        restored = BaselineFile.model_validate_json(baseline.model_dump_json())

        assert restored == baseline
        assert restored.entries[0].violation_id == "secret-17"

    def test_default_containers_are_isolated_between_documents(self):
        first = BaselineFile()
        second = BaselineFile()

        first.entries.append(_entry())
        first.metadata["owner"] = "team-a"

        assert second.entries == []
        assert second.metadata == {}
