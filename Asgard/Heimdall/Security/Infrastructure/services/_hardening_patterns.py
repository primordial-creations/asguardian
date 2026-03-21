"""
Heimdall Hardening Pattern Definitions

Pattern definitions for detecting infrastructure hardening issues.
"""

import re
from typing import List

from Asgard.Heimdall.Security.Infrastructure.models.infra_models import InfraFindingType
from Asgard.Heimdall.Security.models.security_models import SecuritySeverity


class HardeningPattern:
    """Defines a pattern for detecting hardening issues."""

    def __init__(
        self,
        name: str,
        pattern: str,
        finding_type: InfraFindingType,
        severity: SecuritySeverity,
        title: str,
        description: str,
        cwe_id: str,
        remediation: str,
        confidence: float = 0.7,
    ):
        self.name = name
        self.pattern = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
        self.finding_type = finding_type
        self.severity = severity
        self.title = title
        self.description = description
        self.cwe_id = cwe_id
        self.remediation = remediation
        self.confidence = confidence


HARDENING_PATTERNS: List[HardeningPattern] = [
    HardeningPattern(
        name="exposed_debug_endpoint",
        pattern=r"""(?:@app\.route|@router\.\w+|path)\s*\(\s*['"](?:/debug|/_debug|/__debug__|/_internal|/profiler|/_profiler)['"]""",
        finding_type=InfraFindingType.EXPOSED_DEBUG_ENDPOINT,
        severity=SecuritySeverity.HIGH,
        title="Exposed Debug Endpoint",
        description="A debug endpoint is exposed. Debug endpoints can leak sensitive information.",
        cwe_id="CWE-489",
        remediation="Remove or restrict access to debug endpoints in production.",
        confidence=0.9,
    ),
    HardeningPattern(
        name="exposed_admin_route",
        pattern=r"""(?:@app\.route|@router\.\w+|path)\s*\(\s*['"]/admin(?:/|\?|['"])""",
        finding_type=InfraFindingType.EXPOSED_ADMIN_INTERFACE,
        severity=SecuritySeverity.MEDIUM,
        title="Admin Interface Detected",
        description="An admin interface route is detected. Ensure it is properly protected.",
        cwe_id="CWE-749",
        remediation="Ensure admin routes require strong authentication and are rate-limited.",
        confidence=0.6,
    ),
    HardeningPattern(
        name="world_writable_chmod",
        pattern=r"""chmod\s+(?:777|666|a\+w|\+w)""",
        finding_type=InfraFindingType.WORLD_WRITABLE,
        severity=SecuritySeverity.CRITICAL,
        title="World-Writable File Permissions",
        description="File permissions allow anyone to write. This can lead to unauthorized modifications.",
        cwe_id="CWE-732",
        remediation="Use restrictive file permissions (e.g., 644 for files, 755 for directories).",
        confidence=0.95,
    ),
    HardeningPattern(
        name="world_writable_mode",
        pattern=r"""os\.chmod\s*\([^,]+,\s*0o?777\)""",
        finding_type=InfraFindingType.WORLD_WRITABLE,
        severity=SecuritySeverity.CRITICAL,
        title="World-Writable File Permissions (Python)",
        description="Python code sets world-writable permissions. This allows anyone to modify the file.",
        cwe_id="CWE-732",
        remediation="Use restrictive permissions: os.chmod(path, 0o644)",
        confidence=0.95,
    ),
    HardeningPattern(
        name="insecure_temp_file",
        pattern=r"""(?:tempfile\.mktemp|os\.tmpnam|tmpnam\()""",
        finding_type=InfraFindingType.INSECURE_DEFAULT,
        severity=SecuritySeverity.HIGH,
        title="Insecure Temporary File Creation",
        description="Insecure temporary file function used. This can lead to race condition attacks.",
        cwe_id="CWE-377",
        remediation="Use tempfile.mkstemp() or tempfile.TemporaryFile() for secure temporary files.",
        confidence=0.9,
    ),
    HardeningPattern(
        name="http_not_https",
        pattern=r"""['"]http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)[\w.-]+""",
        finding_type=InfraFindingType.INSECURE_TRANSPORT,
        severity=SecuritySeverity.MEDIUM,
        title="Unencrypted HTTP URL",
        description="HTTP URL detected (not HTTPS). Data transmitted over HTTP is unencrypted.",
        cwe_id="CWE-319",
        remediation="Use HTTPS for all external connections to protect data in transit.",
        confidence=0.7,
    ),
    HardeningPattern(
        name="ssl_verify_disabled",
        pattern=r"""(?:verify\s*=\s*False|CERT_NONE|verify_ssl\s*=\s*False|ssl_verify\s*=\s*False)""",
        finding_type=InfraFindingType.INSECURE_TRANSPORT,
        severity=SecuritySeverity.HIGH,
        title="SSL/TLS Verification Disabled",
        description="SSL certificate verification is disabled. This allows man-in-the-middle attacks.",
        cwe_id="CWE-295",
        remediation="Enable SSL verification. Never disable certificate verification in production.",
        confidence=0.95,
    ),
    HardeningPattern(
        name="bind_all_interfaces",
        pattern=r"""(?:\.run\(|bind\s*=|host\s*=)\s*['"](0\.0\.0\.0)['"]""",
        finding_type=InfraFindingType.INSECURE_DEFAULT,
        severity=SecuritySeverity.MEDIUM,
        title="Service Bound to All Interfaces",
        description="Service is bound to 0.0.0.0, listening on all network interfaces.",
        cwe_id="CWE-1188",
        remediation="Bind to specific interfaces (e.g., 127.0.0.1) or use firewall rules.",
        confidence=0.7,
    ),
    HardeningPattern(
        name="exposed_metrics_endpoint",
        # Note: /health and /status are excluded - they are standard Kubernetes/load balancer endpoints
        # that return minimal information and are required for production deployments
        pattern=r"""(?:@app\.route|@router\.\w+|path)\s*\(\s*['"](?:/metrics|/actuator|/info)['"]""",
        finding_type=InfraFindingType.EXPOSED_DEBUG_ENDPOINT,
        severity=SecuritySeverity.MEDIUM,
        title="Exposed Metrics Endpoint",
        description="Metrics endpoint detected. /metrics (Prometheus) and /actuator (Spring Boot) can leak sensitive operational data if not secured.",
        cwe_id="CWE-200",
        remediation="Restrict access to metrics endpoints to internal networks or authorized users. Consider using authentication.",
        confidence=0.7,
    ),
    HardeningPattern(
        name="environment_dump",
        pattern=r"""(?:os\.environ|process\.env|ENV\[)[\s\S]{0,30}(?:print|log|dump|json\.dumps)""",
        finding_type=InfraFindingType.VERBOSE_ERROR_MESSAGES,
        severity=SecuritySeverity.HIGH,
        title="Environment Variables Logged",
        description="Environment variables may be logged or printed. This can expose secrets.",
        cwe_id="CWE-532",
        remediation="Never log environment variables. They often contain secrets.",
        confidence=0.75,
    ),
    HardeningPattern(
        name="docker_privileged",
        pattern=r"""privileged\s*:\s*true""",
        finding_type=InfraFindingType.INSECURE_DEFAULT,
        severity=SecuritySeverity.CRITICAL,
        title="Docker Privileged Mode",
        description="Docker container running in privileged mode. This gives root access to the host.",
        cwe_id="CWE-250",
        remediation="Remove privileged mode. Use specific capabilities if needed.",
        confidence=0.95,
    ),
    HardeningPattern(
        name="docker_root_user",
        pattern=r"""USER\s+root\s*$""",
        finding_type=InfraFindingType.INSECURE_DEFAULT,
        severity=SecuritySeverity.HIGH,
        title="Docker Running as Root",
        description="Docker container runs as root user. This increases the attack surface.",
        cwe_id="CWE-250",
        remediation="Add a non-root USER instruction in your Dockerfile.",
        confidence=0.85,
    ),
    HardeningPattern(
        name="docker_expose_all",
        pattern=r"""ports\s*:\s*\n\s*-\s*['"]?\d+:\d+['"]?""",
        finding_type=InfraFindingType.INSECURE_DEFAULT,
        severity=SecuritySeverity.LOW,
        title="Docker Port Exposure",
        description="Docker ports are exposed. Ensure only necessary ports are exposed.",
        cwe_id="CWE-1188",
        remediation="Only expose ports that are absolutely necessary. Use internal networks where possible.",
        confidence=0.5,
    ),
    HardeningPattern(
        name="nginx_server_tokens",
        pattern=r"""server_tokens\s+on""",
        finding_type=InfraFindingType.VERBOSE_ERROR_MESSAGES,
        severity=SecuritySeverity.LOW,
        title="Nginx Server Tokens Enabled",
        description="Nginx server version is exposed in headers. This aids attackers in targeting vulnerabilities.",
        cwe_id="CWE-200",
        remediation="Set server_tokens off; in nginx configuration.",
        confidence=0.9,
    ),
    HardeningPattern(
        name="expose_php",
        pattern=r"""expose_php\s*=\s*(?:On|1|true)""",
        finding_type=InfraFindingType.VERBOSE_ERROR_MESSAGES,
        severity=SecuritySeverity.LOW,
        title="PHP Version Exposed",
        description="PHP version is exposed in headers. This aids attackers in targeting vulnerabilities.",
        cwe_id="CWE-200",
        remediation="Set expose_php = Off in php.ini.",
        confidence=0.9,
    ),
    HardeningPattern(
        name="directory_listing",
        pattern=r"""(?:autoindex\s+on|Options\s+\+?Indexes|DirectoryIndex\s+disabled)""",
        finding_type=InfraFindingType.INSECURE_DEFAULT,
        severity=SecuritySeverity.MEDIUM,
        title="Directory Listing Enabled",
        description="Directory listing is enabled. This exposes file structure to attackers.",
        cwe_id="CWE-548",
        remediation="Disable directory listing. Set autoindex off; in nginx or Options -Indexes in Apache.",
        confidence=0.9,
    ),
    HardeningPattern(
        name="no_limit_request",
        pattern=r"""(?:LimitRequestBody|client_max_body_size)\s+0""",
        finding_type=InfraFindingType.INSECURE_DEFAULT,
        severity=SecuritySeverity.MEDIUM,
        title="No Request Body Limit",
        description="No limit on request body size. This allows denial of service via large uploads.",
        cwe_id="CWE-770",
        remediation="Set appropriate limits: LimitRequestBody or client_max_body_size.",
        confidence=0.85,
    ),
]
