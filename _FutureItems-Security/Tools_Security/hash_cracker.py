#!/usr/bin/env python3
"""
Hash Identifier and Analyzer
Identifies hash types and tests against common password lists.
"""

import hashlib
import re
import argparse
from pathlib import Path
from typing import Dict, List, Optional


class HashAnalyzer:
    """Identifies and analyzes password hashes."""

    # Hash patterns and their properties
    HASH_PATTERNS = {
        'MD5': {
            'regex': r'^[a-f0-9]{32}$',
            'length': 32,
            'algorithm': 'md5',
            'secure': False,
            'description': 'MD5 - Cryptographically broken'
        },
        'SHA-1': {
            'regex': r'^[a-f0-9]{40}$',
            'length': 40,
            'algorithm': 'sha1',
            'secure': False,
            'description': 'SHA-1 - Deprecated for security use'
        },
        'SHA-256': {
            'regex': r'^[a-f0-9]{64}$',
            'length': 64,
            'algorithm': 'sha256',
            'secure': True,
            'description': 'SHA-256 - Secure for general use'
        },
        'SHA-512': {
            'regex': r'^[a-f0-9]{128}$',
            'length': 128,
            'algorithm': 'sha512',
            'secure': True,
            'description': 'SHA-512 - Secure for general use'
        },
        'SHA-384': {
            'regex': r'^[a-f0-9]{96}$',
            'length': 96,
            'algorithm': 'sha384',
            'secure': True,
            'description': 'SHA-384 - Secure for general use'
        },
        'NTLM': {
            'regex': r'^[a-f0-9]{32}$',
            'length': 32,
            'algorithm': None,
            'secure': False,
            'description': 'NTLM - Windows password hash (weak)'
        },
        'MySQL 5.x': {
            'regex': r'^\*[A-F0-9]{40}$',
            'length': 41,
            'algorithm': None,
            'secure': False,
            'description': 'MySQL 5.x - Database password hash'
        },
        'bcrypt': {
            'regex': r'^\$2[aby]?\$[0-9]{2}\$[./A-Za-z0-9]{53}$',
            'length': 60,
            'algorithm': None,
            'secure': True,
            'description': 'bcrypt - Secure password hashing'
        },
        'Argon2': {
            'regex': r'^\$argon2(?:i|d|id)\$',
            'length': None,
            'algorithm': None,
            'secure': True,
            'description': 'Argon2 - Modern secure password hashing'
        },
        'scrypt': {
            'regex': r'^\$scrypt\$',
            'length': None,
            'algorithm': None,
            'secure': True,
            'description': 'scrypt - Memory-hard password hashing'
        },
        'SHA-256 Crypt': {
            'regex': r'^\$5\$',
            'length': None,
            'algorithm': None,
            'secure': True,
            'description': 'SHA-256 Crypt - Unix password hash'
        },
        'SHA-512 Crypt': {
            'regex': r'^\$6\$',
            'length': None,
            'algorithm': None,
            'secure': True,
            'description': 'SHA-512 Crypt - Unix password hash'
        }
    }

    # Common passwords for testing (educational purposes)
    COMMON_PASSWORDS = [
        'password', '123456', '12345678', 'qwerty', 'abc123', 'monkey', 'master',
        'dragon', '111111', 'baseball', 'iloveyou', 'trustno1', 'sunshine',
        'princess', 'admin', 'welcome', 'shadow', 'password1', 'superman',
        'michael', 'football', 'letmein', '123456789', 'password123', 'passw0rd',
        'qwerty123', 'admin123', 'root', 'toor', 'test', 'guest', 'master123',
        '1234', '12345', '123', 'password1234', 'qwerty1234', '1q2w3e4r',
        'default', 'hello', 'love', 'secret', 'changeme', 'pass', '1qaz2wsx'
    ]

    def __init__(self):
        self.results = {}

    def identify_hash(self, hash_value: str) -> List[Dict]:
        """Identify possible hash types."""
        hash_value = hash_value.strip()
        possible_types = []

        for hash_type, config in self.HASH_PATTERNS.items():
            if re.match(config['regex'], hash_value, re.IGNORECASE):
                possible_types.append({
                    'type': hash_type,
                    'secure': config['secure'],
                    'description': config['description'],
                    'algorithm': config['algorithm']
                })

        return possible_types

    def test_common_passwords(self, hash_value: str, hash_types: List[Dict]) -> Optional[str]:
        """Test hash against common passwords."""
        hash_value = hash_value.lower().strip()

        for hash_info in hash_types:
            algorithm = hash_info.get('algorithm')
            if not algorithm:
                continue

            for password in self.COMMON_PASSWORDS:
                try:
                    computed = hashlib.new(algorithm, password.encode()).hexdigest()
                    if computed == hash_value:
                        return password
                except ValueError:
                    pass

        return None

    def analyze_hash(self, hash_value: str) -> Dict:
        """Perform comprehensive hash analysis."""
        hash_value = hash_value.strip()

        results = {
            'hash': hash_value,
            'length': len(hash_value),
            'possible_types': [],
            'cracked': None,
            'recommendations': []
        }

        # Identify hash types
        results['possible_types'] = self.identify_hash(hash_value)

        if not results['possible_types']:
            results['possible_types'] = [{
                'type': 'Unknown',
                'secure': None,
                'description': 'Unable to identify hash type'
            }]
        else:
            # Test against common passwords
            results['cracked'] = self.test_common_passwords(hash_value, results['possible_types'])

            # Generate recommendations
            for hash_info in results['possible_types']:
                if not hash_info.get('secure', True):
                    if hash_info['type'] in ['MD5', 'SHA-1', 'NTLM']:
                        results['recommendations'].append(
                            f"Upgrade from {hash_info['type']} to bcrypt, Argon2, or scrypt for passwords"
                        )

            if results['cracked']:
                results['recommendations'].append(
                    f"Password was cracked! Use a stronger, unique password"
                )

        self.results = results
        return results

    def analyze_file(self, file_path: Path) -> List[Dict]:
        """Analyze hashes from a file."""
        all_results = []

        try:
            with open(file_path) as f:
                for line in f:
                    hash_value = line.strip()
                    if hash_value and not hash_value.startswith('#'):
                        result = self.analyze_hash(hash_value)
                        all_results.append(result)
        except IOError as e:
            print(f"Error reading file: {e}")

        return all_results

    def print_report(self, results: Dict = None):
        """Print analysis report."""
        if results is None:
            results = self.results

        print("\n" + "=" * 70)
        print("HASH ANALYSIS REPORT")
        print("=" * 70)

        print(f"\nHash: {results['hash']}")
        print(f"Length: {results['length']} characters")

        print("\n" + "-" * 40)
        print("IDENTIFIED TYPES")
        print("-" * 40)

        for hash_type in results['possible_types']:
            secure_status = "✓ Secure" if hash_type.get('secure') else "✗ Insecure" if hash_type.get('secure') is False else "? Unknown"
            print(f"\n{hash_type['type']} ({secure_status})")
            print(f"  {hash_type['description']}")

        if results['cracked']:
            print("\n" + "-" * 40)
            print("⚠️  HASH CRACKED")
            print("-" * 40)
            print(f"\nOriginal password: {results['cracked']}")
            print("This password was found in a common password list!")

        if results['recommendations']:
            print("\n" + "-" * 40)
            print("RECOMMENDATIONS")
            print("-" * 40)
            for rec in results['recommendations']:
                print(f"\n• {rec}")

        print("\n" + "=" * 70)

        return 1 if results['cracked'] else 0


