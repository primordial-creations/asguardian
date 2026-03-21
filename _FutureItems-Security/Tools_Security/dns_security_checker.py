#!/usr/bin/env python3
"""
DNS Security Checker
Analyzes DNS configuration for security issues.
"""

import socket
import argparse
import subprocess
from typing import Dict, List, Optional
from datetime import datetime


class DNSSecurityChecker:
    """Analyzes DNS security configuration."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.results = {}

    def check_dns_security(self, domain: str) -> Dict:
        """Check DNS security for a domain."""
        results = {
            'domain': domain,
            'timestamp': datetime.now().isoformat(),
            'records': {},
            'security_checks': [],
            'issues': [],
            'score': 100
        }

        # Get DNS records
        results['records']['A'] = self._get_dns_records(domain, 'A')
        results['records']['AAAA'] = self._get_dns_records(domain, 'AAAA')
        results['records']['MX'] = self._get_dns_records(domain, 'MX')
        results['records']['TXT'] = self._get_dns_records(domain, 'TXT')
        results['records']['NS'] = self._get_dns_records(domain, 'NS')
        results['records']['CAA'] = self._get_dns_records(domain, 'CAA')

        # Perform security checks
        self._check_spf(results)
        self._check_dmarc(results)
        self._check_dkim_selector(results)
        self._check_caa(results)
        self._check_nameservers(results)
        self._check_dnssec(results, domain)

        # Calculate final score
        results['score'] = max(0, results['score'])
        self.results = results
        return results

    def _get_dns_records(self, domain: str, record_type: str) -> List[str]:
        """Get DNS records using dig or nslookup."""
        records = []

        try:
            # Try using dig first
            result = subprocess.run(
                ['dig', '+short', domain, record_type],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            if result.returncode == 0 and result.stdout.strip():
                records = [r.strip() for r in result.stdout.strip().split('\n') if r.strip()]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # Fall back to socket for A records
            if record_type == 'A':
                try:
                    records = [socket.gethostbyname(domain)]
                except socket.gaierror:
                    pass

        return records

    def _check_spf(self, results: Dict):
        """Check for SPF record."""
        txt_records = results['records'].get('TXT', [])
        spf_found = False
        spf_record = None

        for record in txt_records:
            if 'v=spf1' in record.lower():
                spf_found = True
                spf_record = record
                break

        check = {
            'name': 'SPF Record',
            'status': 'PASS' if spf_found else 'FAIL',
            'description': 'Sender Policy Framework prevents email spoofing'
        }

        if spf_found:
            check['value'] = spf_record

            # Check SPF quality
            if '+all' in spf_record:
                results['issues'].append({
                    'severity': 'CRITICAL',
                    'type': 'spf_permissive',
                    'description': 'SPF uses +all which allows any server to send'
                })
                results['score'] -= 25
            elif '?all' in spf_record:
                results['issues'].append({
                    'severity': 'MEDIUM',
                    'type': 'spf_neutral',
                    'description': 'SPF uses ?all (neutral), consider -all or ~all'
                })
                results['score'] -= 10
        else:
            results['issues'].append({
                'severity': 'HIGH',
                'type': 'no_spf',
                'description': 'No SPF record found - domain vulnerable to email spoofing'
            })
            results['score'] -= 20

        results['security_checks'].append(check)

    def _check_dmarc(self, results: Dict):
        """Check for DMARC record."""
        domain = results['domain']
        dmarc_domain = f'_dmarc.{domain}'
        dmarc_records = self._get_dns_records(dmarc_domain, 'TXT')

        dmarc_found = False
        dmarc_record = None

        for record in dmarc_records:
            if 'v=dmarc1' in record.lower():
                dmarc_found = True
                dmarc_record = record
                break

        check = {
            'name': 'DMARC Record',
            'status': 'PASS' if dmarc_found else 'FAIL',
            'description': 'Domain-based Message Authentication prevents email fraud'
        }

        if dmarc_found:
            check['value'] = dmarc_record

            # Check DMARC policy
            if 'p=none' in dmarc_record:
                results['issues'].append({
                    'severity': 'MEDIUM',
                    'type': 'dmarc_none',
                    'description': 'DMARC policy is set to none (monitoring only)'
                })
                results['score'] -= 10
        else:
            results['issues'].append({
                'severity': 'HIGH',
                'type': 'no_dmarc',
                'description': 'No DMARC record found - email authentication incomplete'
            })
            results['score'] -= 20

        results['security_checks'].append(check)

    def _check_dkim_selector(self, results: Dict):
        """Check for common DKIM selectors."""
        domain = results['domain']
        common_selectors = ['default', 'google', 'selector1', 'selector2', 'k1', 'mail']

        dkim_found = False
        for selector in common_selectors:
            dkim_domain = f'{selector}._domainkey.{domain}'
            records = self._get_dns_records(dkim_domain, 'TXT')
            if records:
                dkim_found = True
                break

        check = {
            'name': 'DKIM Record',
            'status': 'PASS' if dkim_found else 'UNKNOWN',
            'description': 'DomainKeys Identified Mail verifies email authenticity'
        }

        if not dkim_found:
            check['note'] = 'Could not find DKIM with common selectors'
            results['issues'].append({
                'severity': 'LOW',
                'type': 'dkim_unknown',
                'description': 'DKIM selector not found (may use non-standard selector)'
            })

        results['security_checks'].append(check)

    def _check_caa(self, results: Dict):
        """Check for CAA records."""
        caa_records = results['records'].get('CAA', [])

        check = {
            'name': 'CAA Records',
            'status': 'PASS' if caa_records else 'FAIL',
            'description': 'Certificate Authority Authorization controls certificate issuance'
        }

        if caa_records:
            check['value'] = ', '.join(caa_records[:3])
        else:
            results['issues'].append({
                'severity': 'MEDIUM',
                'type': 'no_caa',
                'description': 'No CAA records - any CA can issue certificates for domain'
            })
            results['score'] -= 10

        results['security_checks'].append(check)

    def _check_nameservers(self, results: Dict):
        """Check nameserver configuration."""
        ns_records = results['records'].get('NS', [])

        check = {
            'name': 'Nameserver Configuration',
            'status': 'PASS' if len(ns_records) >= 2 else 'WARNING',
            'description': 'Multiple nameservers provide redundancy'
        }

        if ns_records:
            check['value'] = f'{len(ns_records)} nameservers'

        if len(ns_records) < 2:
            results['issues'].append({
                'severity': 'MEDIUM',
                'type': 'insufficient_ns',
                'description': 'Less than 2 nameservers - no redundancy'
            })
            results['score'] -= 10

        # Check for diverse nameservers (different providers/networks)
        if ns_records:
            domains = set()
            for ns in ns_records:
                parts = ns.rstrip('.').split('.')
                if len(parts) >= 2:
                    domains.add('.'.join(parts[-2:]))

            if len(domains) == 1:
                results['issues'].append({
                    'severity': 'LOW',
                    'type': 'single_ns_provider',
                    'description': 'All nameservers from same provider - consider diversity'
                })

        results['security_checks'].append(check)

    def _check_dnssec(self, results: Dict, domain: str):
        """Check DNSSEC status."""
        dnssec_enabled = False

        try:
            # Check for DNSKEY records
            result = subprocess.run(
                ['dig', '+short', domain, 'DNSKEY'],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            if result.returncode == 0 and result.stdout.strip():
                dnssec_enabled = True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        check = {
            'name': 'DNSSEC',
            'status': 'PASS' if dnssec_enabled else 'FAIL',
            'description': 'DNS Security Extensions prevents DNS spoofing'
        }

        if not dnssec_enabled:
            results['issues'].append({
                'severity': 'MEDIUM',
                'type': 'no_dnssec',
                'description': 'DNSSEC not enabled - DNS responses can be spoofed'
            })
            results['score'] -= 15

        results['security_checks'].append(check)

    def print_report(self):
        """Print DNS security report."""
        results = self.results

        print("\n" + "=" * 70)
        print("DNS SECURITY REPORT")
        print("=" * 70)

        print(f"\nDomain: {results['domain']}")
        print(f"Checked: {results['timestamp']}")
        print(f"Security Score: {results['score']}/100")

        # DNS Records
        print("\n" + "-" * 40)
        print("DNS RECORDS")
        print("-" * 40)

        for record_type, records in results['records'].items():
            if records:
                print(f"\n{record_type}:")
                for record in records[:5]:
                    if len(record) > 60:
                        record = record[:60] + '...'
                    print(f"  {record}")
                if len(records) > 5:
                    print(f"  ... and {len(records) - 5} more")

        # Security Checks
        print("\n" + "-" * 40)
        print("SECURITY CHECKS")
        print("-" * 40)

        for check in results['security_checks']:
            status_symbol = {
                'PASS': '✓',
                'FAIL': '✗',
                'WARNING': '⚠',
                'UNKNOWN': '?'
            }.get(check['status'], '?')

            print(f"\n{status_symbol} {check['name']}: {check['status']}")
            print(f"  {check['description']}")
            if 'value' in check:
                value = check['value']
                if len(str(value)) > 60:
                    value = str(value)[:60] + '...'
                print(f"  Value: {value}")
            if 'note' in check:
                print(f"  Note: {check['note']}")

        # Issues
        if results['issues']:
            print("\n" + "-" * 40)
            print("SECURITY ISSUES")
            print("-" * 40)

            severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
            sorted_issues = sorted(results['issues'],
                                   key=lambda x: severity_order.get(x['severity'], 4))

            for issue in sorted_issues:
                print(f"\n[{issue['severity']}] {issue['type']}")
                print(f"  {issue['description']}")

        # Recommendations
        print("\n" + "-" * 40)
        print("RECOMMENDATIONS")
        print("-" * 40)

        if any(i['type'] == 'no_spf' for i in results['issues']):
            print("\n• Add SPF record: v=spf1 include:_spf.provider.com -all")

        if any(i['type'] == 'no_dmarc' for i in results['issues']):
            print("\n• Add DMARC record: v=DMARC1; p=quarantine; rua=mailto:dmarc@domain.com")

        if any(i['type'] == 'no_caa' for i in results['issues']):
            print("\n• Add CAA record to restrict certificate authorities")

        if any(i['type'] == 'no_dnssec' for i in results['issues']):
            print("\n• Enable DNSSEC with your DNS provider")

        # Rating
        print("\n" + "-" * 40)
        print("OVERALL RATING")
        print("-" * 40)

        score = results['score']
        if score >= 90:
            rating = "A Excellent"
        elif score >= 75:
            rating = "B Good"
        elif score >= 60:
            rating = "C Acceptable"
        elif score >= 40:
            rating = "D Needs Improvement"
        else:
            rating = "F Poor"

        print(f"\nRating: {rating}")
        print("\n" + "=" * 70)

        return 0 if score >= 60 else 1


def main():
    parser = argparse.ArgumentParser(
        description='Check DNS security configuration'
    )
    parser.add_argument(
        'domain',
        help='Domain to check'
    )
    parser.add_argument(
        '-t', '--timeout',
        type=float,
        default=10.0,
        help='Query timeout in seconds (default: 10.0)'
    )

    args = parser.parse_args()
    checker = DNSSecurityChecker(timeout=args.timeout)

    checker.check_dns_security(args.domain)
    return checker.print_report()


if __name__ == '__main__':
    exit(main())
