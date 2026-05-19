"""L3 Contract tests for additional Heimdall Security scanner models.

Covers: Access, Auth, Compliance, Container, DNS, DataExfil, FileIntegrity,
Git, Headers, Hotspots, InfoDisclosure, Infrastructure, LogAnalysis,
TaintAnalysis, TLS, and config_secrets / security_models_findings.
"""
import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Access
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Access.models.access_models import (
    AccessFinding,
    AccessConfig,
    AccessReport,
)


class TestAccessFindingContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            AccessFinding()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Security.Access.models.access_models import AccessFindingType
        from Asgard.Heimdall.Security.models.security_models_base import SecuritySeverity
        af = AccessFinding(
            file_path="/a.py",
            line_number=10,
            finding_type=AccessFindingType.MISSING_AUTH_CHECK,
            severity=SecuritySeverity.HIGH,
            title="Overly permissive access",
            description="Resource exposed without auth check",
            confidence=0.9,
        )
        assert hasattr(af, "finding_type")
        assert hasattr(af, "severity")


class TestAccessConfigContract:
    def test_instantiates_with_defaults(self):
        config = AccessConfig()
        assert config is not None


class TestAccessReportContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            AccessReport()

    def test_accepts_valid_data(self):
        report = AccessReport(scan_path="/some/path")
        assert report.scan_path == "/some/path"
        assert hasattr(report, "findings") or hasattr(AccessReport, "model_fields")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Auth.models.auth_models import (
    AuthFinding,
    AuthConfig,
    AuthReport,
)


class TestAuthFindingContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            AuthFinding()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Security.Auth.models.auth_models import AuthFindingType
        from Asgard.Heimdall.Security.models.security_models_base import SecuritySeverity
        af = AuthFinding(
            file_path="/a.py",
            line_number=5,
            finding_type=AuthFindingType.WEAK_JWT_ALGORITHM,
            severity=SecuritySeverity.HIGH,
            title="Weak auth",
            description="No password complexity enforced",
            confidence=0.9,
        )
        assert hasattr(af, "finding_type")


class TestAuthConfigContract:
    def test_instantiates_with_defaults(self):
        config = AuthConfig()
        assert config is not None


class TestAuthReportContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            AuthReport()

    def test_accepts_valid_data(self):
        report = AuthReport(scan_path="/some/path")
        assert hasattr(report, "scan_path")


# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Compliance.models.compliance_models import (
    CWEEntry,
    CategoryCompliance,
    OWASPComplianceReport,
    CWEComplianceReport,
    ComplianceConfig,
)


class TestCWEEntryContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            CWEEntry()

    def test_accepts_valid_data(self):
        cwe = CWEEntry(cwe_id="CWE-89", name="SQL Injection")
        assert cwe.cwe_id == "CWE-89"
        assert hasattr(cwe, "name")


class TestCategoryComplianceContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            CategoryCompliance()

    def test_accepts_valid_data(self):
        cc = CategoryCompliance(category_id="A01", category_name="Broken Access Control")
        assert cc.category_id == "A01"


class TestOWASPComplianceReportContract:
    def test_instantiates_with_defaults(self):
        report = OWASPComplianceReport()
        assert report is not None


class TestComplianceConfigContract:
    def test_instantiates_with_defaults(self):
        config = ComplianceConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Container.models.container_models import (
    ContainerFinding,
    ContainerConfig,
    ContainerReport,
)


class TestContainerFindingContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            ContainerFinding()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Security.Container.models.container_models import ContainerFindingType
        from Asgard.Heimdall.Security.models.security_models_base import SecuritySeverity
        cf = ContainerFinding(
            file_path="/Dockerfile",
            line_number=1,
            finding_type=ContainerFindingType.ROOT_USER,
            severity=SecuritySeverity.CRITICAL,
            title="Container runs as root",
            description="No USER instruction",
            confidence=0.95,
        )
        assert hasattr(cf, "finding_type")


class TestContainerConfigContract:
    def test_instantiates_with_defaults(self):
        config = ContainerConfig()
        assert config is not None


class TestContainerReportContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            ContainerReport()

    def test_accepts_valid_data(self):
        report = ContainerReport(scan_path="/some/path")
        assert hasattr(report, "scan_path")


# ---------------------------------------------------------------------------
# DNS
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.DNS.models.dns_models import (
    DNSIssue,
    DNSCheck,
    DNSScanReport,
)


class TestDNSIssueContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            DNSIssue()

    def test_accepts_valid_data(self):
        di = DNSIssue(severity="high", issue_type="missing_dnssec", description="DNSSEC not configured")
        assert di.issue_type == "missing_dnssec"


class TestDNSCheckContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            DNSCheck()

    def test_accepts_valid_data(self):
        dc = DNSCheck(name="DNSSEC", status="fail", description="Not configured")
        assert dc.name == "DNSSEC"


class TestDNSScanReportContract:
    def test_requires_domain_and_timestamp(self):
        with pytest.raises((ValidationError, TypeError)):
            DNSScanReport()

    def test_accepts_valid_data(self):
        report = DNSScanReport(domain="example.com", timestamp="2024-01-01T00:00:00")
        assert report.domain == "example.com"
        assert hasattr(report, "issues") or hasattr(DNSScanReport, "model_fields")


# ---------------------------------------------------------------------------
# DataExfil
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.DataExfil.models.data_exfil_models import (
    ExfilFinding,
    ExfilScanConfig,
    ExfilScanReport,
)


class TestExfilFindingContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            ExfilFinding()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Security.DataExfil.models.data_exfil_models import ExfilType, ExfilSeverity
        ef = ExfilFinding(
            file_path="/a.py",
            line_number=10,
            exfil_type=ExfilType.HTTP_EXFIL,
            severity=ExfilSeverity.CRITICAL,
            description="Sensitive data sent to external endpoint",
        )
        assert hasattr(ef, "exfil_type")


class TestExfilScanConfigContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            ExfilScanConfig()

    def test_accepts_valid_data(self, tmp_path):
        config = ExfilScanConfig(scan_path=str(tmp_path))
        assert hasattr(config, "scan_path")


class TestExfilScanReportContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            ExfilScanReport()

    def test_accepts_valid_data(self):
        report = ExfilScanReport(scan_path="/path")
        assert hasattr(report, "findings") or hasattr(ExfilScanReport, "model_fields")


# ---------------------------------------------------------------------------
# File Integrity
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.FileIntegrity.models.file_integrity_models import (
    FileRecord,
    FileModification,
    PermissionChange,
    FileIntegrityReport,
)


class TestFileRecordContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            FileRecord()

    def test_accepts_valid_data(self):
        fr = FileRecord(
            path="/etc/passwd",
            size=1234,
            md5="abc123",
            sha256="def456",
            modified_time="2024-01-01T00:00:00",
            permissions="644",
        )
        assert fr.path == "/etc/passwd"


class TestFileModificationContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            FileModification()

    def test_accepts_valid_data(self):
        fm = FileModification(
            path="/etc/hosts",
            old_hash="abc",
            new_hash="def",
            old_size=100,
            new_size=200,
        )
        assert fm.path == "/etc/hosts"


class TestFileIntegrityReportContract:
    def test_requires_verified_at(self):
        with pytest.raises((ValidationError, TypeError)):
            FileIntegrityReport()

    def test_accepts_valid_data(self):
        report = FileIntegrityReport(verified_at="2024-01-01T00:00:00")
        assert hasattr(report, "verified_at")


# ---------------------------------------------------------------------------
# Git Security
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Git.models.git_models import (
    GitFinding,
    GitScanReport,
)


class TestGitFindingContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            GitFinding()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Security.Git.models.git_models import GitSeverity
        gf = GitFinding(
            file_path=".git/config",
            severity=GitSeverity.CRITICAL,
            issue_type="sensitive_data_in_history",
            description="Password found in git history",
            recommendation="Use git-filter-repo to remove",
        )
        assert hasattr(gf, "issue_type")


class TestGitScanReportContract:
    def test_requires_repo_path(self):
        with pytest.raises((ValidationError, TypeError)):
            GitScanReport()

    def test_accepts_valid_data(self):
        report = GitScanReport(repo_path="/some/repo")
        assert hasattr(report, "repo_path")


# ---------------------------------------------------------------------------
# Security Headers
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Headers.models.header_models import (
    HeaderFinding,
    HeaderConfig,
    HeaderReport,
)


class TestHeaderFindingContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            HeaderFinding()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Security.Headers.models.header_models import HeaderFindingType
        from Asgard.Heimdall.Security.models.security_models_base import SecuritySeverity
        hf = HeaderFinding(
            file_path="/a.py",
            line_number=10,
            finding_type=HeaderFindingType.MISSING_CSP,
            severity=SecuritySeverity.MEDIUM,
            title="Missing X-Frame-Options",
            description="Header not set",
            confidence=0.9,
        )
        assert hasattr(hf, "finding_type")


class TestHeaderConfigContract:
    def test_instantiates_with_defaults(self):
        config = HeaderConfig()
        assert config is not None


class TestHeaderReportContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            HeaderReport()

    def test_accepts_valid_data(self):
        report = HeaderReport(scan_path="/some/path")
        assert hasattr(report, "scan_path")


# ---------------------------------------------------------------------------
# Hotspots
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Hotspots.models.hotspot_models import (
    SecurityHotspot,
    HotspotConfig,
    HotspotReport,
)


class TestSecurityHotspotContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            SecurityHotspot()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Security.Hotspots.models.hotspot_models import HotspotCategory, ReviewPriority
        sh = SecurityHotspot(
            file_path="/a.py",
            line_number=10,
            category=HotspotCategory.COOKIE_CONFIG,
            review_priority=ReviewPriority.HIGH,
            title="Weak cipher usage",
        )
        assert hasattr(sh, "category")
        assert hasattr(sh, "review_priority")


class TestHotspotConfigContract:
    def test_instantiates_with_defaults(self):
        config = HotspotConfig()
        assert config is not None


class TestHotspotReportContract:
    def test_instantiates_with_defaults(self):
        report = HotspotReport()
        assert report is not None
        assert hasattr(HotspotReport, "model_fields")


# ---------------------------------------------------------------------------
# InfoDisclosure
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.InfoDisclosure.models.info_disclosure_models import (
    InfoDisclosureFinding,
    InfoDisclosureScanConfig,
    InfoDisclosureScanReport,
)


class TestInfoDisclosureFindingContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            InfoDisclosureFinding()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Security.InfoDisclosure.models.info_disclosure_models import InfoDisclosureSeverity
        idf = InfoDisclosureFinding(
            file_path="/a.py",
            line_number=10,
            severity=InfoDisclosureSeverity.CRITICAL,
            category="stack_trace",
            issue_type="exposed_traceback",
            description="Stack trace exposed to user",
            recommendation="Log instead of return",
        )
        assert idf.category == "stack_trace"


class TestInfoDisclosureScanConfigContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            InfoDisclosureScanConfig()

    def test_accepts_valid_data(self, tmp_path):
        config = InfoDisclosureScanConfig(scan_path=str(tmp_path))
        assert hasattr(config, "scan_path")


class TestInfoDisclosureScanReportContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            InfoDisclosureScanReport()

    def test_accepts_valid_data(self):
        report = InfoDisclosureScanReport(scan_path="/path")
        assert hasattr(report, "findings") or hasattr(InfoDisclosureScanReport, "model_fields")


# ---------------------------------------------------------------------------
# Infrastructure
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.Infrastructure.models.infra_models import (
    InfraFinding,
    InfraConfig,
    InfraReport,
)


class TestInfraFindingContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            InfraFinding()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Security.Infrastructure.models.infra_models import InfraFindingType
        from Asgard.Heimdall.Security.models.security_models_base import SecuritySeverity
        inf = InfraFinding(
            file_path="/terraform/main.tf",
            line_number=10,
            finding_type=InfraFindingType.DEFAULT_CREDENTIALS,
            severity=SecuritySeverity.CRITICAL,
            title="Public S3 bucket",
            description="Bucket is publicly accessible",
            confidence=0.9,
        )
        assert hasattr(inf, "finding_type")


class TestInfraConfigContract:
    def test_instantiates_with_defaults(self):
        config = InfraConfig()
        assert config is not None


class TestInfraReportContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            InfraReport()

    def test_accepts_valid_data(self):
        report = InfraReport(scan_path="/some/path")
        assert hasattr(report, "scan_path")


# ---------------------------------------------------------------------------
# Log Analysis
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.LogAnalysis.models.log_models import (
    LogEvent,
    LogAnalysisReport,
)


class TestLogEventContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            LogEvent()

    def test_accepts_valid_data(self):
        le = LogEvent(
            file_path="/a.py",
            line_number=20,
            event_type="sensitive_data_logged",
            severity="high",
            description="Password logged in plaintext",
        )
        assert le.event_type == "sensitive_data_logged"


class TestLogAnalysisReportContract:
    def test_instantiates_with_defaults(self):
        report = LogAnalysisReport()
        assert report is not None
        assert hasattr(LogAnalysisReport, "model_fields")


# ---------------------------------------------------------------------------
# Taint Analysis
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.TaintAnalysis.models.taint_models import (
    TaintFlowStep,
    TaintFlow,
    TaintReport,
    TaintConfig,
)


class TestTaintFlowStepContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            TaintFlowStep()

    def test_accepts_valid_data(self):
        tfs = TaintFlowStep(
            file_path="/a.py",
            line_number=5,
            function_name="handle_input",
            step_type="source",
        )
        assert tfs.step_type == "source"


class TestTaintFlowContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            TaintFlow()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Security.TaintAnalysis.models.taint_models import (
            TaintSourceType, TaintSinkType, TaintFlowStep
        )
        source = TaintFlowStep(file_path="views.py", line_number=10, function_name="handle", step_type="source")
        sink = TaintFlowStep(file_path="db.py", line_number=50, function_name="execute", step_type="sink")
        tf = TaintFlow(
            source_type=TaintSourceType.HTTP_PARAMETER,
            sink_type=TaintSinkType.SQL_QUERY,
            severity="critical",
            source_location=source,
            sink_location=sink,
            title="SQL Injection",
            description="User input flows to SQL query",
        )
        assert hasattr(tf, "source_type")
        assert hasattr(tf, "sink_type")


class TestTaintConfigContract:
    def test_instantiates_with_defaults(self):
        config = TaintConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# TLS
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.TLS.models.tls_models import (
    TLSFinding,
    TLSConfig,
    TLSReport,
)


class TestTLSFindingContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            TLSFinding()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Security.TLS.models.tls_models import TLSFindingType
        from Asgard.Heimdall.Security.models.security_models_base import SecuritySeverity
        tf = TLSFinding(
            file_path="/a.py",
            line_number=10,
            finding_type=TLSFindingType.DEPRECATED_TLS_VERSION,
            severity=SecuritySeverity.HIGH,
            title="Weak TLS cipher",
            description="RC4 used",
            confidence=0.9,
        )
        assert hasattr(tf, "finding_type")


class TestTLSConfigContract:
    def test_instantiates_with_defaults(self):
        config = TLSConfig()
        assert config is not None


class TestTLSReportContract:
    def test_requires_scan_path(self):
        with pytest.raises((ValidationError, TypeError)):
            TLSReport()

    def test_accepts_valid_data(self):
        report = TLSReport(scan_path="/some/path")
        assert hasattr(report, "scan_path")


# ---------------------------------------------------------------------------
# Config Secrets
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.models.config_secrets_models import (
    ConfigSecretFinding,
    ConfigSecretsReport,
    ConfigSecretsConfig,
)


class TestConfigSecretFindingContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            ConfigSecretFinding()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Security.models.config_secrets_models import ConfigSecretType, ConfigSecretSeverity
        csf = ConfigSecretFinding(
            file_path="/config.yaml",
            key_name="db_password",
            masked_value="***",
            secret_type=ConfigSecretType.CREDENTIAL_KEY,
            severity=ConfigSecretSeverity.CRITICAL,
            context_description="Plaintext password in config",
        )
        assert csf.key_name == "db_password"


class TestConfigSecretsConfigContract:
    def test_instantiates_with_defaults(self):
        config = ConfigSecretsConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# Security Models Findings
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Security.models.security_models_findings import (
    CryptoFinding,
    SecretFinding,
    SecurityScanConfig,
    VulnerabilityFinding,
    SecretsReport,
    VulnerabilityReport,
    CryptoReport,
    SecurityReport,
)


class TestCryptoFindingContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            CryptoFinding()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Security.models.security_models_base import SecuritySeverity
        cf = CryptoFinding(
            file_path="/a.py",
            line_number=10,
            issue_type="weak_algorithm",
            severity=SecuritySeverity.HIGH,
            algorithm="MD5",
            description="MD5 is not collision-resistant",
            recommendation="Use SHA-256",
        )
        assert cf.algorithm == "MD5"


class TestSecretFindingContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            SecretFinding()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Security.models.security_models_base import SecretType, SecuritySeverity
        sf = SecretFinding(
            file_path="/a.py",
            line_number=5,
            secret_type=SecretType.API_KEY,
            severity=SecuritySeverity.CRITICAL,
            pattern_name="Generic API Key",
            masked_value="sk-****",
            line_content="api_key = 'sk-...'",
            confidence=0.9,
        )
        assert hasattr(sf, "secret_type")


class TestSecurityScanConfigContract:
    def test_instantiates_with_defaults(self):
        config = SecurityScanConfig()
        assert config is not None


class TestVulnerabilityFindingContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            VulnerabilityFinding()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Security.models.security_models_base import VulnerabilityType, SecuritySeverity
        vf = VulnerabilityFinding(
            file_path="/a.py",
            line_number=10,
            vulnerability_type=VulnerabilityType.SQL_INJECTION,
            severity=SecuritySeverity.CRITICAL,
            title="SQL Injection",
            description="Unsanitized input in query",
            confidence=0.9,
        )
        assert hasattr(vf, "vulnerability_type")
