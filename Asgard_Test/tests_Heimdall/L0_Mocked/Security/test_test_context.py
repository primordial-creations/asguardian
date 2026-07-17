"""
Tests for the Test-Context Engine (plan 08 Part B, DEEPTHINK_08/03).

Covers the path-heuristic failure-mode table verbatim, AST-level
TEST_FUNCTION tainting, the contextual severity matrix (secrets never
suppressed), pragma/strict-path overrides, and priority modifiers.
"""

import pytest

from Asgard.Heimdall.Security.context.test_context import (
    ContextAction,
    ContextTag,
    FindingKind,
    TestContextIndex,
    apply_test_context,
    classify_file_context,
    contextual_action,
    finding_kind_for_cwe,
    is_test_context,
)
from Asgard.Heimdall.Security.normalization.priority import (
    context_modifier_for_tag,
)


class TestPathHeuristics:
    """The DEEPTHINK_08 failure-mode table, verbatim."""

    @pytest.mark.parametrize("path,expected", [
        # Canonical test files.
        ("tests/test_api.py", ContextTag.TEST_UNIT),
        ("pkg/tests/unit/test_models.py", ContextTag.TEST_UNIT),
        ("src/__tests__/app.test.js", ContextTag.TEST_UNIT),
        ("spec/user_spec_test.rb", ContextTag.TEST_UNIT),
        # Integration flavours.
        ("tests/integration/test_db.py", ContextTag.TEST_INTEGRATION),
        ("tests/e2e/test_login.py", ContextTag.TEST_INTEGRATION),
        ("system/tests/test_boot.py", ContextTag.TEST_INTEGRATION),
        # Standalone test-infrastructure files.
        ("conftest.py", ContextTag.TEST_UNIT),
        ("src/app/conftest.py", ContextTag.TEST_UNIT),
        ("noxfile.py", ContextTag.TEST_UNIT),
        # Failure modes that must stay PRODUCTION:
        ("ab_testing/experiment.py", ContextTag.PRODUCTION),
        ("ab_testing/test_flight_api.py", ContextTag.PRODUCTION),  # dir not a test dir? test_ file needs test dir
        ("scripts/test_db_connection.py", ContextTag.PRODUCTION),  # prod script, no test dir
        ("src/protest/handler.py", ContextTag.PRODUCTION),
        ("src/app/main.py", ContextTag.PRODUCTION),
        ("testing_tools/deploy.py", ContextTag.PRODUCTION),
        # Toolchain-enforced test suffixes qualify standalone.
        ("pkg/server_test.go", ContextTag.TEST_UNIT),
        ("src/Button.spec.tsx", ContextTag.TEST_UNIT),
    ])
    def test_classification_table(self, path, expected):
        assert classify_file_context(path) is expected

    def test_ab_testing_dir_with_test_filename_stays_production(self):
        # /ab_testing/ must not word-boundary-match the test dir regex.
        assert classify_file_context("ab_testing/test_flight_api.py") is ContextTag.PRODUCTION

    def test_windows_separators_normalized(self):
        assert classify_file_context(r"tests\test_api.py") is ContextTag.TEST_UNIT

    def test_strict_scan_paths_bypass(self):
        # Student-exam scenario: an app dir literally named test/, opted
        # back into full scanning via strict paths.
        assert classify_file_context(
            "tests/security/test_auth_regression.py",
            strict_scan_paths=[r"tests/security/.*"],
        ) is ContextTag.PRODUCTION

    def test_is_test_context_helper(self):
        assert is_test_context("tests/test_x.py") is True
        assert is_test_context("src/main.py") is False


