"""
Heimdall Security Analysis Base Models

Base enums, finding models, and config for security analysis.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SecuritySeverity(str, Enum):
    """Severity level for security findings."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecretType(str, Enum):
    """Types of secrets that can be detected."""
    API_KEY = "api_key"
    PASSWORD = "password"
    PRIVATE_KEY = "private_key"
    ACCESS_TOKEN = "access_token"
    SECRET_KEY = "secret_key"
    DATABASE_URL = "database_url"
    AWS_CREDENTIALS = "aws_credentials"
    AZURE_CREDENTIALS = "azure_credentials"
    GCP_CREDENTIALS = "gcp_credentials"
    JWT_TOKEN = "jwt_token"
    SSH_KEY = "ssh_key"
    CERTIFICATE = "certificate"
    OAUTH_TOKEN = "oauth_token"
    GENERIC_SECRET = "generic_secret"


class VulnerabilityType(str, Enum):
    """Types of vulnerabilities that can be detected."""
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    COMMAND_INJECTION = "command_injection"
    PATH_TRAVERSAL = "path_traversal"
    INSECURE_DESERIALIZATION = "insecure_deserialization"
    SSRF = "ssrf"
    OPEN_REDIRECT = "open_redirect"
    INSECURE_CRYPTO = "insecure_crypto"
    HARDCODED_SECRET = "hardcoded_secret"
    INSECURE_RANDOM = "insecure_random"
    WEAK_HASH = "weak_hash"
    MISSING_AUTH = "missing_auth"
    IMPROPER_INPUT_VALIDATION = "improper_input_validation"


class DependencyRiskLevel(str, Enum):
    """Risk level for dependency vulnerabilities."""
    SAFE = "safe"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class SecretFinding(BaseModel):
    """A detected secret in the codebase."""
    file_path: str = Field(..., description="Path to the file containing the secret")
    line_number: int = Field(..., description="Line number where the secret was found")
    column_start: int = Field(0, description="Column where the secret starts")
    column_end: int = Field(0, description="Column where the secret ends")
    secret_type: SecretType = Field(..., description="Type of secret detected")
    severity: SecuritySeverity = Field(..., description="Severity of the finding")
    pattern_name: str = Field(..., description="Name of the pattern that matched")
    masked_value: str = Field(..., description="Masked version of the secret")
    line_content: str = Field(..., description="Content of the line (sanitized)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score of the detection")
    remediation: str = Field("", description="Suggested remediation steps")
    context_tag: str = Field(
        "production",
        description="Test-context tag (plan 08). Secrets are NEVER suppressed by test context.",
    )
    suppressed_by_context: bool = Field(
        False,
        description="Always False for secrets by policy; present for schema uniformity.",
    )
    mechanism_id: str = Field(
        "secret.generic",
        description="Normalization-engine mechanism id (plan 06).",
    )
    confidence_bucket: str = Field(
        "probable",
        description="Qualitative confidence bucket (plan 06 priority.confidence_bucket).",
    )
    semantic_score: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description=(
            "Plan 07.3 semantic context score: identifier-name and "
            "behavioral-proof signal, independent of pattern-match "
            "confidence. Folded into `confidence` but reported separately "
            "for explainability."
        ),
    )

    class Config:
        use_enum_values = True


class VulnerabilityFinding(BaseModel):
    """A detected security vulnerability in the code."""
    file_path: str = Field(..., description="Path to the file containing the vulnerability")
    line_number: int = Field(..., description="Line number of the vulnerability")
    column_start: int = Field(0, description="Column where the issue starts")
    column_end: int = Field(0, description="Column where the issue ends")
    vulnerability_type: VulnerabilityType = Field(..., description="Type of vulnerability")
    severity: SecuritySeverity = Field(..., description="Severity of the finding")
    title: str = Field(..., description="Short title describing the issue")
    description: str = Field(..., description="Detailed description of the vulnerability")
    code_snippet: str = Field("", description="The vulnerable code snippet")
    cwe_id: Optional[str] = Field(None, description="CWE ID if applicable")
    owasp_category: Optional[str] = Field(None, description="OWASP category if applicable")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    remediation: str = Field("", description="Suggested remediation steps")
    references: List[str] = Field(default_factory=list, description="Reference URLs")
    context_tag: str = Field(
        "production",
        description="Test-context tag from the Security/context engine (plan 08).",
    )
    suppressed_by_context: bool = Field(
        False,
        description=(
            "True when the test-context severity matrix suppressed this "
            "finding; retained for --include-test-context, excluded from "
            "score and gate."
        ),
    )

    class Config:
        use_enum_values = True


