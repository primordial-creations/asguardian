"""Tests for DNS security checker."""
import pytest
from unittest.mock import patch, MagicMock
from Asgard.Heimdall.Security.DNS.services.dns_checker import DNSSecurityChecker
from Asgard.Heimdall.Security.DNS.models.dns_models import DNSScanReport


class TestDNSSecurityCheckerInstantiation:
    def test_checker_can_be_instantiated(self):
        assert DNSSecurityChecker() is not None

    def test_checker_accepts_custom_timeout(self):
        checker = DNSSecurityChecker(timeout=5.0)
        assert checker is not None


class TestDNSSecurityCheckerReportStructure:
    def test_report_has_required_fields(self):
        checker = DNSSecurityChecker(timeout=2.0)
        with patch.object(checker, '_get_records', return_value=[]):
            report: DNSScanReport = checker.check('example.com')
        assert hasattr(report, 'domain')
        assert hasattr(report, 'score')
        assert hasattr(report, 'issues')
        assert report.domain == 'example.com'
        assert isinstance(report.score, int)
        assert isinstance(report.issues, list)

    def test_report_has_security_checks_field(self):
        checker = DNSSecurityChecker(timeout=2.0)
        with patch.object(checker, '_get_records', return_value=[]):
            report: DNSScanReport = checker.check('example.com')
        assert hasattr(report, 'security_checks')
        assert isinstance(report.security_checks, list)
