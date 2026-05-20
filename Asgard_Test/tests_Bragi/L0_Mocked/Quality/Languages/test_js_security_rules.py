"""
Tests for JavaScript security rules (_js_security_rules.py)

Tests write JavaScript code to temporary files and run the JSAnalyzer against them.
"""

import tempfile
from pathlib import Path

import pytest

from Asgard.Bragi.Quality.languages.javascript.models.js_models import JSSeverity, JSRuleCategory
from Asgard.Bragi.Quality.languages.javascript.services.js_analyzer import JSAnalyzer


class TestJsSqlInjection:
    def test_template_literal_in_db_query_flagged(self):
        code = 'db.query(`SELECT * FROM users WHERE id=${userId}`);\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "repo.js").write_text(code)
            report = JSAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "js.sql-injection" for f in report.findings)

    def test_string_concat_in_db_query_flagged(self):
        code = 'db.query("SELECT * FROM users WHERE id=" + userId);\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "repo.js").write_text(code)
            report = JSAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "js.sql-injection" for f in report.findings)

    def test_parameterised_query_not_flagged(self):
        code = 'db.query("SELECT * FROM users WHERE id=?", [userId]);\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "safe.js").write_text(code)
            report = JSAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "js.sql-injection" for f in report.findings)

    def test_severity_is_error(self):
        code = 'db.query(`DELETE FROM t WHERE x=${x}`);\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "bad.js").write_text(code)
            report = JSAnalyzer().analyze(scan_path=d)
        findings = [f for f in report.findings if f.rule_id == "js.sql-injection"]
        assert findings[0].severity == JSSeverity.ERROR


class TestJsHardcodedCredentials:
    def test_const_password_flagged(self):
        code = 'const password = "mysupersecret";\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "config.js").write_text(code)
            report = JSAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "js.hardcoded-credentials" for f in report.findings)

    def test_const_api_key_flagged(self):
        code = 'const apiKey = "abcd1234efgh";\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "config.js").write_text(code)
            report = JSAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "js.hardcoded-credentials" for f in report.findings)

    def test_env_var_not_flagged(self):
        code = 'const password = process.env.DB_PASS;\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "safe.js").write_text(code)
            report = JSAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "js.hardcoded-credentials" for f in report.findings)


class TestJsCommandInjection:
    def test_exec_with_template_literal_flagged(self):
        code = 'exec(`ls ${userInput}`);\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "cmd.js").write_text(code)
            report = JSAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "js.command-injection" for f in report.findings)

    def test_exec_sync_with_template_literal_flagged(self):
        code = 'execSync(`rm -rf ${path}`);\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "cmd.js").write_text(code)
            report = JSAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "js.command-injection" for f in report.findings)

    def test_exec_with_literal_string_not_flagged(self):
        code = 'exec("ls -la");\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "safe.js").write_text(code)
            report = JSAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "js.command-injection" for f in report.findings)

    def test_severity_is_error(self):
        code = 'exec(`cat ${filename}`);\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "bad.js").write_text(code)
            report = JSAnalyzer().analyze(scan_path=d)
        findings = [f for f in report.findings if f.rule_id == "js.command-injection"]
        assert findings[0].severity == JSSeverity.ERROR


class TestJsXss:
    def test_inner_html_with_variable_flagged(self):
        code = 'element.innerHTML = userInput;\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "ui.js").write_text(code)
            report = JSAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "js.xss" for f in report.findings)

    def test_document_write_with_variable_flagged(self):
        code = 'document.write(userData);\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "ui.js").write_text(code)
            report = JSAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "js.xss" for f in report.findings)

    def test_category_is_security(self):
        code = 'div.innerHTML = content;\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "ui.js").write_text(code)
            report = JSAnalyzer().analyze(scan_path=d)
        findings = [f for f in report.findings if f.rule_id == "js.xss"]
        assert findings[0].category == JSRuleCategory.SECURITY


class TestJsPathTraversal:
    def test_fs_read_file_with_req_param_flagged(self):
        code = 'fs.readFile(req.params.filename, callback);\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "server.js").write_text(code)
            report = JSAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "js.path-traversal" for f in report.findings)

    def test_fs_read_file_sync_with_req_flagged(self):
        code = 'const data = fs.readFileSync(req.query.path);\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "server.js").write_text(code)
            report = JSAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "js.path-traversal" for f in report.findings)

    def test_static_path_not_flagged(self):
        code = 'fs.readFile("./static/index.html", callback);\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "safe.js").write_text(code)
            report = JSAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "js.path-traversal" for f in report.findings)


class TestJsWeakCrypto:
    def test_md5_hash_flagged(self):
        code = "const hash = crypto.createHash('md5').update(data).digest('hex');\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "crypto.js").write_text(code)
            report = JSAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "js.weak-crypto" for f in report.findings)

    def test_sha1_hash_flagged(self):
        code = 'const hash = crypto.createHash("sha1").update(data).digest("hex");\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "crypto.js").write_text(code)
            report = JSAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "js.weak-crypto" for f in report.findings)

    def test_sha256_not_flagged(self):
        code = "const hash = crypto.createHash('sha256').update(data).digest('hex');\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "safe.js").write_text(code)
            report = JSAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "js.weak-crypto" for f in report.findings)

    def test_severity_is_error(self):
        code = "crypto.createHash('md5');\n"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "bad.js").write_text(code)
            report = JSAnalyzer().analyze(scan_path=d)
        findings = [f for f in report.findings if f.rule_id == "js.weak-crypto"]
        assert findings[0].severity == JSSeverity.ERROR


class TestJsNoPrototypePollution:
    def test_proto_assignment_flagged(self):
        code = 'obj.__proto__ = payload;\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "bad.js").write_text(code)
            report = JSAnalyzer().analyze(scan_path=d)
        assert any(f.rule_id == "js.no-prototype-pollution" for f in report.findings)

    def test_regular_assignment_not_flagged(self):
        code = 'obj.prototype = MyClass.prototype;\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "ok.js").write_text(code)
            report = JSAnalyzer().analyze(scan_path=d)
        assert not any(f.rule_id == "js.no-prototype-pollution" for f in report.findings)

    def test_category_is_security(self):
        code = 'target.__proto__ = src;\n'
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "bad.js").write_text(code)
            report = JSAnalyzer().analyze(scan_path=d)
        findings = [f for f in report.findings if f.rule_id == "js.no-prototype-pollution"]
        assert findings[0].category == JSRuleCategory.SECURITY