def compute_hash(text: str, algorithm: str) -> str:
    """Compute hash of text."""
    try:
        return hashlib.new(algorithm, text.encode()).hexdigest()
    except ValueError as e:
        return f"Error: {e}"


def main():
    parser = argparse.ArgumentParser(
        description='Identify and analyze password hashes'
    )
    parser.add_argument(
        'hash',
        nargs='?',
        help='Hash value to analyze'
    )
    parser.add_argument(
        '-f', '--file',
        help='File containing hashes to analyze (one per line)'
    )
    parser.add_argument(
        '--compute',
        help='Compute hash of given text'
    )
    parser.add_argument(
        '-a', '--algorithm',
        default='sha256',
        help='Algorithm for --compute (default: sha256)'
    )

    args = parser.parse_args()
    analyzer = HashAnalyzer()

    if args.compute:
        print(f"\nComputing {args.algorithm} hash:")
        print(f"Input: {args.compute}")
        print(f"Hash: {compute_hash(args.compute, args.algorithm)}")
        return 0

    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: File not found: {args.file}")
            return 1

        results = analyzer.analyze_file(file_path)
        exit_code = 0
        for result in results:
            code = analyzer.print_report(result)
            if code > exit_code:
                exit_code = code
        return exit_code

    if args.hash:
        results = analyzer.analyze_hash(args.hash)
        return analyzer.print_report(results)

    # Interactive mode
    print("Enter hash to analyze (or 'q' to quit):")
    while True:
        try:
            hash_input = input("> ").strip()
            if hash_input.lower() == 'q':
                break
            if hash_input:
                results = analyzer.analyze_hash(hash_input)
                analyzer.print_report(results)
        except (EOFError, KeyboardInterrupt):
            break

    return 0


if __name__ == '__main__':
    exit(main())
