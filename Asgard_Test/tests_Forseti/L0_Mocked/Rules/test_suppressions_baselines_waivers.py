"""Tests for inline suppressions, baselines and epoch waivers (plan 02)."""

from datetime import date

from Asgard.Forseti.Reporting.models.finding_models import Coordinates, Finding
from Asgard.Forseti.Rules.models._rule_base_models import SchemaFormat, Severity
from Asgard.Forseti.Rules.services._suppression_helpers import (
    MISSING_REASON_RULE,
    apply_suppressions,
    collect_suppressions,
    parse_comment_suppressions,
)
from Asgard.Forseti.Rules.services.baseline_service import BaselineService
from Asgard.Forseti.Rules.services.waiver_service import WaiverService


def _finding(rule_id="oas.docs.description-required", json_path="/paths/~1users/get",
             severity=Severity.WARNING, message="Missing description") -> Finding:
    return Finding(
        rule_id=rule_id,
        severity=severity,
        message=message,
        coordinates=Coordinates(file="api.yaml", json_path=json_path),
    )


class TestInlineSuppressions:
    def test_collects_scoped_entries(self):
        doc = {
            "paths": {
                "/users": {
                    "get": {
                        "x-forseti-ignore": [
                            {"rule": "oas.docs.description-required",
                             "reason": "legacy consumer"},
                        ],
                    },
                },
            },
        }
        entries = collect_suppressions(doc)
        assert len(entries) == 1
        assert entries[0].scope == "/paths/~1users/get"
        assert entries[0].has_reason

    def test_suppression_marks_finding_and_keeps_it(self):
        doc_findings = [_finding()]
        entries = collect_suppressions({
            "paths": {"/users": {"get": {"x-forseti-ignore": [
                {"rule": "oas.docs.*", "reason": "legacy"}]}}},
        })
        result = apply_suppressions(doc_findings, entries)
        assert result[0].suppressed is True
        assert result[0].suppression_reason == "legacy"

    def test_missing_reason_is_itself_a_warning(self):
        entries = collect_suppressions({
            "x-forseti-ignore": [{"rule": "oas.docs.description-required"}],
        })
        result = apply_suppressions([_finding()], entries)
        warning = [f for f in result if f.rule_id == MISSING_REASON_RULE]
        assert len(warning) == 1
        assert warning[0].severity == Severity.WARNING

    def test_core_rules_cannot_be_suppressed(self):
        finding = _finding(rule_id="oas.structure.required-field",
                           severity=Severity.ERROR)
        entries = collect_suppressions({
            "x-forseti-ignore": [{"rule": "oas.structure.required-field",
                                  "reason": "please"}],
        })
        result = apply_suppressions([finding], entries,
                                    core_rule_ids={"oas.structure.required-field"})
        assert result[0].suppressed is False

    def test_comment_suppressions_parse(self):
        text = "syntax = \"proto3\";\n// forseti:ignore proto.style.naming-convention legacy names\n"
        entries = parse_comment_suppressions(text)
        assert entries[0].rule == "proto.style.naming-convention"
        assert entries[0].reason == "legacy names"
        assert entries[0].scope == "line:2"

    def test_comment_suppression_without_reason(self):
        entries = parse_comment_suppressions("# forseti:ignore sql.style.x\n")
        assert entries[0].reason is None


class TestBaselineRoundTrip:
    def test_baseline_round_trip_and_boy_scout(self, tmp_path):
        doc = {"paths": {"/users": {"get": {"summary": "old"}}}}
        service = BaselineService(tmp_path / "baseline.json")
        finding = _finding(json_path="/paths/~1users/get")

        # 1. baseline created -> rerun is clean
        service.update([finding], doc)
        rerun = service.apply([_finding(json_path="/paths/~1users/get")], doc)
        assert rerun[0].suppressed and rerun[0].suppression_reason == "baseline"

        # 2. net-new violation is still reported
        new = _finding(rule_id="oas.docs.other-rule", json_path="/paths/~1users/get")
        applied = service.apply([new], doc)
        assert applied[0].suppressed is False

        # 3. editing the baselined node revokes the exemption
        edited_doc = {"paths": {"/users": {"get": {"summary": "changed"}}}}
        resurfaced = service.apply([_finding(json_path="/paths/~1users/get")], edited_doc)
        assert resurfaced[0].suppressed is False

    def test_suppressed_findings_not_baselined(self, tmp_path):
        service = BaselineService(tmp_path / "baseline.json")
        finding = _finding()
        finding.suppressed = True
        assert service.update([finding], {}) == 0


class TestWaivers:
    def _write(self, tmp_path, expires="2099-01-01"):
        (tmp_path / "waivers.yaml").write_text(
            "waivers:\n"
            "  - rule: FIELD_REMOVED\n"
            "    location: User.address\n"
            "    from: v1.5\n"
            "    to: v2.0\n"
            "    reason: consumer migration in progress\n"
            f"    expires: {expires}\n"
        )
        return WaiverService(tmp_path / "waivers.yaml")

    def test_waiver_matches_exact_epoch(self, tmp_path):
        service = self._write(tmp_path)
        assert service.is_waived("FIELD_REMOVED", "User.address", "v1.5", "v2.0",
                                 today=date(2026, 1, 1)) is not None

    def test_waiver_applies_only_to_exact_version_pair(self, tmp_path):
        service = self._write(tmp_path)
        assert service.is_waived("FIELD_REMOVED", "User.address", "v2.0", "v2.1",
                                 today=date(2026, 1, 1)) is None

    def test_expired_waiver_is_ignored(self, tmp_path):
        service = self._write(tmp_path, expires="2020-01-01")
        assert service.is_waived("FIELD_REMOVED", "User.address", "v1.5", "v2.0",
                                 today=date(2026, 1, 1)) is None

    def test_missing_file_yields_no_waivers(self, tmp_path):
        assert WaiverService(tmp_path / "nope.yaml").load() == []
