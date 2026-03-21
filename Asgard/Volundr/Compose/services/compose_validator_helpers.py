from typing import Any, Dict, List, Optional

from Asgard.common.output_formatter import (
    FormattedIssue,
    FormattedReport,
    Severity,
)


def validate_service(
    name: str, config: Dict[str, Any], file_path: str
) -> List[FormattedIssue]:
    issues: List[FormattedIssue] = []

    if config is None:
        config = {}

    if not config.get("image") and not config.get("build"):
        issues.append(FormattedIssue(
            message=f"Service '{name}' has no image or build configuration",
            severity=Severity.ERROR,
            file_path=file_path,
            rule_id="no-image-or-build",
        ))

    image = config.get("image", "")
    if image.endswith(":latest") or (image and ":" not in image):
        issues.append(FormattedIssue(
            message=f"Service '{name}' uses :latest or untagged image - pin to specific version",
            severity=Severity.WARNING,
            file_path=file_path,
            rule_id="unpinned-image",
            suggestion="Use a specific version tag instead of :latest",
        ))

    if not config.get("healthcheck"):
        issues.append(FormattedIssue(
            message=f"Service '{name}' has no health check defined",
            severity=Severity.WARNING,
            file_path=file_path,
            rule_id="no-healthcheck",
            suggestion="Add a healthcheck to detect container failures",
        ))

    restart = config.get("restart")
    if not restart or restart == "no":
        issues.append(FormattedIssue(
            message=f"Service '{name}' has no restart policy",
            severity=Severity.WARNING,
            file_path=file_path,
            rule_id="no-restart-policy",
            suggestion="Add 'restart: unless-stopped' or 'restart: always'",
        ))

    if config.get("privileged"):
        issues.append(FormattedIssue(
            message=f"Service '{name}' uses privileged mode - security concern",
            severity=Severity.ERROR,
            file_path=file_path,
            rule_id="privileged-container",
            suggestion="Avoid privileged mode; use specific capabilities if needed",
        ))

    deploy = config.get("deploy", {})
    resources = deploy.get("resources", {})
    if not resources.get("limits"):
        issues.append(FormattedIssue(
            message=f"Service '{name}' has no resource limits defined",
            severity=Severity.WARNING,
            file_path=file_path,
            rule_id="no-resource-limits",
            suggestion="Add deploy.resources.limits for cpu and memory",
        ))

    environment = config.get("environment", {})
    if isinstance(environment, dict):
        for key, value in environment.items():
            if looks_like_secret(key, value):
                issues.append(FormattedIssue(
                    message=f"Service '{name}' has potential secret in environment: {key}",
                    severity=Severity.WARNING,
                    file_path=file_path,
                    rule_id="secret-in-env",
                    suggestion="Use Docker secrets or external secret management",
                ))

    if not config.get("logging"):
        issues.append(FormattedIssue(
            message=f"Service '{name}' has no logging configuration",
            severity=Severity.INFO,
            file_path=file_path,
            rule_id="no-logging-config",
            suggestion="Add logging configuration with max-size and max-file",
        ))

    if not config.get("security_opt") and not config.get("cap_drop"):
        issues.append(FormattedIssue(
            message=f"Service '{name}' has no security hardening (no cap_drop or security_opt)",
            severity=Severity.INFO,
            file_path=file_path,
            rule_id="no-security-hardening",
            suggestion="Add 'cap_drop: [ALL]' and only add required capabilities",
        ))

    if not config.get("user"):
        issues.append(FormattedIssue(
            message=f"Service '{name}' runs as root (no user specified)",
            severity=Severity.WARNING,
            file_path=file_path,
            rule_id="running-as-root",
            suggestion="Add 'user: 1000:1000' or similar non-root user",
        ))

    network_mode = config.get("network_mode")
    if network_mode == "host":
        issues.append(FormattedIssue(
            message=f"Service '{name}' uses host network mode",
            severity=Severity.WARNING,
            file_path=file_path,
            rule_id="host-network-mode",
            suggestion="Avoid host network mode unless absolutely necessary",
        ))

    return issues


