#!/usr/bin/env python3
"""
SSL/TLS Certificate Checker
Analyzes SSL/TLS certificates and configuration for security issues.
"""

import ssl
import socket
import argparse
from datetime import datetime
from typing import Dict, List, Optional
import hashlib


class SSLChecker:
    """Analyzes SSL/TLS certificates and configurations."""

    # Weak cipher suites
    WEAK_CIPHERS = {
        'RC4', 'DES', '3DES', 'MD5', 'NULL', 'EXPORT', 'anon', 'ADH', 'AECDH'
    }

    # Recommended cipher suites
    STRONG_CIPHERS = {
        'ECDHE', 'DHE', 'AES256', 'AES128', 'CHACHA20', 'GCM', 'SHA256', 'SHA384'
    }

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.results = {}

    def check_certificate(self, host: str, port: int = 443) -> Dict:
        """Check SSL certificate and configuration."""
        results = {
            'host': host,
            'port': port,
            'timestamp': datetime.now().isoformat(),
            'certificate': {},
            'protocol': {},
            'cipher': {},
            'issues': [],
            'score': 100
        }

        try:
            # Create SSL context
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            # Connect and get certificate
            with socket.create_connection((host, port), timeout=self.timeout) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert(binary_form=True)
                    cert_dict = ssl.DER_cert_to_PEM_cert(cert)

                    # Get cipher info
                    cipher = ssock.cipher()
                    protocol = ssock.version()

                    # Parse certificate
                    x509 = ssl._ssl._test_decode_cert(cert)

                    results['certificate'] = self.parse_certificate(x509, cert)
                    results['protocol'] = {
                        'version': protocol,
                        'secure': self.is_protocol_secure(protocol)
                    }
                    results['cipher'] = {
                        'name': cipher[0],
                        'version': cipher[1],
                        'bits': cipher[2],
                        'secure': self.is_cipher_secure(cipher[0])
                    }

        except ssl.SSLError as e:
            results['issues'].append(f"SSL Error: {str(e)}")
            results['score'] -= 50
        except socket.error as e:
            results['issues'].append(f"Connection Error: {str(e)}")
            results['score'] = 0
            return results
        except Exception as e:
            results['issues'].append(f"Error: {str(e)}")
            results['score'] -= 30

        # Analyze results
        self.analyze_security(results)
        self.results = results
        return results

    def parse_certificate(self, cert_dict: Dict, cert_der: bytes) -> Dict:
        """Parse certificate information."""
        cert_info = {
            'subject': {},
            'issuer': {},
            'serial': '',
            'not_before': '',
            'not_after': '',
            'fingerprints': {},
            'san': [],
            'key_usage': [],
            'is_valid': True,
            'days_remaining': 0
        }

        # Subject
        if 'subject' in cert_dict:
            for item in cert_dict['subject']:
                for key, value in item:
                    cert_info['subject'][key] = value

        # Issuer
        if 'issuer' in cert_dict:
            for item in cert_dict['issuer']:
                for key, value in item:
                    cert_info['issuer'][key] = value

        # Serial number
        cert_info['serial'] = cert_dict.get('serialNumber', '')

        # Validity dates
        if 'notBefore' in cert_dict:
            cert_info['not_before'] = cert_dict['notBefore']
        if 'notAfter' in cert_dict:
            cert_info['not_after'] = cert_dict['notAfter']
            try:
                expiry = datetime.strptime(cert_dict['notAfter'], '%b %d %H:%M:%S %Y %Z')
                cert_info['days_remaining'] = (expiry - datetime.utcnow()).days
                cert_info['is_valid'] = cert_info['days_remaining'] > 0
            except ValueError:
                pass

        # Subject Alternative Names
        if 'subjectAltName' in cert_dict:
            cert_info['san'] = [name for type_, name in cert_dict['subjectAltName']]

        # Fingerprints
        cert_info['fingerprints'] = {
            'sha256': hashlib.sha256(cert_der).hexdigest(),
            'sha1': hashlib.sha1(cert_der).hexdigest()
        }

        return cert_info

    def is_protocol_secure(self, protocol: str) -> bool:
        """Check if protocol version is secure."""
        insecure = {'SSLv2', 'SSLv3', 'TLSv1', 'TLSv1.0', 'TLSv1.1'}
        return protocol not in insecure

    def is_cipher_secure(self, cipher_name: str) -> bool:
        """Check if cipher suite is secure."""
        cipher_upper = cipher_name.upper()
        for weak in self.WEAK_CIPHERS:
            if weak in cipher_upper:
                return False
        return True

    def analyze_security(self, results: Dict):
        """Analyze security and generate issues."""
        cert = results['certificate']
        protocol = results['protocol']
        cipher = results['cipher']

        # Check certificate validity
        if not cert.get('is_valid', False):
            results['issues'].append("CRITICAL: Certificate has expired")
            results['score'] -= 40

        # Check days remaining
        days = cert.get('days_remaining', 0)
        if days < 0:
            results['issues'].append(f"CRITICAL: Certificate expired {abs(days)} days ago")
        elif days < 7:
            results['issues'].append(f"CRITICAL: Certificate expires in {days} days")
            results['score'] -= 30
        elif days < 30:
            results['issues'].append(f"WARNING: Certificate expires in {days} days")
            results['score'] -= 15
        elif days < 90:
            results['issues'].append(f"INFO: Certificate expires in {days} days")
            results['score'] -= 5

        # Check protocol
        if not protocol.get('secure', False):
            results['issues'].append(f"HIGH: Insecure protocol version: {protocol.get('version', 'Unknown')}")
            results['score'] -= 25

        # Check cipher
        if not cipher.get('secure', False):
            results['issues'].append(f"HIGH: Weak cipher suite: {cipher.get('name', 'Unknown')}")
            results['score'] -= 20

        # Check key size
        bits = cipher.get('bits', 0)
        if bits < 128:
            results['issues'].append(f"CRITICAL: Very weak key size: {bits} bits")
            results['score'] -= 30
        elif bits < 256:
            results['issues'].append(f"WARNING: Consider using 256-bit encryption")
            results['score'] -= 5

        # Check for self-signed
        subject = cert.get('subject', {})
        issuer = cert.get('issuer', {})
        if subject.get('commonName') == issuer.get('commonName'):
            results['issues'].append("WARNING: Self-signed certificate detected")
            results['score'] -= 10

        # Ensure score doesn't go below 0
        results['score'] = max(0, results['score'])

    def check_protocol_support(self, host: str, port: int = 443) -> Dict:
        """Check which SSL/TLS protocols are supported."""
        protocols = {
            'SSLv2': ssl.PROTOCOL_SSLv23,
            'SSLv3': ssl.PROTOCOL_SSLv23,
            'TLSv1': ssl.PROTOCOL_TLSv1 if hasattr(ssl, 'PROTOCOL_TLSv1') else None,
            'TLSv1.1': ssl.PROTOCOL_TLSv1_1 if hasattr(ssl, 'PROTOCOL_TLSv1_1') else None,
            'TLSv1.2': ssl.PROTOCOL_TLSv1_2 if hasattr(ssl, 'PROTOCOL_TLSv1_2') else None,
        }

        supported = {}

        for proto_name, proto_const in protocols.items():
            if proto_const is None:
                supported[proto_name] = 'Not available'
                continue

            try:
                context = ssl.SSLContext(proto_const)
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE

                with socket.create_connection((host, port), timeout=self.timeout) as sock:
                    with context.wrap_socket(sock, server_hostname=host) as ssock:
                        supported[proto_name] = True
            except ssl.SSLError:
                supported[proto_name] = False
            except Exception:
                supported[proto_name] = 'Error'

        return supported

    def print_report(self):
        """Print SSL check report."""
        results = self.results

        print("\n" + "=" * 70)
        print("SSL/TLS CERTIFICATE SECURITY REPORT")
        print("=" * 70)

        print(f"\nHost: {results['host']}:{results['port']}")
        print(f"Checked: {results['timestamp']}")
        print(f"Security Score: {results['score']}/100")

        # Certificate Info
        cert = results['certificate']
        print("\n" + "-" * 40)
        print("CERTIFICATE INFORMATION")
        print("-" * 40)

        if cert:
            print(f"\nSubject: {cert.get('subject', {}).get('commonName', 'N/A')}")
            print(f"Issuer: {cert.get('issuer', {}).get('organizationName', 'N/A')}")
            print(f"Serial: {cert.get('serial', 'N/A')}")
            print(f"Valid From: {cert.get('not_before', 'N/A')}")
            print(f"Valid Until: {cert.get('not_after', 'N/A')}")
            print(f"Days Remaining: {cert.get('days_remaining', 'N/A')}")

            if cert.get('san'):
                print(f"\nSubject Alt Names:")
                for san in cert['san'][:5]:
                    print(f"  • {san}")
                if len(cert['san']) > 5:
                    print(f"  ... and {len(cert['san']) - 5} more")

            print(f"\nSHA-256 Fingerprint:")
            print(f"  {cert.get('fingerprints', {}).get('sha256', 'N/A')}")

        # Protocol Info
        protocol = results['protocol']
        print("\n" + "-" * 40)
        print("PROTOCOL")
        print("-" * 40)
        status = "✓ Secure" if protocol.get('secure', False) else "✗ Insecure"
        print(f"\nVersion: {protocol.get('version', 'N/A')} ({status})")

        # Cipher Info
        cipher = results['cipher']
        print("\n" + "-" * 40)
        print("CIPHER SUITE")
        print("-" * 40)
        status = "✓ Secure" if cipher.get('secure', False) else "✗ Weak"
        print(f"\nCipher: {cipher.get('name', 'N/A')}")
        print(f"Bits: {cipher.get('bits', 'N/A')} ({status})")

        # Issues
        if results['issues']:
            print("\n" + "-" * 40)
            print("SECURITY ISSUES")
            print("-" * 40)
            for issue in results['issues']:
                print(f"\n• {issue}")

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
        elif score >= 60:
            rating = "C Needs Improvement"
        elif score >= 50:
            rating = "D Poor"
        else:
            rating = "F Critical Issues"

        print(f"\nRating: {rating}")

        print("\n" + "=" * 70)

        return 0 if score >= 70 else 1


def main():
    parser = argparse.ArgumentParser(
        description='Check SSL/TLS certificate security'
    )
    parser.add_argument(
        'host',
        help='Host to check (hostname or IP)'
    )
    parser.add_argument(
        '-p', '--port',
        type=int,
        default=443,
        help='Port number (default: 443)'
    )
    parser.add_argument(
        '-t', '--timeout',
        type=float,
        default=10.0,
        help='Connection timeout in seconds (default: 10.0)'
    )
    parser.add_argument(
        '--protocols',
        action='store_true',
        help='Check supported SSL/TLS protocols'
    )

    args = parser.parse_args()
    checker = SSLChecker(timeout=args.timeout)

    checker.check_certificate(args.host, args.port)
    exit_code = checker.print_report()

    if args.protocols:
        print("\n" + "-" * 40)
        print("PROTOCOL SUPPORT")
        print("-" * 40)
        supported = checker.check_protocol_support(args.host, args.port)
        for proto, status in supported.items():
            if status is True:
                print(f"  {proto}: ✓ Supported")
            elif status is False:
                print(f"  {proto}: ✗ Not supported")
            else:
                print(f"  {proto}: {status}")

    return exit_code


if __name__ == '__main__':
    exit(main())
