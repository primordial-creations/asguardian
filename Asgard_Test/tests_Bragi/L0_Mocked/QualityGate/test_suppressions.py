"""
Tests for structured suppressions (Plan Heimdall-09 §3).

Reason-mandatory, machine-readable inline ignores: valid FP passes, bare
ignore fails, expired RISK ACCEPTED fails, FP never expires.
"""

from datetime import date

from Asgard.Bragi.QualityGate.suppressions import (
    SuppressionKind,
    lint_suppressions,
    parse_suppression_comment,
    parse_suppressions,
)

TODAY = date(2026, 7, 17)


class TestParsing:
    def test_valid_fp_suppression(self):
        d = parse_suppression_comment(
            "# heimdall-ignore: SQLI - FP: input cast to int before query"
        )
        assert d is not None
        assert d.valid is True
        assert d.rule_id == "SQLI"
        assert d.kind == SuppressionKind.FALSE_POSITIVE or d.kind == "fp"
        assert "cast to int" in d.reason

    def test_valid_risk_accepted_suppression(self):
        d = parse_suppression_comment(
            "# heimdall-ignore: SQLI - RISK ACCEPTED until 2026-12-01 - TICKET-123"
        )
        assert d is not None
        assert d.valid is True
        assert d.kind == SuppressionKind.RISK_ACCEPTED or d.kind == "risk_accepted"
        assert d.expires == date(2026, 12, 1)
        assert d.ticket == "TICKET-123"

    def test_bare_ignore_is_invalid(self):
        d = parse_suppression_comment("# heimdall-ignore: SQLI")
        assert d is not None
        assert d.valid is False
        assert "justification" in d.error

    def test_malformed_justification_is_invalid(self):
        d = parse_suppression_comment("# heimdall-ignore: SQLI - because I said so")
        assert d is not None
        assert d.valid is False

    def test_invalid_date_is_invalid(self):
        d = parse_suppression_comment(
            "# heimdall-ignore: SQLI - RISK ACCEPTED until 2026-13-45 - TICKET-1"
        )
        assert d is not None
        assert d.valid is False

    def test_non_directive_line_returns_none(self):
        assert parse_suppression_comment("x = 1  # ordinary comment") is None

    def test_asgard_ignore_marker_supported(self):
        d = parse_suppression_comment("# asgard-ignore: XSS - FP: escaped upstream")
        assert d is not None and d.valid is True

    def test_slash_comment_leader_supported(self):
        d = parse_suppression_comment("// heimdall-ignore: XSS - FP: sanitized")
        assert d is not None and d.valid is True

    def test_parse_suppressions_scans_source(self):
        source = (
            "def f():\n"
            "    q = build(x)  # heimdall-ignore: SQLI - FP: x is an int enum\n"
            "    return q\n"
        )
        directives = parse_suppressions(source, file_path="src/mod.py")
        assert len(directives) == 1
        assert directives[0].line == 2
        assert directives[0].file_path == "src/mod.py"


class TestExpiry:
    def test_fp_never_expires(self):
        d = parse_suppression_comment("# heimdall-ignore: SQLI - FP: safe")
        assert d.is_expired(date(2099, 1, 1)) is False
        assert d.is_active(date(2099, 1, 1)) is True

    def test_risk_accepted_active_before_expiry(self):
        d = parse_suppression_comment(
            "# heimdall-ignore: SQLI - RISK ACCEPTED until 2026-12-01 - T-1"
        )
        assert d.is_active(TODAY) is True

    def test_risk_accepted_expired_after_date(self):
        d = parse_suppression_comment(
            "# heimdall-ignore: SQLI - RISK ACCEPTED until 2026-01-01 - T-1"
        )
        assert d.is_expired(TODAY) is True
        assert d.is_active(TODAY) is False


class TestLinter:
    def test_valid_directives_produce_no_violations(self):
        directives = parse_suppressions(
            "# heimdall-ignore: A - FP: reason\n"
            "# heimdall-ignore: B - RISK ACCEPTED until 2099-01-01 - T-9\n"
        )
        assert lint_suppressions(directives, TODAY) == []

    def test_bare_ignore_fails_lint(self):
        directives = parse_suppressions("# heimdall-ignore: SQLI\n")
        violations = lint_suppressions(directives, TODAY)
        assert len(violations) == 1

    def test_expired_risk_accepted_fails_lint(self):
        directives = parse_suppressions(
            "# heimdall-ignore: SQLI - RISK ACCEPTED until 2020-01-01 - T-2\n"
        )
        violations = lint_suppressions(directives, TODAY)
        assert len(violations) == 1
        assert "expired" in violations[0]
