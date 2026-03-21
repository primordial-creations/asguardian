#!/usr/bin/env python3
"""
Encryption Analyzer
Analyzes encryption strength and identifies weak cryptographic implementations.
"""

import re
import os
import argparse
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class CryptoIssue:
    """Represents a cryptographic security issue."""
    file_path: str
    line_number: int
    severity: str
    issue_type: str
    code_snippet: str
    description: str
    recommendation: str


class EncryptionAnalyzer:
    """Analyzes code for weak encryption practices."""

    WEAK_CRYPTO_PATTERNS = {
        'python': [
            {
                'pattern': r'hashlib\.md5\s*\(',
                'severity': 'HIGH',
                'type': 'weak_hash_md5',
                'description': 'MD5 is cryptographically broken',
                'recommendation': 'Use SHA-256 or SHA-3 for hashing'
            },
            {
                'pattern': r'hashlib\.sha1\s*\(',
                'severity': 'MEDIUM',
                'type': 'weak_hash_sha1',
                'description': 'SHA-1 is deprecated for security use',
                'recommendation': 'Use SHA-256 or SHA-3'
            },
            {
                'pattern': r'DES\.new\s*\(|from Crypto\.Cipher import DES',
                'severity': 'CRITICAL',
                'type': 'weak_cipher_des',
                'description': 'DES is insecure (56-bit key)',
                'recommendation': 'Use AES-256-GCM'
            },
            {
                'pattern': r'Blowfish\.new\s*\(',
                'severity': 'MEDIUM',
                'type': 'weak_cipher_blowfish',
                'description': 'Blowfish has 64-bit block size vulnerability',
                'recommendation': 'Use AES-256-GCM'
            },
            {
                'pattern': r'AES\.MODE_ECB',
                'severity': 'HIGH',
                'type': 'ecb_mode',
                'description': 'ECB mode leaks patterns in encrypted data',
                'recommendation': 'Use AES-GCM or AES-CBC with HMAC'
            },
            {
                'pattern': r'random\.random\s*\(|random\.randint\s*\(',
                'severity': 'HIGH',
                'type': 'weak_random',
                'description': 'Predictable random for cryptographic use',
                'recommendation': 'Use secrets module or os.urandom()'
            },
            {
                'pattern': r'RC4|ARC4',
                'severity': 'CRITICAL',
                'type': 'weak_cipher_rc4',
                'description': 'RC4 is completely broken',
                'recommendation': 'Use AES-256-GCM'
            },
            {
                'pattern': r'RSA.*1024|rsa.*1024',
                'severity': 'HIGH',
                'type': 'weak_rsa_key',
                'description': 'RSA-1024 is too weak',
                'recommendation': 'Use RSA-2048 or higher, or ECC'
            },
            {
                'pattern': r'PBKDF2.*iterations\s*=\s*[0-9]{1,4}[^0-9]',
                'severity': 'HIGH',
                'type': 'low_pbkdf2_iterations',
                'description': 'PBKDF2 iterations too low',
                'recommendation': 'Use at least 100,000 iterations'
            }
        ],
        'javascript': [
            {
                'pattern': r'createHash\s*\(\s*[\'"]md5[\'"]\s*\)',
                'severity': 'HIGH',
                'type': 'weak_hash_md5',
                'description': 'MD5 is cryptographically broken',
                'recommendation': 'Use SHA-256 or SHA-3'
            },
            {
                'pattern': r'createHash\s*\(\s*[\'"]sha1[\'"]\s*\)',
                'severity': 'MEDIUM',
                'type': 'weak_hash_sha1',
                'description': 'SHA-1 is deprecated for security use',
                'recommendation': 'Use SHA-256 or SHA-3'
            },
            {
                'pattern': r'createCipher\s*\(',
                'severity': 'HIGH',
                'type': 'deprecated_cipher',
                'description': 'createCipher is deprecated (derives key with MD5)',
                'recommendation': 'Use createCipheriv with proper key derivation'
            },
            {
                'pattern': r'Math\.random\s*\(',
                'severity': 'HIGH',
                'type': 'weak_random',
                'description': 'Math.random() is not cryptographically secure',
                'recommendation': 'Use crypto.randomBytes() or crypto.getRandomValues()'
            },
            {
                'pattern': r'[\'"]des[\'"]|[\'"]des-ede[\'"]',
                'severity': 'CRITICAL',
                'type': 'weak_cipher_des',
                'description': 'DES/3DES are insecure',
                'recommendation': 'Use aes-256-gcm'
            },
            {
                'pattern': r'[\'"]rc4[\'"]|[\'"]rc2[\'"]',
                'severity': 'CRITICAL',
                'type': 'weak_cipher_rc4',
                'description': 'RC4/RC2 are broken stream ciphers',
                'recommendation': 'Use aes-256-gcm'
            },
            {
                'pattern': r'aes-[0-9]+-ecb',
                'severity': 'HIGH',
                'type': 'ecb_mode',
                'description': 'ECB mode leaks patterns',
                'recommendation': 'Use aes-256-gcm'
            },
            {
                'pattern': r'Buffer\.from\s*\([^)]+,\s*[\'"]hex[\'"]\s*\)',
                'severity': 'LOW',
                'type': 'potential_hardcoded_key',
                'description': 'Potential hardcoded cryptographic key',
                'recommendation': 'Use environment variables or key management'
            }
        ],
        'java': [
            {
                'pattern': r'MessageDigest\.getInstance\s*\(\s*"MD5"\s*\)',
                'severity': 'HIGH',
                'type': 'weak_hash_md5',
                'description': 'MD5 is cryptographically broken',
                'recommendation': 'Use SHA-256 or SHA-3'
            },
            {
                'pattern': r'MessageDigest\.getInstance\s*\(\s*"SHA-?1"\s*\)',
                'severity': 'MEDIUM',
                'type': 'weak_hash_sha1',
                'description': 'SHA-1 is deprecated',
                'recommendation': 'Use SHA-256 or SHA-3'
            },
            {
                'pattern': r'Cipher\.getInstance\s*\(\s*"DES',
                'severity': 'CRITICAL',
                'type': 'weak_cipher_des',
                'description': 'DES is insecure',
                'recommendation': 'Use AES/GCM/NoPadding'
            },
            {
                'pattern': r'Cipher\.getInstance\s*\(\s*"AES/ECB',
                'severity': 'HIGH',
                'type': 'ecb_mode',
                'description': 'ECB mode leaks patterns',
                'recommendation': 'Use AES/GCM/NoPadding'
            },
            {
                'pattern': r'new Random\s*\(',
                'severity': 'HIGH',
                'type': 'weak_random',
                'description': 'java.util.Random is predictable',
                'recommendation': 'Use SecureRandom'
            },
            {
                'pattern': r'KeyGenerator.*128',
                'severity': 'MEDIUM',
                'type': 'short_key',
                'description': 'Consider using 256-bit keys',
                'recommendation': 'Use 256-bit AES keys for sensitive data'
            },
            {
                'pattern': r'NullCipher',
                'severity': 'CRITICAL',
                'type': 'null_cipher',
                'description': 'NullCipher provides no encryption',
                'recommendation': 'Use proper encryption algorithm'
            }
        ],
        'php': [
            {
                'pattern': r'md5\s*\(',
                'severity': 'HIGH',
                'type': 'weak_hash_md5',
                'description': 'MD5 is cryptographically broken',
                'recommendation': 'Use password_hash() or hash("sha256", ...)'
            },
            {
                'pattern': r'sha1\s*\(',
                'severity': 'MEDIUM',
                'type': 'weak_hash_sha1',
                'description': 'SHA-1 is deprecated',
                'recommendation': 'Use hash("sha256", ...)'
            },
            {
                'pattern': r'mcrypt_',
                'severity': 'HIGH',
                'type': 'deprecated_mcrypt',
                'description': 'mcrypt is deprecated and removed in PHP 7.2+',
                'recommendation': 'Use openssl_encrypt() with AES-256-GCM'
            },
            {
                'pattern': r'rand\s*\(|mt_rand\s*\(',
                'severity': 'HIGH',
                'type': 'weak_random',
                'description': 'rand/mt_rand are not cryptographically secure',
                'recommendation': 'Use random_bytes() or random_int()'
            },
            {
                'pattern': r'MCRYPT_DES|MCRYPT_3DES',
                'severity': 'CRITICAL',
                'type': 'weak_cipher_des',
                'description': 'DES/3DES are insecure',
                'recommendation': 'Use AES-256-GCM'
            },
            {
                'pattern': r'MCRYPT_MODE_ECB',
                'severity': 'HIGH',
                'type': 'ecb_mode',
                'description': 'ECB mode leaks patterns',
                'recommendation': 'Use GCM or CBC mode with HMAC'
            }
        ],
        'csharp': [
            {
                'pattern': r'MD5\.Create\s*\(',
                'severity': 'HIGH',
                'type': 'weak_hash_md5',
                'description': 'MD5 is cryptographically broken',
                'recommendation': 'Use SHA256 or SHA512'
            },
            {
                'pattern': r'SHA1\.Create\s*\(',
                'severity': 'MEDIUM',
                'type': 'weak_hash_sha1',
                'description': 'SHA-1 is deprecated',
                'recommendation': 'Use SHA256 or SHA512'
            },
            {
                'pattern': r'DESCryptoServiceProvider|TripleDESCryptoServiceProvider',
                'severity': 'CRITICAL',
                'type': 'weak_cipher_des',
                'description': 'DES/3DES are insecure',
                'recommendation': 'Use AesGcm or AesCryptoServiceProvider'
            },
            {
                'pattern': r'CipherMode\.ECB',
                'severity': 'HIGH',
                'type': 'ecb_mode',
                'description': 'ECB mode leaks patterns',
                'recommendation': 'Use AesGcm'
            },
            {
                'pattern': r'new Random\s*\(',
                'severity': 'HIGH',
                'type': 'weak_random',
                'description': 'System.Random is predictable',
                'recommendation': 'Use RandomNumberGenerator'
            }
        ]
    }

    def __init__(self):
        self.issues: List[CryptoIssue] = []
        self.files_scanned = 0
        self.compiled_patterns = {}

        # Pre-compile patterns
        for lang, patterns in self.WEAK_CRYPTO_PATTERNS.items():
            self.compiled_patterns[lang] = []
            for p in patterns:
                try:
                    self.compiled_patterns[lang].append({
                        'regex': re.compile(p['pattern'], re.IGNORECASE),
                        **p
                    })
                except re.error:
                    pass

    def get_language(self, file_path: Path) -> str:
        """Determine language from file extension."""
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'javascript',
            '.jsx': 'javascript',
            '.tsx': 'javascript',
            '.java': 'java',
            '.php': 'php',
            '.cs': 'csharp'
        }
        return ext_map.get(file_path.suffix.lower(), '')

    def scan_file(self, file_path: Path) -> List[CryptoIssue]:
        """Scan a single file for weak crypto."""
        issues = []
        language = self.get_language(file_path)

        if not language or language not in self.compiled_patterns:
            return issues

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except (IOError, OSError):
            return issues

        self.files_scanned += 1

        for line_num, line in enumerate(lines, 1):
            for pattern_config in self.compiled_patterns[language]:
                if pattern_config['regex'].search(line):
                    issue = CryptoIssue(
                        file_path=str(file_path),
                        line_number=line_num,
                        severity=pattern_config['severity'],
                        issue_type=pattern_config['type'],
                        code_snippet=line.strip()[:100],
                        description=pattern_config['description'],
                        recommendation=pattern_config['recommendation']
                    )
                    issues.append(issue)

        return issues

    def scan_directory(self, directory: Path, recursive: bool = True) -> List[CryptoIssue]:
        """Scan directory for weak crypto."""
        all_issues = []
        skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'vendor', 'dist', 'build'}

        if recursive:
            for root, dirs, files in os.walk(directory):
                dirs[:] = [d for d in dirs if d not in skip_dirs]

                for file in files:
                    file_path = Path(root) / file
                    issues = self.scan_file(file_path)
                    all_issues.extend(issues)
        else:
            for item in directory.iterdir():
                if item.is_file():
                    issues = self.scan_file(item)
                    all_issues.extend(issues)

        self.issues = all_issues
        return all_issues

    def get_summary(self) -> Dict:
        """Get summary of findings."""
        summary = {
            'total_issues': len(self.issues),
            'files_scanned': self.files_scanned,
            'by_severity': {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0},
            'by_type': {}
        }

        for issue in self.issues:
            summary['by_severity'][issue.severity] += 1
            if issue.issue_type not in summary['by_type']:
                summary['by_type'][issue.issue_type] = 0
            summary['by_type'][issue.issue_type] += 1

        return summary

    def print_report(self):
        """Print scan report."""
        summary = self.get_summary()

        print("\n" + "=" * 70)
        print("ENCRYPTION ANALYSIS REPORT")
        print("=" * 70)

        print(f"\nFiles Scanned: {summary['files_scanned']}")
        print(f"Total Issues: {summary['total_issues']}")

        if summary['total_issues'] > 0:
            print("\nIssues by Severity:")
            for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
                count = summary['by_severity'][severity]
                if count > 0:
                    print(f"  {severity}: {count}")

            print("\n" + "-" * 70)
            print("WEAK CRYPTOGRAPHY FOUND")
            print("-" * 70)

            severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
            sorted_issues = sorted(self.issues, key=lambda x: severity_order[x.severity])

            for issue in sorted_issues:
                print(f"\n[{issue.severity}] {issue.file_path}:{issue.line_number}")
                print(f"  Type: {issue.issue_type}")
                print(f"  Code: {issue.code_snippet}")
                print(f"  Issue: {issue.description}")
                print(f"  Fix: {issue.recommendation}")
        else:
            print("\n✓ No weak cryptography detected!")

        print("\n" + "=" * 70)

        if summary['by_severity']['CRITICAL'] > 0:
            return 2
        elif summary['by_severity']['HIGH'] > 0:
            return 1
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Analyze code for weak encryption practices'
    )
    parser.add_argument(
        'path',
        nargs='?',
        default='.',
        help='File or directory to scan (default: current directory)'
    )
    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        default=True,
        help='Scan directories recursively (default: True)'
    )
    parser.add_argument(
        '--no-recursive',
        action='store_true',
        help='Do not scan directories recursively'
    )

    args = parser.parse_args()
    analyzer = EncryptionAnalyzer()

    target = Path(args.path)

    if not target.exists():
        print(f"Error: Path not found: {args.path}")
        return 1

    print(f"Analyzing encryption: {target.absolute()}")

    if target.is_file():
        analyzer.scan_file(target)
    else:
        recursive = not args.no_recursive
        analyzer.scan_directory(target, recursive=recursive)

    return analyzer.print_report()


if __name__ == '__main__':
    exit(main())
