"""
TLS/mTLS config-file analyzer (plan 07.9, RESEARCH_17).

Max-precision posture: apps behind a reverse proxy legitimately use HTTP
internally, so config-file evidence -- nginx ``ssl_verify_client``,
HAProxy ``verify required``, Terraform ALB ``mutual_authentication`` --
outranks any code-level guess about TLS posture. This is a separate,
config-only source from the certificate_validator's code-pattern sweep
(``source="config"``, never a hotspot: explicit config directives are the
ground truth for the deployed edge, not a guess).

Deliberately narrow, line-oriented parsing (not a full nginx/HCL grammar)
-- these formats have no single canonical AST library available without
adding a heavy dependency, and the directives checked here are
single-line by convention in all three formats. Findings are always
HIGH confidence because config-file text is authoritative, not inferred.

Documented FN: dynamically-generated/templated config (Jinja2, Helm,
environment substitution) that only resolves at deploy time is invisible
to a static text scan.
"""

import re
from pathlib import Path
from typing import List

from Asgard.Heimdall.Security.TLS.models.tls_models import TLSFinding, TLSFindingType
from Asgard.Heimdall.Security.normalization.priority import confidence_bucket

# NIST SP 800-52r2 minimum: TLS 1.2, TLS 1.3 preferred. Anything below is
# a protocol-minimum violation.
_WEAK_TLS_TOKENS = {"SSLv2", "SSLv3", "TLSv1", "TLSv1.0", "TLSv1.1", "sslv3", "tlsv1", "tlsv1.1"}

_NGINX_SSL_PROTOCOLS = re.compile(r"ssl_protocols\s+([^;]+);")
_NGINX_VERIFY_CLIENT = re.compile(r"ssl_verify_client\s+(\S+);")
_HAPROXY_VERIFY = re.compile(r"\bverify\s+(none|optional|required)\b", re.IGNORECASE)
_HAPROXY_SSL_MINVER = re.compile(r"ssl-min-ver\s+(\S+)", re.IGNORECASE)
_TF_MUTUAL_AUTH_BLOCK = re.compile(r"mutual_authentication\s*\{([^}]*)\}", re.DOTALL)
_TF_MUTUAL_AUTH_MODE = re.compile(r'mode\s*=\s*"([^"]+)"')
_TF_SSL_POLICY = re.compile(r'ssl_policy\s*=\s*"([^"]+)"')


def _mk(file_path: str, line_number: int, finding_type: TLSFindingType, severity: str,
        title: str, description: str, remediation: str, snippet: str, confidence: float = 0.9) -> TLSFinding:
    return TLSFinding(
        file_path=file_path,
        line_number=line_number,
        finding_type=finding_type,
        severity=severity,
        title=title,
        description=description,
        code_snippet=snippet[:150],
        cwe_id="CWE-295",
        confidence=confidence,
        confidence_bucket=confidence_bucket(confidence),
        mechanism_id=f"tls.config.{finding_type.value}",
        is_hotspot=False,
        source="config",
        remediation=remediation,
    )


def analyze_nginx_config(file_path: Path, content: str) -> List[TLSFinding]:
    findings: List[TLSFinding] = []
    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        m = _NGINX_SSL_PROTOCOLS.search(line)
        if m:
            protocols = m.group(1).split()
            weak = [p for p in protocols if p in _WEAK_TLS_TOKENS]
            if weak:
                findings.append(_mk(
                    str(file_path), i, TLSFindingType.DEPRECATED_TLS_VERSION, "high",
                    "nginx ssl_protocols allows deprecated TLS/SSL versions",
                    f"ssl_protocols directive allows {', '.join(weak)} -- below the "
                    "NIST SP 800-52r2 TLS 1.2 minimum.",
                    "Set `ssl_protocols TLSv1.2 TLSv1.3;`",
                    line.strip(),
                ))
        m = _NGINX_VERIFY_CLIENT.search(line)
        if m and m.group(1).lower() in ("off", "optional_no_ca"):
            findings.append(_mk(
                str(file_path), i, TLSFindingType.DISABLED_VERIFICATION, "medium",
                f"nginx ssl_verify_client {m.group(1)}",
                f"ssl_verify_client is set to '{m.group(1)}' -- client certificate "
                "verification is disabled or does not enforce a CA chain, weakening "
                "mTLS on this server block.",
                "Set `ssl_verify_client on;` (or `optional` only if a downstream "
                "layer performs the real authorization check) with a trusted "
                "`ssl_client_certificate` CA bundle.",
                line.strip(),
            ))
    return findings