def validate_network(
    name: str, config: Optional[Dict[str, Any]], file_path: str
) -> List[FormattedIssue]:
    issues: List[FormattedIssue] = []

    if config is None:
        return issues

    if config.get("external") and not config.get("name"):
        issues.append(FormattedIssue(
            message=f"External network '{name}' should specify explicit name",
            severity=Severity.INFO,
            file_path=file_path,
            rule_id="external-network-no-name",
        ))

    return issues


def validate_volume(
    name: str, config: Optional[Dict[str, Any]], file_path: str
) -> List[FormattedIssue]:
    issues: List[FormattedIssue] = []

    if config is None:
        return issues

    driver = config.get("driver", "local")
    if driver == "local" and config.get("driver_opts"):
        opts = config.get("driver_opts", {})
        if opts.get("type") == "nfs" or opts.get("type") == "cifs":
            if "o" not in opts:
                issues.append(FormattedIssue(
                    message=f"Volume '{name}' uses NFS/CIFS but missing mount options",
                    severity=Severity.WARNING,
                    file_path=file_path,
                    rule_id="volume-missing-options",
                ))

    return issues


def looks_like_secret(key: str, value: Any) -> bool:
    secret_patterns = [
        "password", "secret", "key", "token", "api_key",
        "apikey", "auth", "credential", "private",
    ]

    key_lower = key.lower()
    for pattern in secret_patterns:
        if pattern in key_lower:
            if value and isinstance(value, str):
                if not value.startswith("${") and not value.startswith("$"):
                    return True

    return False


def initialize_rules() -> Dict[str, Dict[str, Any]]:
    return {
        "compose-version": {
            "description": "Compose file version check",
            "severity": Severity.WARNING,
        },
        "no-services": {
            "description": "No services defined",
            "severity": Severity.WARNING,
        },
        "no-image-or-build": {
            "description": "Service missing image or build",
            "severity": Severity.ERROR,
        },
        "unpinned-image": {
            "description": "Image uses :latest or no tag",
            "severity": Severity.WARNING,
        },
        "no-healthcheck": {
            "description": "Service missing health check",
            "severity": Severity.WARNING,
        },
        "no-restart-policy": {
            "description": "Service missing restart policy",
            "severity": Severity.WARNING,
        },
        "privileged-container": {
            "description": "Container runs in privileged mode",
            "severity": Severity.ERROR,
        },
        "no-resource-limits": {
            "description": "Service missing resource limits",
            "severity": Severity.WARNING,
        },
        "secret-in-env": {
            "description": "Potential secret in environment variable",
            "severity": Severity.WARNING,
        },
        "no-logging-config": {
            "description": "Service missing logging configuration",
            "severity": Severity.INFO,
        },
        "no-security-hardening": {
            "description": "Service missing security hardening",
            "severity": Severity.INFO,
        },
        "running-as-root": {
            "description": "Container running as root",
            "severity": Severity.WARNING,
        },
        "host-network-mode": {
            "description": "Container uses host network mode",
            "severity": Severity.WARNING,
        },
    }


def build_report(
    source: str, issues: List[FormattedIssue]
) -> FormattedReport:
    error_count = sum(1 for i in issues if i.severity in (Severity.ERROR, Severity.CRITICAL))
    warning_count = sum(1 for i in issues if i.severity == Severity.WARNING)
    info_count = sum(1 for i in issues if i.severity == Severity.INFO)

    return FormattedReport(
        title=f"Docker Compose Validation: {source}",
        summary=f"Found {error_count} errors, {warning_count} warnings, {info_count} info",
        issues=issues,
        stats={
            "total_issues": len(issues),
            "errors": error_count,
            "warnings": warning_count,
            "info": info_count,
        },
        metadata={"source": source},
    )