class TestASTLevelTainting:
    """TEST_FUNCTION context pushes/pops with AST scope in prod files."""

    def _index(self, source, path="src/utils.py"):
        return TestContextIndex.for_python_source(path, source)

    def test_pytest_fixture_in_prod_file_tagged(self):
        src = (
            "import pytest\n"
            "@pytest.fixture\n"
            "def fake_creds():\n"
            "    return 'md5'\n"
            "def real_helper():\n"
            "    return 1\n"
        )
        idx = self._index(src)
        assert idx.tag_for_line(4) is ContextTag.TEST_FUNCTION
        assert idx.tag_for_line(6) is ContextTag.PRODUCTION

    def test_mock_patch_decorator_tagged(self):
        src = (
            "from unittest import mock\n"
            "@mock.patch('requests.get')\n"
            "def helper(m):\n"
            "    return m\n"
        )
        assert self._index(src).tag_for_line(4) is ContextTag.TEST_FUNCTION

    def test_unittest_testcase_class_tagged(self):
        src = (
            "import unittest\n"
            "class ThingTests(unittest.TestCase):\n"
            "    def test_one(self):\n"
            "        self.assertEqual(1, 1)\n"
        )
        assert self._index(src).tag_for_line(4) is ContextTag.TEST_FUNCTION

    def test_test_named_function_with_assert_tagged(self):
        src = (
            "def test_hash():\n"
            "    assert hash_it('a')\n"
        )
        assert self._index(src).tag_for_line(2) is ContextTag.TEST_FUNCTION

    def test_test_named_function_without_assert_not_tagged(self):
        src = (
            "def test_connection():\n"
            "    return connect()\n"
        )
        assert self._index(src).tag_for_line(2) is ContextTag.PRODUCTION

    def test_prod_helper_in_test_file_gets_file_tag(self):
        # File-level tag wins for files already classified as tests.
        src = "def helper():\n    return 1\n"
        idx = TestContextIndex.for_python_source("tests/test_x.py", src)
        assert idx.tag_for_line(2) is ContextTag.TEST_UNIT

    def test_enforce_pragma_strips_line(self):
        src = "def helper():\n    x = 1  # heimdall: enforce\n"
        idx = TestContextIndex.for_python_source("tests/test_x.py", src)
        assert idx.tag_for_line(2) is ContextTag.PRODUCTION
        assert idx.tag_for_line(1) is ContextTag.TEST_UNIT

    def test_enforce_pragma_on_def_line_strips_scope(self):
        src = (
            "import pytest\n"
            "@pytest.fixture\n"
            "def creds():  # heimdall: enforce\n"
            "    return 'x'\n"
        )
        idx = self._index(src)
        assert idx.tag_for_line(4) is ContextTag.PRODUCTION


class TestSeverityMatrix:
    """The contextual severity matrix, row by row."""

    @pytest.mark.parametrize("kind,unit,integration", [
        (FindingKind.DATA_FLOW_INJECTION, ContextAction.SUPPRESS, ContextAction.SUPPRESS),
        (FindingKind.WEAK_CRYPTO, ContextAction.SUPPRESS, ContextAction.SUPPRESS),
        (FindingKind.COMMAND_INJECTION, ContextAction.SUPPRESS, ContextAction.DOWNGRADE_LOW),
        (FindingKind.SSRF, ContextAction.SUPPRESS, ContextAction.DOWNGRADE_LOW),
        (FindingKind.NETWORK_CONFIG, ContextAction.SUPPRESS, ContextAction.DOWNGRADE_INFO),
        (FindingKind.HARDCODED_SECRET, ContextAction.KEEP, ContextAction.KEEP),
    ])
    def test_matrix_rows(self, kind, unit, integration):
        assert contextual_action(kind, ContextTag.TEST_UNIT) is unit
        assert contextual_action(kind, ContextTag.TEST_FUNCTION) is unit
        assert contextual_action(kind, ContextTag.TEST_INTEGRATION) is integration

    def test_production_always_keeps(self):
        for kind in FindingKind:
            assert contextual_action(kind, ContextTag.PRODUCTION) is ContextAction.KEEP

    def test_secrets_never_suppressed_in_any_context(self):
        for tag in ContextTag:
            decision = apply_test_context("critical", tag, kind=FindingKind.HARDCODED_SECRET)
            assert decision.suppressed_by_context is False
            assert decision.severity == "critical"

    def test_suppressed_findings_retained_not_deleted(self):
        decision = apply_test_context("high", ContextTag.TEST_UNIT, cwe_id="CWE-89")
        assert decision.suppressed_by_context is True
        # Severity retained: suppression is a routing flag, not a downgrade.
        assert decision.severity == "high"

    def test_downgrade_low_in_integration(self):
        decision = apply_test_context("critical", ContextTag.TEST_INTEGRATION, cwe_id="CWE-78")
        assert decision.suppressed_by_context is False
        assert decision.severity == "low"

    def test_network_config_downgrades_to_info_in_integration(self):
        decision = apply_test_context("medium", ContextTag.TEST_INTEGRATION, cwe_id="CWE-295")
        assert decision.severity == "info"

    def test_unknown_kind_kept(self):
        decision = apply_test_context("high", ContextTag.TEST_UNIT, cwe_id="CWE-9999")
        assert decision.suppressed_by_context is False