class DependencyVulnerability(BaseModel):
    """A vulnerability found in a dependency."""
    package_name: str = Field(..., description="Name of the vulnerable package")
    installed_version: str = Field(..., description="Currently installed version")
    vulnerable_versions: str = Field(..., description="Version range affected")
    fixed_version: Optional[str] = Field(None, description="Version that fixes the issue")
    risk_level: DependencyRiskLevel = Field(..., description="Risk level of the vulnerability")
    cve_id: Optional[str] = Field(None, description="CVE ID if available")
    ghsa_id: Optional[str] = Field(None, description="GitHub Security Advisory ID")
    title: str = Field(..., description="Title of the vulnerability")
    description: str = Field(..., description="Detailed description")
    published_date: Optional[datetime] = Field(None, description="When the vulnerability was published")
    references: List[str] = Field(default_factory=list, description="Reference URLs")
    ecosystem: str = Field("pypi", description="Package ecosystem (pypi, npm, etc.)")
    mechanism_id: str = Field("", description="Normalization-engine mechanism id (plan 06).")
    confidence_bucket: str = Field("probable", description="Qualitative confidence bucket (plan 06).")
    confidence: float = Field(0.7, ge=0.0, le=1.0, description="Confidence score")
    is_dev_dependency: bool = Field(
        False,
        description=(
            "Plan 07.10 DEEPTHINK_11: dev/test-only dependencies (declared in "
            "a dev-extras group, requirements-dev.txt, etc.) get a severity "
            "discount rather than suppression -- a vulnerable dev tool is "
            "still a supply-chain risk (CI/CD compromise) but does not ship "
            "to production."
        ),
    )
    finding_kind: str = Field(
        "known_vulnerability",
        description=(
            "'known_vulnerability' (OSV/NVD/local DB match), 'typosquat' "
            "(manifest entry similar to a popular package name), or "
            "'dependency_confusion' (internal-looking name resolvable on a "
            "public index) -- plan 07.10."
        ),
    )
    source_db: str = Field(
        "local",
        description="Provenance of the vulnerability data: 'osv', 'nvd', or 'local' (bundled offline DB).",
    )

    class Config:
        use_enum_values = True


class CryptoFinding(BaseModel):
    """A cryptographic implementation issue."""
    file_path: str = Field(..., description="Path to the file")
    line_number: int = Field(..., description="Line number of the issue")
    issue_type: str = Field(..., description="Type of cryptographic issue")
    severity: SecuritySeverity = Field(..., description="Severity of the finding")
    algorithm: str = Field(..., description="Algorithm or function involved")
    description: str = Field(..., description="Description of the issue")
    recommendation: str = Field(..., description="Recommended secure alternative")
    code_snippet: str = Field("", description="The problematic code snippet")

    class Config:
        use_enum_values = True


class SecurityScanConfig(BaseModel):
    """Configuration for security scanning."""
    scan_path: Path = Field(default_factory=lambda: Path("."), description="Root path to scan")
    scan_secrets: bool = Field(True, description="Enable secrets detection")
    scan_vulnerabilities: bool = Field(True, description="Enable vulnerability scanning")
    scan_dependencies: bool = Field(True, description="Enable dependency scanning")
    scan_crypto: bool = Field(True, description="Enable cryptographic validation")
    scan_access: bool = Field(True, description="Enable access control scanning")
    scan_auth: bool = Field(True, description="Enable authentication scanning")
    scan_headers: bool = Field(True, description="Enable security headers scanning")
    scan_tls: bool = Field(True, description="Enable TLS/SSL scanning")
    scan_container: bool = Field(True, description="Enable container security scanning")
    scan_infrastructure: bool = Field(True, description="Enable infrastructure security scanning")
    min_severity: SecuritySeverity = Field(SecuritySeverity.LOW, description="Minimum severity to report")
    scoring_version: str = Field(
        "v1",
        description=(
            "Security score formula: 'v1' = legacy linear-subtractive (default "
            "for one deprecation cycle), 'v2' = multiplicative decay with size "
            "normalization and per-category soft caps. Both values are always "
            "computed and dual-reported (legacy_score / security_score_v2)."
        ),
    )
    exclude_patterns: List[str] = Field(
        default_factory=lambda: [
            "__pycache__",
            "node_modules",
            ".git",
            ".venv",
            "venv",
            "build",
            "dist",
            ".next",
            "coverage",
            "*.min.js",
            "*.min.css",
            # Exclude Heimdall's own security detection patterns (they define weak crypto to detect it)
            "Heimdall/Security",
            "Heimdall\\Security",
            "Asgard/Heimdall",
            "Asgard\\Heimdall",
            # Exclude test files (they intentionally contain vulnerable code for testing)
            "*_Test",
            "*Test",
            "tests",
            "test_*",
            "Ankh_Test",
            "Asgard_Test",
            "Hercules",
            # Exclude tool prototypes (experimental code)
            "_tool_prototypes",
            # Exclude package lock files (contain dependency hashes that look like secrets)
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
            # Exclude UI dump files
            "ui_dump.xml",
        ],
        description="Patterns to exclude from scanning"
    )
    include_extensions: Optional[List[str]] = Field(
        None,
        description="File extensions to include (None = all code files)"
    )
    custom_patterns: Dict[str, str] = Field(
        default_factory=dict,
        description="Custom regex patterns for secret detection"
    )
    ignore_paths: List[str] = Field(
        default_factory=list,
        description="Specific paths to ignore"
    )
    baseline_file: Optional[Path] = Field(
        None,
        description="Path to baseline file for ignoring known issues"
    )

    class Config:
        use_enum_values = True
