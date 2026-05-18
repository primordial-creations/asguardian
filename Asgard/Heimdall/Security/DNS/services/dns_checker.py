"""DNS security checker — live DNS query-based analysis."""

import socket
import subprocess
from datetime import datetime
from typing import Dict, List

from Asgard.Heimdall.Security.DNS.models.dns_models import DNSCheck, DNSIssue, DNSScanReport

_COMMON_DKIM_SELECTORS = ["default", "google", "selector1", "selector2", "k1", "mail"]


class DNSSecurityChecker:
    """Analyzes DNS configuration for security issues (SPF, DMARC, DKIM, CAA, DNSSEC)."""

    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout

    def check(self, domain: str) -> DNSScanReport:
        report = DNSScanReport(domain=domain, timestamp=datetime.now().isoformat())

        for rtype in ("A", "AAAA", "MX", "TXT", "NS", "CAA"):
            report.records[rtype] = self._get_records(domain, rtype)

        self._check_spf(report)
        self._check_dmarc(report)
        self._check_dkim(report)
        self._check_caa(report)
        self._check_nameservers(report)
        self._check_dnssec(report, domain)

        report.score = max(0, report.score)
        return report

    # ── private helpers ────────────────────────────────────────────────────────

    def _get_records(self, domain: str, rtype: str) -> List[str]:
        try:
            result = subprocess.run(
                ["dig", "+short", domain, rtype],
                capture_output=True, text=True, timeout=self.timeout,
            )
            if result.returncode == 0 and result.stdout.strip():
                return [r.strip() for r in result.stdout.strip().splitlines() if r.strip()]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            if rtype == "A":
                try:
                    return [socket.gethostbyname(domain)]
                except socket.gaierror:
                    pass
        return []

    def _check_spf(self, report: DNSScanReport) -> None:
        spf = next((r for r in report.records.get("TXT", []) if "v=spf1" in r.lower()), None)
        check = DNSCheck(name="SPF Record", status="PASS" if spf else "FAIL",
                         description="Sender Policy Framework prevents email spoofing",
                         value=spf)
        if spf:
            if "+all" in spf:
                report.issues.append(DNSIssue(severity="CRITICAL", issue_type="spf_permissive",
                                               description="SPF uses +all which allows any server to send"))
                report.score -= 25
            elif "?all" in spf:
                report.issues.append(DNSIssue(severity="MEDIUM", issue_type="spf_neutral",
                                               description="SPF uses ?all (neutral); consider -all or ~all"))
                report.score -= 10
        else:
            report.issues.append(DNSIssue(severity="HIGH", issue_type="no_spf",
                                           description="No SPF record — domain vulnerable to email spoofing"))
            report.score -= 20
        report.security_checks.append(check)

    def _check_dmarc(self, report: DNSScanReport) -> None:
        dmarc_records = self._get_records(f"_dmarc.{report.domain}", "TXT")
        dmarc = next((r for r in dmarc_records if "v=dmarc1" in r.lower()), None)
        check = DNSCheck(name="DMARC Record", status="PASS" if dmarc else "FAIL",
                         description="Domain-based Message Authentication prevents email fraud",
                         value=dmarc)
        if dmarc:
            if "p=none" in dmarc:
                report.issues.append(DNSIssue(severity="MEDIUM", issue_type="dmarc_none",
                                               description="DMARC policy is set to none (monitoring only)"))
                report.score -= 10
        else:
            report.issues.append(DNSIssue(severity="HIGH", issue_type="no_dmarc",
                                           description="No DMARC record — email authentication incomplete"))
            report.score -= 20
        report.security_checks.append(check)

    def _check_dkim(self, report: DNSScanReport) -> None:
        found = any(
            self._get_records(f"{sel}._domainkey.{report.domain}", "TXT")
            for sel in _COMMON_DKIM_SELECTORS
        )
        check = DNSCheck(name="DKIM Record", status="PASS" if found else "UNKNOWN",
                         description="DomainKeys Identified Mail verifies email authenticity",
                         note=None if found else "Could not find DKIM with common selectors")
        if not found:
            report.issues.append(DNSIssue(severity="LOW", issue_type="dkim_unknown",
                                           description="DKIM selector not found (may use non-standard selector)"))
        report.security_checks.append(check)

    def _check_caa(self, report: DNSScanReport) -> None:
        caa = report.records.get("CAA", [])
        check = DNSCheck(name="CAA Records", status="PASS" if caa else "FAIL",
                         description="Certificate Authority Authorization controls certificate issuance",
                         value=", ".join(caa[:3]) if caa else None)
        if not caa:
            report.issues.append(DNSIssue(severity="MEDIUM", issue_type="no_caa",
                                           description="No CAA records — any CA can issue certificates"))
            report.score -= 10
        report.security_checks.append(check)

    def _check_nameservers(self, report: DNSScanReport) -> None:
        ns = report.records.get("NS", [])
        check = DNSCheck(name="Nameserver Configuration",
                         status="PASS" if len(ns) >= 2 else "WARNING",
                         description="Multiple nameservers provide redundancy",
                         value=f"{len(ns)} nameservers" if ns else None)
        if len(ns) < 2:
            report.issues.append(DNSIssue(severity="MEDIUM", issue_type="insufficient_ns",
                                           description="Less than 2 nameservers — no redundancy"))
            report.score -= 10
        report.security_checks.append(check)

    def _check_dnssec(self, report: DNSScanReport, domain: str) -> None:
        enabled = False
        try:
            result = subprocess.run(
                ["dig", "+short", domain, "DNSKEY"],
                capture_output=True, text=True, timeout=self.timeout,
            )
            enabled = result.returncode == 0 and bool(result.stdout.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        check = DNSCheck(name="DNSSEC", status="PASS" if enabled else "FAIL",
                         description="DNS Security Extensions prevents DNS spoofing")
        if not enabled:
            report.issues.append(DNSIssue(severity="MEDIUM", issue_type="no_dnssec",
                                           description="DNSSEC not enabled — DNS responses can be spoofed"))
            report.score -= 15
        report.security_checks.append(check)
