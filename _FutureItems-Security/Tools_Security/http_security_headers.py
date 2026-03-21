#!/usr/bin/env python3
"""
HTTP Security Headers Checker
Analyzes HTTP response headers for security best practices.
"""

import argparse
import urllib.request
import urllib.error
from typing import Dict, List, Optional
from datetime import datetime


class HTTPSecurityHeadersChecker:
    """Analyzes HTTP security headers."""

    # Security headers to check
    SECURITY_HEADERS = {
        'Strict-Transport-Security': {
            'name': 'HSTS',
            'severity': 'HIGH',
            'description': 'Enforces HTTPS connections',
            'recommendation': 'Add: Strict-Transport-Security: max-age=31536000; includeSubDomains'
        },
        'Content-Security-Policy': {
            'name': 'CSP',
            'severity': 'HIGH',
            'description': 'Prevents XSS and injection attacks',
            'recommendation': "Add Content-Security-Policy header with appropriate directives"
        },
        'X-Content-Type-Options': {
            'name': 'X-Content-Type-Options',
            'severity': 'MEDIUM',
            'description': 'Prevents MIME-type sniffing',
            'recommendation': 'Add: X-Content-Type-Options: nosniff'
        },
        'X-Frame-Options': {
            'name': 'X-Frame-Options',
            'severity': 'MEDIUM',
            'description': 'Prevents clickjacking attacks',
            'recommendation': 'Add: X-Frame-Options: DENY or SAMEORIGIN'
        },
        'X-XSS-Protection': {
            'name': 'X-XSS-Protection',
            'severity': 'LOW',
            'description': 'Legacy XSS protection (use CSP instead)',
            'recommendation': 'Add: X-XSS-Protection: 1; mode=block (or rely on CSP)'
        },
        'Referrer-Policy': {
            'name': 'Referrer-Policy',
            'severity': 'MEDIUM',
            'description': 'Controls referrer information',
            'recommendation': 'Add: Referrer-Policy: strict-origin-when-cross-origin'
        },
        'Permissions-Policy': {
            'name': 'Permissions-Policy',
            'severity': 'MEDIUM',
            'description': 'Controls browser features',
            'recommendation': 'Add Permissions-Policy to restrict unnecessary features'
        },
        'Cross-Origin-Embedder-Policy': {
            'name': 'COEP',
            'severity': 'LOW',
            'description': 'Controls cross-origin embedding',
            'recommendation': 'Add: Cross-Origin-Embedder-Policy: require-corp'
        },
        'Cross-Origin-Opener-Policy': {
            'name': 'COOP',
            'severity': 'LOW',
            'description': 'Isolates browsing context',
            'recommendation': 'Add: Cross-Origin-Opener-Policy: same-origin'
        },
        'Cross-Origin-Resource-Policy': {
            'name': 'CORP',
            'severity': 'LOW',
            'description': 'Controls resource loading',
            'recommendation': 'Add: Cross-Origin-Resource-Policy: same-origin'
        }
    }

    # Headers that should NOT be present
    INSECURE_HEADERS = {
        'Server': {
            'severity': 'LOW',
            'description': 'Reveals server software version',
            'recommendation': 'Remove or minimize Server header information'
        },
        'X-Powered-By': {
            'severity': 'LOW',
            'description': 'Reveals technology stack',
            'recommendation': 'Remove X-Powered-By header'
        },
        'X-AspNet-Version': {
            'severity': 'LOW',
            'description': 'Reveals ASP.NET version',
            'recommendation': 'Remove X-AspNet-Version header'
        },
        'X-AspNetMvc-Version': {
            'severity': 'LOW',
            'description': 'Reveals ASP.NET MVC version',
            'recommendation': 'Remove X-AspNetMvc-Version header'
        }
    }

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.results = {}

    def check_url(self, url: str) -> Dict:
        """Check security headers for a URL."""
        results = {
            'url': url,
            'timestamp': datetime.now().isoformat(),
            'status': None,
            'headers': {},
            'present': [],
            'missing': [],
            'insecure': [],
            'score': 0,
            'max_score': 100
        }

        # Ensure URL has scheme
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            results['url'] = url

        try:
            request = urllib.request.Request(url, method='GET')
            request.add_header('User-Agent', 'SecurityHeadersChecker/1.0')

            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                results['status'] = response.status
                results['headers'] = dict(response.headers)

        except urllib.error.HTTPError as e:
            results['status'] = e.code
            results['headers'] = dict(e.headers)
        except urllib.error.URLError as e:
            results['error'] = f"Connection error: {str(e.reason)}"
            return results
        except Exception as e:
            results['error'] = f"Error: {str(e)}"
            return results

        # Analyze headers
        self.analyze_headers(results)
        self.results = results
        return results

    def analyze_headers(self, results: Dict):
        """Analyze security headers and calculate score."""
        headers = {k.lower(): v for k, v in results['headers'].items()}
        score = 0
        points_per_header = 100 // len(self.SECURITY_HEADERS)

        # Check for required security headers
        for header, config in self.SECURITY_HEADERS.items():
            header_lower = header.lower()
            if header_lower in headers:
                value = headers[header_lower]
                results['present'].append({
                    'header': header,
                    'value': value,
                    'name': config['name']
                })

                # Additional validation
                if header == 'Strict-Transport-Security':
                    score += self.validate_hsts(value, points_per_header)
                elif header == 'Content-Security-Policy':
                    score += self.validate_csp(value, points_per_header)
                elif header == 'X-Frame-Options':
                    score += self.validate_xfo(value, points_per_header)
                else:
                    score += points_per_header
            else:
                results['missing'].append({
                    'header': header,
                    'severity': config['severity'],
                    'description': config['description'],
                    'recommendation': config['recommendation']
                })

        # Check for insecure headers
        for header, config in self.INSECURE_HEADERS.items():
            header_lower = header.lower()
            if header_lower in headers:
                results['insecure'].append({
                    'header': header,
                    'value': headers[header_lower],
                    'severity': config['severity'],
                    'description': config['description'],
                    'recommendation': config['recommendation']
                })
                score -= 2  # Small penalty for info disclosure

        results['score'] = max(0, min(100, score))

    def validate_hsts(self, value: str, max_points: int) -> int:
        """Validate HSTS header value."""
        score = max_points // 2

        value_lower = value.lower()
        if 'max-age=' in value_lower:
            try:
                max_age = int(value_lower.split('max-age=')[1].split(';')[0])
                if max_age >= 31536000:  # 1 year
                    score += max_points // 4
            except (ValueError, IndexError):
                pass

        if 'includesubdomains' in value_lower:
            score += max_points // 4

        return score

    def validate_csp(self, value: str, max_points: int) -> int:
        """Validate CSP header value."""
        score = max_points // 2

        value_lower = value.lower()

        # Check for unsafe directives
        if "'unsafe-inline'" in value_lower:
            score -= max_points // 4
        if "'unsafe-eval'" in value_lower:
            score -= max_points // 4

        # Good directives
        if 'default-src' in value_lower:
            score += max_points // 4
        if 'script-src' in value_lower:
            score += max_points // 8

        return max(0, score)

    def validate_xfo(self, value: str, max_points: int) -> int:
        """Validate X-Frame-Options header value."""
        value_upper = value.upper()
        if value_upper in ('DENY', 'SAMEORIGIN'):
            return max_points
        return max_points // 2

    def print_report(self):
        """Print security headers report."""
        results = self.results

        print("\n" + "=" * 70)
        print("HTTP SECURITY HEADERS REPORT")
        print("=" * 70)

        print(f"\nURL: {results['url']}")
        print(f"Checked: {results['timestamp']}")

        if 'error' in results:
            print(f"\nError: {results['error']}")
            return 1

        print(f"HTTP Status: {results['status']}")
        print(f"Security Score: {results['score']}/{results['max_score']}")

        # Present headers
        if results['present']:
            print("\n" + "-" * 40)
            print("✓ SECURITY HEADERS PRESENT")
            print("-" * 40)

            for item in results['present']:
                print(f"\n{item['name']}:")
                print(f"  Header: {item['header']}")
                value = item['value']
                if len(value) > 60:
                    value = value[:60] + '...'
                print(f"  Value: {value}")

        # Missing headers
        if results['missing']:
            print("\n" + "-" * 40)
            print("✗ MISSING SECURITY HEADERS")
            print("-" * 40)

            # Sort by severity
            severity_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
            sorted_missing = sorted(results['missing'], key=lambda x: severity_order[x['severity']])

            for item in sorted_missing:
                print(f"\n[{item['severity']}] {item['header']}")
                print(f"  {item['description']}")
                print(f"  → {item['recommendation']}")

        # Insecure headers
        if results['insecure']:
            print("\n" + "-" * 40)
            print("⚠ INFORMATION DISCLOSURE HEADERS")
            print("-" * 40)

            for item in results['insecure']:
                print(f"\n{item['header']}: {item['value']}")
                print(f"  {item['description']}")
                print(f"  → {item['recommendation']}")

        # Rating
        print("\n" + "-" * 40)
        print("OVERALL RATING")
        print("-" * 40)

        score = results['score']
        if score >= 90:
            rating = "A+ Excellent"
        elif score >= 80:
            rating = "A Good"
        elif score >= 70:
            rating = "B Acceptable"
        elif score >= 50:
            rating = "C Needs Improvement"
        elif score >= 30:
            rating = "D Poor"
        else:
            rating = "F Critical"

        print(f"\nRating: {rating}")

        # Summary
        print("\n" + "-" * 40)
        print("SUMMARY")
        print("-" * 40)
        print(f"Headers Present: {len(results['present'])}/{len(self.SECURITY_HEADERS)}")

        missing_high = sum(1 for m in results['missing'] if m['severity'] == 'HIGH')
        if missing_high > 0:
            print(f"⚠ {missing_high} high-severity headers missing")

        print("\n" + "=" * 70)

        return 0 if score >= 70 else 1


def main():
    parser = argparse.ArgumentParser(
        description='Check HTTP security headers'
    )
    parser.add_argument(
        'url',
        help='URL to check'
    )
    parser.add_argument(
        '-t', '--timeout',
        type=float,
        default=10.0,
        help='Connection timeout in seconds (default: 10.0)'
    )
    parser.add_argument(
        '--all-headers',
        action='store_true',
        help='Show all response headers'
    )

    args = parser.parse_args()
    checker = HTTPSecurityHeadersChecker(timeout=args.timeout)

    checker.check_url(args.url)
    exit_code = checker.print_report()

    if args.all_headers and 'headers' in checker.results:
        print("\n" + "-" * 40)
        print("ALL RESPONSE HEADERS")
        print("-" * 40)
        for header, value in sorted(checker.results['headers'].items()):
            if len(value) > 60:
                value = value[:60] + '...'
            print(f"{header}: {value}")

    return exit_code


if __name__ == '__main__':
    exit(main())
