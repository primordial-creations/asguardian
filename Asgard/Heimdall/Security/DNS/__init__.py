"""
Heimdall Security DNS — live DNS security configuration checker.

Checks SPF, DMARC, DKIM, CAA records, nameserver redundancy, and DNSSEC status.
Requires 'dig' to be available on the system path for full functionality.

Usage:
    from Asgard.Heimdall.Security.DNS import DNSSecurityChecker

    checker = DNSSecurityChecker()
    report = checker.check("example.com")
    print(f"DNS score: {report.score}/100  Rating: {report.rating}")
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Heimdall.Security.DNS.models.dns_models import DNSCheck, DNSIssue, DNSScanReport
from Asgard.Heimdall.Security.DNS.services.dns_checker import DNSSecurityChecker

__all__ = ["DNSCheck", "DNSIssue", "DNSScanReport", "DNSSecurityChecker"]
