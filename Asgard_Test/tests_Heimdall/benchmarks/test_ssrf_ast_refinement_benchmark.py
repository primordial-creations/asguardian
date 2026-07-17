"""Benchmark corpus for the SSRF AST refinement pipeline (plan 07.1).

Vulnerable/safe pairs exercising each of the 5 pipeline steps: host-
control structural check, source verification, entry-point tiering,
allowlist dominator check, and redirect metadata. The regex-only scanner
over-flags several of the "safe" cases below (its documented 40%+ FP
profile); the AST refinement pass is what suppresses or downgrades them.
"""
from pathlib import Path

from Asgard.Heimdall.Security.SSRF.models.ssrf_models import SSRFScanConfig, SSRFVulnerabilityType
from Asgard.Heimdall.Security.SSRF.services.ssrf_scanner import SSRFXXEScanner


def _scan(tmp_path: Path, code: str):
    (tmp_path / "app.py").write_text(code)
    return SSRFXXEScanner().scan(SSRFScanConfig(scan_path=tmp_path))


def test_env_sourced_url_is_suppressed(tmp_path):
    report = _scan(tmp_path, """
import os
import requests

def fetch():
    url = os.environ.get("UPSTREAM_URL")
    return requests.get(url)
""")
    assert report.total_findings == 0


def test_constant_sourced_url_is_suppressed(tmp_path):
    report = _scan(tmp_path, """
import requests

UPSTREAM_URL = "https://internal.example.com/api"

def fetch():
    url = UPSTREAM_URL
    return requests.get(url)
""")
    assert report.total_findings == 0


# BLOCKER-1 regressions (adversarial review): `_source_chain_is_trusted`
# used to match any `.environ`/`.config`/`.settings`/`.getenv` ATTRIBUTE
# NAME anywhere in the sliced subtree, with no check that the base object
# was actually `os`. That laundered attacker-controlled sources through
# object attributes that merely share a name with the real trusted ones.
#
# NOTE: variable names below use `target_url` rather than a bare `url` --
# the regex dual-engine floor's Python SSRF pattern requires at least one
# character before the `url`/`host`/`target`/... keyword in the call
# argument text (`[^'"]+(?:url|URL|host|...)`), so an argument that is
# *exactly* the 3-character name `url` never reaches the regex layer at
# all (a pre-existing, out-of-scope regex-coverage gap, not part of the
# BLOCKER-1 AST-refinement bug). `target_url` reaches the regex floor so
# these tests actually exercise the AST refinement pass being fixed here.
def test_wsgi_environ_forwarded_host_is_not_suppressed(tmp_path):
    report = _scan(tmp_path, """
import requests

def fetch(request):
    target_url = request.environ['HTTP_X_FORWARDED_HOST']
    return requests.get(target_url)
""")
    findings = [f for f in report.findings if f.vulnerability_type == SSRFVulnerabilityType.SSRF]
    assert findings, "request.environ is attacker-controlled WSGI headers -- must not be suppressed as trusted"


def test_user_object_config_subscript_is_not_suppressed(tmp_path):
    report = _scan(tmp_path, """
import requests

def fetch(user_obj, request):
    target_url = user_obj.config[request.args['key']]
    return requests.get(target_url)
""")
    findings = [f for f in report.findings if f.vulnerability_type == SSRFVulnerabilityType.SSRF]
    assert findings, "user_obj.config[...] with a tainted subscript key must not be suppressed as trusted"


def test_os_environ_subscript_with_tainted_key_is_not_suppressed(tmp_path):
    report = _scan(tmp_path, """
import os
import requests

def fetch(request):
    target_url = os.environ[request.args['key']]
    return requests.get(target_url)
""")
    findings = [f for f in report.findings if f.vulnerability_type == SSRFVulnerabilityType.SSRF]
    assert findings, "a non-literal (tainted) subscript key on os.environ must not be treated as trusted"


def test_os_environ_literal_subscript_is_still_suppressed(tmp_path):
    # Sanity check the fix didn't over-correct: a genuine os.environ read
    # with a literal key must still suppress, same as os.environ.get(...).
    report = _scan(tmp_path, """
import os
import requests

def fetch():
    target_url = os.environ["UPSTREAM_URL"]
    return requests.get(target_url)
""")
    assert report.total_findings == 0


def test_literal_host_with_path_suffix_becomes_api_path_injection(tmp_path):
    report = _scan(tmp_path, """
import requests

def fetch(path_suffix):
    return requests.get(f"https://api.internal.example.com/{path_suffix}")
""")
    findings = [f for f in report.findings if f.vulnerability_type == SSRFVulnerabilityType.SSRF]
    assert findings, "expected the reclassified finding to still be reported"
    assert findings[0].severity == "LOW"
    assert findings[0].pattern_type == "api_path_injection"


def test_route_handler_param_is_high_confidence(tmp_path):
    report = _scan(tmp_path, """
import requests
from flask import Flask, request

app = Flask(__name__)

@app.route("/proxy")
def proxy():
    target_url = request.args.get("url")
    return requests.get(target_url)
""")
    findings = [f for f in report.findings if f.vulnerability_type == SSRFVulnerabilityType.SSRF]
    assert findings
    assert findings[0].confidence >= 0.8
    assert findings[0].confidence_bucket in ("certain", "probable")


def test_generic_helper_param_is_low_confidence(tmp_path):
    report = _scan(tmp_path, """
import requests

def fetch_helper(target_url):
    return requests.get(target_url)
""")
    findings = [f for f in report.findings if f.vulnerability_type == SSRFVulnerabilityType.SSRF]
    assert findings
    assert findings[0].confidence < 0.5


def test_strict_equality_allowlist_suppresses(tmp_path):
    report = _scan(tmp_path, """
import requests

def fetch(target_url):
    if target_url == "https://trusted.example.com/data":
        return requests.get(target_url)
""")
    assert report.total_findings == 0


def test_startswith_guard_downgrades_to_validation_bypass(tmp_path):
    report = _scan(tmp_path, """
import requests

def fetch(target_url):
    if target_url.startswith("https://trusted.example.com"):
        return requests.get(target_url)
""")
    findings = [f for f in report.findings if f.vulnerability_type == SSRFVulnerabilityType.SSRF]
    assert findings
    assert findings[0].severity == "MEDIUM"
    assert "Validation Bypass" in findings[0].description
