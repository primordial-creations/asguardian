#!/usr/bin/env python3
"""
CORS Misconfiguration Checker
Tests websites for Cross-Origin Resource Sharing misconfigurations.
"""

import argparse
import urllib.request
import urllib.error
from typing import Dict, List
from datetime import datetime


class CORSChecker:
    """Checks for CORS misconfigurations."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.results = {}

    def check_cors(self, url: str) -> Dict:
        """Check CORS configuration for a URL."""
        results = {
            'url': url,
            'timestamp': datetime.now().isoformat(),
            'tests': [],
            'vulnerabilities': [],
            'score': 100
        }

        # Ensure URL has scheme
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            results['url'] = url

        # Test origins to check
        test_origins = [
            {'origin': 'https://evil.com', 'type': 'arbitrary', 'description': 'Arbitrary origin'},
            {'origin': 'null', 'type': 'null', 'description': 'Null origin'},
            {'origin': self._get_subdomain_variant(url), 'type': 'subdomain', 'description': 'Subdomain variant'},
            {'origin': self._get_suffix_variant(url), 'type': 'suffix', 'description': 'Domain suffix bypass'},
            {'origin': self._get_prefix_variant(url), 'type': 'prefix', 'description': 'Domain prefix bypass'}
        ]

        for test in test_origins:
            test_result = self._test_origin(url, test['origin'])
            test_result['type'] = test['type']
            test_result['description'] = test['description']
            results['tests'].append(test_result)

            # Check for vulnerabilities
            if test_result.get('reflects_origin', False):
                severity = self._assess_severity(test['type'], test_result)
                vuln = {
                    'type': test['type'],
                    'severity': severity,
                    'origin': test['origin'],
                    'description': f"Origin '{test['origin']}' is reflected in CORS headers",
                    'credentials': test_result.get('allows_credentials', False)
                }
                results['vulnerabilities'].append(vuln)

                # Adjust score
                if severity == 'CRITICAL':
                    results['score'] -= 40
                elif severity == 'HIGH':
                    results['score'] -= 25
                elif severity == 'MEDIUM':
                    results['score'] -= 10

        # Check for wildcard
        wildcard_test = self._test_origin(url, 'https://test.com')
        if wildcard_test.get('access_control_allow_origin') == '*':
            results['vulnerabilities'].append({
                'type': 'wildcard',
                'severity': 'MEDIUM',
                'origin': '*',
                'description': 'Wildcard CORS policy allows any origin',
                'credentials': False
            })
            results['score'] -= 15

        results['score'] = max(0, results['score'])
        self.results = results
        return results

    def _get_subdomain_variant(self, url: str) -> str:
        """Generate subdomain variant for testing."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return f"{parsed.scheme}://evil.{parsed.netloc}"

    def _get_suffix_variant(self, url: str) -> str:
        """Generate domain suffix variant for testing."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}.evil.com"

    def _get_prefix_variant(self, url: str) -> str:
        """Generate domain prefix variant for testing."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return f"{parsed.scheme}://evil{parsed.netloc}"

    def _test_origin(self, url: str, origin: str) -> Dict:
        """Test a specific origin."""
        result = {
            'origin': origin,
            'reflects_origin': False,
            'allows_credentials': False,
            'access_control_allow_origin': None,
            'access_control_allow_credentials': None,
            'error': None
        }

        try:
            request = urllib.request.Request(url, method='OPTIONS')
            request.add_header('Origin', origin)
            request.add_header('Access-Control-Request-Method', 'GET')
            request.add_header('User-Agent', 'CORSChecker/1.0')

            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                headers = dict(response.headers)

                acao = headers.get('Access-Control-Allow-Origin', '')
                acac = headers.get('Access-Control-Allow-Credentials', '')

                result['access_control_allow_origin'] = acao
                result['access_control_allow_credentials'] = acac

                # Check if origin is reflected
                if acao == origin or (acao == '*' and origin != 'null'):
                    result['reflects_origin'] = True

                # Check credentials
                if acac.lower() == 'true':
                    result['allows_credentials'] = True

        except urllib.error.HTTPError as e:
            # Still check CORS headers on error responses
            headers = dict(e.headers)
            acao = headers.get('Access-Control-Allow-Origin', '')
            acac = headers.get('Access-Control-Allow-Credentials', '')

            result['access_control_allow_origin'] = acao
            result['access_control_allow_credentials'] = acac

            if acao == origin:
                result['reflects_origin'] = True
            if acac.lower() == 'true':
                result['allows_credentials'] = True

        except urllib.error.URLError as e:
            result['error'] = str(e.reason)
        except Exception as e:
            result['error'] = str(e)

        return result

    def _assess_severity(self, test_type: str, test_result: Dict) -> str:
        """Assess vulnerability severity."""
        allows_creds = test_result.get('allows_credentials', False)

        if test_type == 'arbitrary':
            return 'CRITICAL' if allows_creds else 'HIGH'
        elif test_type == 'null':
            return 'CRITICAL' if allows_creds else 'HIGH'
        elif test_type in ['subdomain', 'suffix', 'prefix']:
            return 'HIGH' if allows_creds else 'MEDIUM'

        return 'MEDIUM'

    def print_report(self):
        """Print CORS check report."""
        results = self.results

        print("\n" + "=" * 70)
        print("CORS MISCONFIGURATION REPORT")
        print("=" * 70)

        print(f"\nURL: {results['url']}")
        print(f"Checked: {results['timestamp']}")
        print(f"Security Score: {results['score']}/100")

        # Vulnerabilities
        if results['vulnerabilities']:
            print("\n" + "-" * 40)
            print("VULNERABILITIES FOUND")
            print("-" * 40)

            # Sort by severity
            severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
            sorted_vulns = sorted(results['vulnerabilities'],
                                  key=lambda x: severity_order.get(x['severity'], 4))

            for vuln in sorted_vulns:
                print(f"\n[{vuln['severity']}] {vuln['type'].title()} Origin Attack")
                print(f"  Origin: {vuln['origin']}")
                print(f"  {vuln['description']}")
                if vuln.get('credentials'):
                    print(f"  ⚠ Credentials are allowed - HIGH RISK")

        # Test Details
        print("\n" + "-" * 40)
        print("TEST RESULTS")
        print("-" * 40)

        for test in results['tests']:
            status = "✗ VULNERABLE" if test['reflects_origin'] else "✓ Safe"
            print(f"\n{test['description']}:")
            print(f"  Origin: {test['origin']}")
            print(f"  Result: {status}")
            if test.get('access_control_allow_origin'):
                print(f"  ACAO: {test['access_control_allow_origin']}")
            if test.get('allows_credentials'):
                print(f"  Credentials: Allowed")
            if test.get('error'):
                print(f"  Error: {test['error']}")

        # Recommendations
        if results['vulnerabilities']:
            print("\n" + "-" * 40)
            print("RECOMMENDATIONS")
            print("-" * 40)
            print("\n1. Whitelist specific, trusted origins only")
            print("2. Avoid reflecting the Origin header directly")
            print("3. Never use Access-Control-Allow-Origin: * with credentials")
            print("4. Implement proper origin validation on the server")
            print("5. Be cautious with null origin (can be exploited via sandboxed iframes)")

        # Rating
        print("\n" + "-" * 40)
        print("OVERALL RATING")
        print("-" * 40)

        score = results['score']
        if score >= 90:
            rating = "A Excellent"
        elif score >= 80:
            rating = "B Good"
        elif score >= 60:
            rating = "C Needs Improvement"
        elif score >= 40:
            rating = "D Poor"
        else:
            rating = "F Critical"

        print(f"\nRating: {rating}")
        print("\n" + "=" * 70)

        # Return exit code
        has_critical = any(v['severity'] == 'CRITICAL' for v in results['vulnerabilities'])
        has_high = any(v['severity'] == 'HIGH' for v in results['vulnerabilities'])

        if has_critical:
            return 2
        elif has_high:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Check for CORS misconfigurations'
    )
    parser.add_argument(
        'url',
        help='URL to check'
    )
    parser.add_argument(
        '-t', '--timeout',
        type=float,
        default=10.0,
        help='Request timeout in seconds (default: 10.0)'
    )

    args = parser.parse_args()
    checker = CORSChecker(timeout=args.timeout)

    checker.check_cors(args.url)
    return checker.print_report()


if __name__ == '__main__':
    exit(main())