class TestCweMapping:
    @pytest.mark.parametrize("cwe,kind", [
        ("CWE-89", FindingKind.DATA_FLOW_INJECTION),
        ("CWE-79", FindingKind.DATA_FLOW_INJECTION),
        ("CWE-22", FindingKind.DATA_FLOW_INJECTION),
        ("CWE-327", FindingKind.WEAK_CRYPTO),
        ("CWE-338", FindingKind.WEAK_CRYPTO),
        ("CWE-78", FindingKind.COMMAND_INJECTION),
        ("CWE-918", FindingKind.SSRF),
        ("CWE-295", FindingKind.NETWORK_CONFIG),
        ("CWE-798", FindingKind.HARDCODED_SECRET),
        (None, FindingKind.OTHER),
        ("", FindingKind.OTHER),
    ])
    def test_mapping(self, cwe, kind):
        assert finding_kind_for_cwe(cwe) is kind


class TestPriorityContextModifiers:
    def test_modifiers(self):
        assert context_modifier_for_tag("production") == 1.0
        assert context_modifier_for_tag("test_integration") == 0.5
        assert context_modifier_for_tag("test_unit") == 0.25
        assert context_modifier_for_tag("test_function") == 0.25
        assert context_modifier_for_tag("unknown_tag") == 1.0


class TestTaintAnalyzerIntegration:
    """The taint engine's test-path handling delegates to this engine."""

    def test_taint_is_test_path_uses_conjunction(self):
        from pathlib import Path
        from Asgard.Heimdall.Security.TaintAnalysis.services.taint_analyzer import (
            _is_test_path,
        )
        assert _is_test_path(Path("tests/test_api.py")) is True
        assert _is_test_path(Path("conftest.py")) is True
        # Old heuristic false positives, now correct:
        assert _is_test_path(Path("scripts/test_db_connection.py")) is False

    def test_dispatch_engine_auto_classifies(self, tmp_path):
        from Asgard.Heimdall.Security.engine.dispatch import DispatchEngine
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        f = tests_dir / "test_handler.py"
        f.write_text(
            "def handler():\n"
            "    q = request.args.get('q')\n"
            "    cursor.execute(q)\n"
        )
        engine = DispatchEngine()
        result = engine.scan_file(f)
        assert engine.is_test_context is True
        for flow in result.taint_flows:
            assert flow.confidence <= 0.1

    def test_dispatch_secrets_never_capped_by_test_context(self, tmp_path):
        from Asgard.Heimdall.Security.engine.dispatch import DispatchEngine
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        f = tests_dir / "conftest.py"
        # High-entropy GitHub PAT in a conftest fixture: stays high-confidence.
        f.write_text("PAT = 'ghp_" + "K7q9ZrT2wXv4bN8mJ5cH1sD3fG6hL0pQaEuY" + "'\n")
        result = DispatchEngine().scan_file(f)
        hits = [x for x in result.structural_findings if x.rule_id == "L1.github_token"]
        assert len(hits) == 1
        assert hits[0].confidence >= 0.9

    def test_dispatch_dummy_secrets_dropped(self, tmp_path):
        from Asgard.Heimdall.Security.engine.dispatch import DispatchEngine
        f = tmp_path / "conftest.py"
        f.write_text(
            "AWS = 'AKIAXXXXXXXXXXXXXXXX'\n"
            "K2 = 'AKIA1234567890123456'\n"
        )
        result = DispatchEngine().scan_file(f)
        assert [x for x in result.structural_findings if x.layer == 1] == []


class TestFindingModelFields:
    def test_vulnerability_finding_has_context_fields(self):
        from Asgard.Heimdall.Security.models.security_models_base import (
            SecuritySeverity,
            VulnerabilityFinding,
            VulnerabilityType,
        )
        finding = VulnerabilityFinding(
            file_path="/x.py", line_number=1,
            vulnerability_type=list(VulnerabilityType)[0],
            severity=SecuritySeverity.HIGH,
            title="t", description="d", confidence=0.9,
        )
        assert finding.context_tag == "production"
        assert finding.suppressed_by_context is False

    def test_secret_finding_has_context_fields(self):
        from Asgard.Heimdall.Security.models.security_models_base import (
            SecretFinding,
            SecretType,
            SecuritySeverity,
        )
        finding = SecretFinding(
            file_path="/x.py", line_number=1,
            secret_type=list(SecretType)[0],
            severity=SecuritySeverity.CRITICAL,
            pattern_name="p", masked_value="***", line_content="l",
            confidence=0.99,
        )
        assert finding.context_tag == "production"
        assert finding.suppressed_by_context is False
