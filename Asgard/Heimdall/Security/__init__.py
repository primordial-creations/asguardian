"""
Heimdall Security - Security Analysis

This module provides security analysis tools including:
- Secrets detection (API keys, passwords, tokens)
- Dependency vulnerability scanning
- Injection pattern detection (SQL, XSS, command injection)
- Cryptographic implementation validation
- Access control analysis (RBAC, permissions)
- Authentication analysis (JWT, sessions, passwords)
- Security headers analysis (CSP, CORS, HSTS)
- TLS/SSL configuration analysis
- Container security analysis (Dockerfile, docker-compose)
- Infrastructure security analysis (credentials, config)
- Comprehensive static security analysis
- Security hotspot detection (code patterns requiring manual review)
- OWASP Top 10 and CWE Top 25 compliance reporting

Usage:
    python -m Heimdall security scan ./src
    python -m Heimdall security secrets ./src
    python -m Heimdall security dependencies ./src
    python -m Heimdall security vulnerabilities ./src
    python -m Heimdall security access ./src
    python -m Heimdall security auth ./src
    python -m Heimdall security headers ./src
    python -m Heimdall security tls ./src
    python -m Heimdall security container ./src
    python -m Heimdall security infra ./src

Example:
    from Heimdall.Security import StaticSecurityService

    service = StaticSecurityService()
    report = service.scan("./src")
    print(f"Security Score: {report.security_score}/100")
"""

__version__ = "1.1.0"
__author__ = "Asgard Contributors"

from Asgard.Heimdall.Security.models import (
    CryptoFinding,
    CryptoReport,
    DependencyReport,
    DependencyRiskLevel,
    DependencyVulnerability,
    SecretFinding,
    SecretType,
    SecretsReport,
    SecurityReport,
    SecurityScanConfig,
    SecuritySeverity,
    VulnerabilityFinding,
    VulnerabilityReport,
    VulnerabilityType,
)
from Asgard.Heimdall.Security.services import (
    CryptoPattern,
    CryptographicValidationService,
    DependencyVulnerabilityService,
    InjectionDetectionService,
    InjectionPattern,
    SecretPattern,
    SecretsDetectionService,
    StaticSecurityService,
)
from Asgard.Heimdall.Security.Access import (
    AccessAnalyzer,
    AccessConfig,
    AccessFinding,
    AccessFindingType,
    AccessReport,
    ControlAnalyzer,
    PermissionAnalyzer,
)
from Asgard.Heimdall.Security.Auth import (
    AuthAnalyzer,
    AuthConfig,
    AuthFinding,
    AuthFindingType,
    AuthReport,
    JWTValidator,
    PasswordAnalyzer,
    SessionAnalyzer,
)
from Asgard.Heimdall.Security.Headers import (
    CORSAnalyzer,
    CSPAnalyzer,
    HeaderConfig,
    HeaderFinding,
    HeaderFindingType,
    HeaderReport,
    HeadersAnalyzer,
    HeaderValidator,
)
from Asgard.Heimdall.Security.TLS import (
    CertificateValidator,
    CipherValidator,
    ProtocolAnalyzer,
    TLSAnalyzer,
    TLSConfig,
    TLSFinding,
    TLSFindingType,
    TLSReport,
)
from Asgard.Heimdall.Security.Container import (
    ComposeAnalyzer,
    ContainerAnalyzer,
    ContainerConfig,
    ContainerFinding,
    ContainerFindingType,
    ContainerReport,
    DockerfileAnalyzer,
)
from Asgard.Heimdall.Security.Infrastructure import (
    ConfigValidator,
    CredentialAnalyzer,
    HardeningChecker,
    InfraAnalyzer,
    InfraConfig,
    InfraFinding,
    InfraFindingType,
    InfraReport,
)
from Asgard.Heimdall.Security.Hotspots import (
    HotspotCategory,
    HotspotConfig,
    HotspotDetector,
    HotspotReport,
    ReviewPriority,
    ReviewStatus,
    SecurityHotspot,
)
from Asgard.Heimdall.Security.Compliance import (
    CategoryCompliance,
    ComplianceConfig,
    ComplianceGrade,
    ComplianceReporter,
    CWEComplianceReport,
    OWASPCategory,
    OWASPComplianceReport,
)

