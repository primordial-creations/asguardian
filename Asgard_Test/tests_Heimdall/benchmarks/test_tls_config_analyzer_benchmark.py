"""Benchmark for the TLS/mTLS config-file analyzer (plan 07.9, RESEARCH_17).

Vulnerable/safe pairs across nginx, HAProxy, and Terraform ALB configs.
Config-file evidence is max-precision (source="config", never a hotspot).
"""
import tempfile
from pathlib import Path

from Asgard.Heimdall.Security.TLS.services.tls_config_analyzer import analyze_config_file


def _analyze(filename: str, content: str):
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / filename
        file_path.write_text(content)
        return analyze_config_file(file_path)


def test_nginx_weak_ssl_protocols_flagged():
    findings = _analyze(
        "nginx.conf",
        "server {\n  ssl_protocols TLSv1 TLSv1.1;\n}\n",
    )
    assert findings, "weak ssl_protocols should be flagged"
    assert findings[0].source == "config"
    assert findings[0].is_hotspot is False
    assert findings[0].mechanism_id


def test_nginx_modern_ssl_protocols_not_flagged():
    findings = _analyze(
        "nginx.conf",
        "server {\n  ssl_protocols TLSv1.2 TLSv1.3;\n}\n",
    )
    assert not any(f.finding_type == "deprecated_tls_version" for f in findings)


def test_nginx_ssl_verify_client_off_flagged():
    findings = _analyze(
        "nginx.conf",
        "server {\n  ssl_verify_client off;\n}\n",
    )
    assert any(f.finding_type == "disabled_verification" for f in findings)


def test_haproxy_verify_none_flagged():
    findings = _analyze(
        "haproxy.cfg",
        "backend b\n  server s1 10.0.0.1:443 ssl verify none\n",
    )
    assert any(f.finding_type == "disabled_verification" for f in findings)


def test_haproxy_verify_required_not_flagged():
    findings = _analyze(
        "haproxy.cfg",
        "backend b\n  server s1 10.0.0.1:443 ssl verify required ca-file /etc/ca.pem\n",
    )
    assert not any(f.finding_type == "disabled_verification" for f in findings)


def test_terraform_mutual_auth_off_flagged():
    findings = _analyze(
        "alb.tf",
        'resource "aws_lb_listener" "x" {\n'
        "  mutual_authentication {\n"
        '    mode = "off"\n'
        "  }\n"
        "}\n",
    )
    assert any(f.finding_type == "disabled_verification" for f in findings)


def test_terraform_mutual_auth_verify_not_flagged():
    findings = _analyze(
        "alb.tf",
        'resource "aws_lb_listener" "x" {\n'
        "  mutual_authentication {\n"
        '    mode = "verify"\n'
        "  }\n"
        "}\n",
    )
    assert not any(f.finding_type == "disabled_verification" for f in findings)


def test_terraform_deprecated_ssl_policy_flagged():
    findings = _analyze(
        "alb.tf",
        'resource "aws_lb_listener" "x" {\n'
        '  ssl_policy = "ELBSecurityPolicy-TLS-1-0-2015-04"\n'
        "}\n",
    )
    assert any(f.finding_type == "deprecated_tls_version" for f in findings)
