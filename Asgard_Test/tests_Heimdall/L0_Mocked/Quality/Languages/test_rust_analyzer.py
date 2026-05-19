"""Unit tests for the Rust analyzer."""

import pytest
from Asgard.Heimdall.Quality.languages.rust.models.rust_models import (
    RustScanConfig, RustSeverity, RustRuleCategory,
)
from Asgard.Heimdall.Quality.languages.rust.services._rust_rules import (
    check_unsafe_block,
    check_unwrap_in_production,
    check_transmute,
    check_command_injection,
    check_hardcoded_credentials,
    check_path_traversal,
)
from Asgard.Heimdall.Quality.languages.rust.services.rust_analyzer import RustAnalyzer


class TestRustAnalyzerInit:
    def test_default_config(self):
        analyzer = RustAnalyzer()
        assert analyzer._config is not None
        assert ".rs" in analyzer._config.include_extensions
        assert analyzer._config.max_findings == 1000

    def test_custom_config(self):
        config = RustScanConfig(max_findings=200)
        analyzer = RustAnalyzer(config=config)
        assert analyzer._config.max_findings == 200


class TestRustUnsafeBlock:
    def test_unsafe_block_flagged(self):
        lines = ['    unsafe {']
        findings = check_unsafe_block("lib.rs", lines)
        assert len(findings) == 1
        assert findings[0].rule_id == "rust.unsafe-block"

    def test_unsafe_fn_flagged(self):
        lines = ['pub unsafe fn dangerous() {']
        findings = check_unsafe_block("lib.rs", lines)
        assert len(findings) == 1

    def test_safe_code_not_flagged(self):
        lines = ['fn safe_function() {']
        findings = check_unsafe_block("lib.rs", lines)
        assert len(findings) == 0

    def test_disabled_rule_returns_empty(self):
        lines = ['unsafe {']
        findings = check_unsafe_block("lib.rs", lines, enabled=False)
        assert findings == []


class TestRustUnwrap:
    def test_unwrap_flagged(self):
        lines = ['    let val = result.unwrap();']
        findings = check_unwrap_in_production("lib.rs", lines)
        assert len(findings) == 1
        assert findings[0].rule_id == "rust.unwrap-in-production"
        assert findings[0].severity == RustSeverity.WARNING

    def test_expect_flagged(self):
        lines = ['    let val = result.expect("oh no");']
        findings = check_unwrap_in_production("lib.rs", lines)
        assert len(findings) == 1

    def test_question_mark_not_flagged(self):
        lines = ['    let val = result?;']
        findings = check_unwrap_in_production("lib.rs", lines)
        assert len(findings) == 0

    def test_disabled_rule_returns_empty(self):
        lines = ['    let val = result.unwrap();']
        findings = check_unwrap_in_production("lib.rs", lines, enabled=False)
        assert findings == []


class TestRustTransmute:
    def test_mem_transmute_flagged(self):
        lines = ['    let x: u32 = mem::transmute(y);']
        findings = check_transmute("lib.rs", lines)
        assert len(findings) == 1
        assert findings[0].rule_id == "rust.transmute"
        assert findings[0].severity == RustSeverity.ERROR

    def test_std_mem_transmute_flagged(self):
        lines = ['    let x = std::mem::transmute::<f32, u32>(val);']
        findings = check_transmute("lib.rs", lines)
        assert len(findings) == 1

    def test_safe_cast_not_flagged(self):
        lines = ['    let x = val as u32;']
        findings = check_transmute("lib.rs", lines)
        assert len(findings) == 0


class TestRustCommandInjection:
    def test_command_new_variable_flagged(self):
        lines = ['    Command::new(userInput)']
        findings = check_command_injection("main.rs", lines)
        assert len(findings) == 1
        assert findings[0].rule_id == "rust.command-injection"
        assert findings[0].category == RustRuleCategory.SECURITY

    def test_command_new_literal_not_flagged(self):
        lines = ['    Command::new("ls")']
        findings = check_command_injection("main.rs", lines)
        assert len(findings) == 0

    def test_disabled_rule_returns_empty(self):
        lines = ['    Command::new(userInput)']
        findings = check_command_injection("main.rs", lines, enabled=False)
        assert findings == []


class TestRustHardcodedCredentials:
    def test_let_password_flagged(self):
        lines = ['    let password = "hunter2";']
        findings = check_hardcoded_credentials("main.rs", lines)
        assert len(findings) == 1
        assert findings[0].rule_id == "rust.hardcoded-credentials"
        assert findings[0].severity == RustSeverity.ERROR

    def test_let_secret_flagged(self):
        lines = ['    let secret = "topsecret";']
        findings = check_hardcoded_credentials("main.rs", lines)
        assert len(findings) == 1

    def test_let_username_not_flagged(self):
        lines = ['    let username = "admin";']
        findings = check_hardcoded_credentials("main.rs", lines)
        assert len(findings) == 0


class TestRustAnalyzerReport:
    def test_multiple_findings_counted(self):
        lines = [
            'unsafe {',
            '    let val = result.unwrap();',
            '    let password = "hunter2";',
        ]
        findings = []
        findings.extend(check_unsafe_block("f.rs", lines))
        findings.extend(check_unwrap_in_production("f.rs", lines))
        findings.extend(check_hardcoded_credentials("f.rs", lines))
        assert len(findings) == 3

    def test_disabled_rule_skipped(self):
        config = RustScanConfig(rules={"rust.unsafe-block": False})
        lines = ['unsafe {']
        rule_id = check_unsafe_block.__doc__.split(":")[0].strip()
        enabled = config.rules.get(rule_id, True)
        findings = check_unsafe_block("f.rs", lines, enabled=enabled)
        assert findings == []