__all__ = [
    "CryptoFinding",
    "CryptoPattern",
    "CryptoReport",
    "CryptographicValidationService",
    "DependencyReport",
    "DependencyRiskLevel",
    "DependencyVulnerability",
    "DependencyVulnerabilityService",
    "InjectionDetectionService",
    "InjectionPattern",
    "SecretFinding",
    "SecretPattern",
    "SecretType",
    "SecretsDetectionService",
    "SecretsReport",
    "SecurityReport",
    "SecurityScanConfig",
    "SecuritySeverity",
    "StaticSecurityService",
    "VulnerabilityFinding",
    "VulnerabilityReport",
    "VulnerabilityType",
    "AccessAnalyzer",
    "AccessConfig",
    "AccessFinding",
    "AccessFindingType",
    "AccessReport",
    "ControlAnalyzer",
    "PermissionAnalyzer",
    "AuthAnalyzer",
    "AuthConfig",
    "AuthFinding",
    "AuthFindingType",
    "AuthReport",
    "JWTValidator",
    "PasswordAnalyzer",
    "SessionAnalyzer",
    "CORSAnalyzer",
    "CSPAnalyzer",
    "HeaderConfig",
    "HeaderFinding",
    "HeaderFindingType",
    "HeaderReport",
    "HeadersAnalyzer",
    "HeaderValidator",
    "CertificateValidator",
    "CipherValidator",
    "ProtocolAnalyzer",
    "TLSAnalyzer",
    "TLSConfig",
    "TLSFinding",
    "TLSFindingType",
    "TLSReport",
    "ComposeAnalyzer",
    "ContainerAnalyzer",
    "ContainerConfig",
    "ContainerFinding",
    "ContainerFindingType",
    "ContainerReport",
    "DockerfileAnalyzer",
    "ConfigValidator",
    "CredentialAnalyzer",
    "HardeningChecker",
    "InfraAnalyzer",
    "InfraConfig",
    "InfraFinding",
    "InfraFindingType",
    "InfraReport",
    # Hotspot detection
    "HotspotCategory",
    "HotspotConfig",
    "HotspotDetector",
    "HotspotReport",
    "ReviewPriority",
    "ReviewStatus",
    "SecurityHotspot",
    # Compliance reporting
    "CategoryCompliance",
    "ComplianceConfig",
    "ComplianceGrade",
    "ComplianceReporter",
    "CWEComplianceReport",
    "OWASPCategory",
    "OWASPComplianceReport",
]

# ── New submodule imports ──────────────────────────────────────────────────────
from Asgard.Heimdall.Security.API import APIFinding, APIScanConfig, APIScanReport, APISecurityCategory, APISecurityScanner, APISeverity  # noqa: E501
from Asgard.Heimdall.Security.Backdoor import BackdoorDetector, BackdoorFinding, BackdoorScanConfig, BackdoorScanReport, BackdoorSeverity, BackdoorType  # noqa: E501
from Asgard.Heimdall.Security.DataExfil import DataExfiltrationDetector, ExfilFinding, ExfilScanConfig, ExfilScanReport, ExfilSeverity, ExfilType  # noqa: E501
from Asgard.Heimdall.Security.Deserialization import DeserializationFinding, DeserializationScanConfig, DeserializationScanReport, DeserializationScanner, DeserializationSeverity  # noqa: E501
from Asgard.Heimdall.Security.DNS import DNSCheck, DNSIssue, DNSScanReport, DNSSecurityChecker
from Asgard.Heimdall.Security.FileIntegrity import FileIntegrityChecker, FileIntegrityReport, FileModification, FileRecord, PermissionChange  # noqa: E501
from Asgard.Heimdall.Security.Frontend import FrontendFinding, FrontendScanConfig, FrontendScanReport, FrontendSecurityScanner, FrontendSeverity  # noqa: E501
from Asgard.Heimdall.Security.Git import GitFinding, GitScanReport, GitSecurityScanner, GitSeverity
from Asgard.Heimdall.Security.InfoDisclosure import InfoDisclosureFinding, InfoDisclosureScanConfig, InfoDisclosureScanReport, InfoDisclosureScanner, InfoDisclosureSeverity  # noqa: E501
from Asgard.Heimdall.Security.InputValidation import InputValidationFinding, InputValidationScanConfig, InputValidationScanReport, InputValidationScanner, InputValidationSeverity  # noqa: E501
from Asgard.Heimdall.Security.LogAnalysis import LogAnalysisReport, LogAnalyzer, LogEvent
from Asgard.Heimdall.Security.Malware import MalwareFinding, MalwareScanConfig, MalwareScanReport, MalwareScanner, MalwareSeverity  # noqa: E501
from Asgard.Heimdall.Security.Misconfig import MisconfigFinding, MisconfigScanConfig, MisconfigScanReport, MisconfigSeverity, SecurityMisconfigScanner  # noqa: E501
from Asgard.Heimdall.Security.PathTraversal import PathTraversalFinding, PathTraversalScanConfig, PathTraversalScanReport, PathTraversalScanner, PathTraversalSeverity  # noqa: E501
from Asgard.Heimdall.Security.RaceCondition import RaceConditionDetector, RaceConditionFinding, RaceConditionScanConfig, RaceConditionScanReport, RaceConditionSeverity  # noqa: E501
from Asgard.Heimdall.Security.ReDoS import ReDoSFinding, ReDoSScanConfig, ReDoSScanReport, ReDoSScanner, ReDoSSeverity  # noqa: E501
from Asgard.Heimdall.Security.SensitiveData import SensitiveDataFinding, SensitiveDataScanConfig, SensitiveDataScanReport, SensitiveDataScanner, SensitiveDataSeverity  # noqa: E501
from Asgard.Heimdall.Security.SSRF import SSRFFinding, SSRFScanConfig, SSRFScanReport, SSRFSeverity, SSRFVulnerabilityType, SSRFXXEScanner  # noqa: E501