def analyze_haproxy_config(file_path: Path, content: str) -> List[TLSFinding]:
    findings: List[TLSFinding] = []
    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        if "ssl" not in line.lower():
            continue
        m = _HAPROXY_VERIFY.search(line)
        if m and m.group(1).lower() == "none":
            findings.append(_mk(
                str(file_path), i, TLSFindingType.DISABLED_VERIFICATION, "high",
                "HAProxy 'verify none' disables TLS peer verification",
                "'verify none' on a bind/server line disables certificate "
                "verification for that TLS connection entirely.",
                "Use `verify required` with a `ca-file` pointing at a trusted CA bundle.",
                line.strip(),
            ))
        m = _HAPROXY_SSL_MINVER.search(line)
        if m and m.group(1) in _WEAK_TLS_TOKENS:
            findings.append(_mk(
                str(file_path), i, TLSFindingType.DEPRECATED_TLS_VERSION, "high",
                "HAProxy ssl-min-ver below NIST SP 800-52r2 minimum",
                f"ssl-min-ver is set to {m.group(1)}, below the TLS 1.2 floor.",
                "Set `ssl-min-ver TLSv1.2` (prefer TLSv1.3).",
                line.strip(),
            ))
    return findings


def analyze_terraform_alb_config(file_path: Path, content: str) -> List[TLSFinding]:
    findings: List[TLSFinding] = []
    for m in _TF_MUTUAL_AUTH_BLOCK.finditer(content):
        block = m.group(1)
        mode_m = _TF_MUTUAL_AUTH_MODE.search(block)
        if mode_m and mode_m.group(1) in ("off", "passthrough"):
            line_number = content.count("\n", 0, m.start()) + 1
            findings.append(_mk(
                str(file_path), line_number, TLSFindingType.DISABLED_VERIFICATION, "medium",
                f"Terraform ALB mutual_authentication mode = \"{mode_m.group(1)}\"",
                (
                    "mode is 'off' (mTLS disabled) or 'passthrough' (client cert "
                    "presented but NOT verified by the ALB -- verification is "
                    "pushed to the application, which must not be assumed)."
                ),
                'Set mode = "verify" with a configured trust_store for real mTLS enforcement.',
                block.strip()[:150],
            ))
    for m in _TF_SSL_POLICY.finditer(content):
        policy = m.group(1)
        if "TLS-1-0" in policy or "TLS-1-1" in policy or policy.startswith("ELBSecurityPolicy-2015"):
            line_number = content.count("\n", 0, m.start()) + 1
            findings.append(_mk(
                str(file_path), line_number, TLSFindingType.DEPRECATED_TLS_VERSION, "high",
                f"Terraform ALB ssl_policy allows deprecated TLS: {policy}",
                f"ssl_policy '{policy}' permits TLS versions below the NIST "
                "SP 800-52r2 1.2 minimum.",
                'Use a modern policy, e.g. ssl_policy = "ELBSecurityPolicy-TLS13-1-2-2021-06".',
                m.group(0),
            ))
    return findings


_ANALYZERS_BY_SUFFIX = {
    ".conf": analyze_nginx_config,
    ".cfg": analyze_haproxy_config,
    ".tf": analyze_terraform_alb_config,
}


def analyze_config_file(file_path: Path) -> List[TLSFinding]:
    """Dispatch to the right config-format analyzer by filename/suffix heuristic."""
    name = file_path.name.lower()
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    if "nginx" in name or name == "nginx.conf" or file_path.suffix == ".conf":
        return analyze_nginx_config(file_path, content)
    if "haproxy" in name or file_path.suffix == ".cfg":
        return analyze_haproxy_config(file_path, content)
    if file_path.suffix == ".tf":
        return analyze_terraform_alb_config(file_path, content)
    return []
