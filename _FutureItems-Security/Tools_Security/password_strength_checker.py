#!/usr/bin/env python3
"""
Password Strength Checker
Analyzes password strength based on multiple security criteria.
"""

import re
import math
import hashlib
import argparse
from typing import Dict, List, Tuple
from pathlib import Path


class PasswordStrengthChecker:
    """Comprehensive password strength analyzer."""

    # Common weak passwords (subset for checking)
    COMMON_PASSWORDS = {
        'password', '123456', '12345678', 'qwerty', 'abc123', 'monkey', 'master',
        'dragon', '111111', 'baseball', 'iloveyou', 'trustno1', 'sunshine', 'princess',
        'admin', 'welcome', 'shadow', 'password1', 'superman', 'michael', 'football',
        'letmein', '123456789', 'password123', 'passw0rd', 'qwerty123', 'admin123'
    }

    # Common keyboard patterns
    KEYBOARD_PATTERNS = [
        'qwerty', 'asdf', 'zxcv', 'qazwsx', '1234', '0987', 'poiu', 'lkjh'
    ]

    def __init__(self):
        self.results = {}

    def calculate_entropy(self, password: str) -> float:
        """Calculate password entropy in bits."""
        charset_size = 0

        if re.search(r'[a-z]', password):
            charset_size += 26
        if re.search(r'[A-Z]', password):
            charset_size += 26
        if re.search(r'[0-9]', password):
            charset_size += 10
        if re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]', password):
            charset_size += 32
        if re.search(r'\s', password):
            charset_size += 1

        if charset_size == 0:
            return 0

        entropy = len(password) * math.log2(charset_size)
        return round(entropy, 2)

    def check_length(self, password: str) -> Tuple[int, str]:
        """Check password length."""
        length = len(password)
        if length >= 16:
            return 25, "Excellent length (16+ characters)"
        elif length >= 12:
            return 20, "Good length (12-15 characters)"
        elif length >= 8:
            return 10, "Minimum acceptable length (8-11 characters)"
        else:
            return 0, "Too short (less than 8 characters)"

    def check_character_variety(self, password: str) -> Tuple[int, List[str]]:
        """Check for character variety."""
        score = 0
        findings = []

        if re.search(r'[a-z]', password):
            score += 5
            findings.append("✓ Contains lowercase letters")
        else:
            findings.append("✗ Missing lowercase letters")

        if re.search(r'[A-Z]', password):
            score += 5
            findings.append("✓ Contains uppercase letters")
        else:
            findings.append("✗ Missing uppercase letters")

        if re.search(r'[0-9]', password):
            score += 5
            findings.append("✓ Contains numbers")
        else:
            findings.append("✗ Missing numbers")

        if re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]', password):
            score += 10
            findings.append("✓ Contains special characters")
        else:
            findings.append("✗ Missing special characters")

        return score, findings

    def check_patterns(self, password: str) -> Tuple[int, List[str]]:
        """Check for weak patterns."""
        score = 25  # Start with full points, deduct for patterns
        findings = []
        lower_pass = password.lower()

        # Check for common passwords
        if lower_pass in self.COMMON_PASSWORDS:
            score -= 25
            findings.append("✗ Password is in common password list")

        # Check for keyboard patterns
        for pattern in self.KEYBOARD_PATTERNS:
            if pattern in lower_pass:
                score -= 5
                findings.append(f"✗ Contains keyboard pattern: {pattern}")
                break

        # Check for repeated characters
        if re.search(r'(.)\1{2,}', password):
            score -= 5
            findings.append("✗ Contains repeated characters (3+)")

        # Check for sequential numbers
        if re.search(r'(012|123|234|345|456|567|678|789|890)', password):
            score -= 5
            findings.append("✗ Contains sequential numbers")

        # Check for sequential letters
        if re.search(r'(abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz)', lower_pass):
            score -= 5
            findings.append("✗ Contains sequential letters")

        if not findings:
            findings.append("✓ No common patterns detected")

        return max(0, score), findings

    def check_dictionary_words(self, password: str) -> Tuple[int, List[str]]:
        """Check for dictionary words (simplified check)."""
        score = 15
        findings = []
        lower_pass = password.lower()

        # Common words to check
        common_words = [
            'password', 'admin', 'user', 'login', 'welcome', 'hello',
            'test', 'root', 'master', 'guest', 'default', 'system'
        ]

        for word in common_words:
            if word in lower_pass:
                score -= 5
                findings.append(f"✗ Contains common word: {word}")

        if not findings:
            findings.append("✓ No common dictionary words detected")

        return max(0, score), findings

    def analyze_password(self, password: str) -> Dict:
        """Perform comprehensive password analysis."""
        results = {
            'password_length': len(password),
            'entropy_bits': self.calculate_entropy(password),
            'checks': {},
            'total_score': 0,
            'max_score': 100,
            'strength': '',
            'recommendations': []
        }

        # Run all checks
        length_score, length_msg = self.check_length(password)
        results['checks']['length'] = {'score': length_score, 'max': 25, 'details': [length_msg]}

        variety_score, variety_findings = self.check_character_variety(password)
        results['checks']['character_variety'] = {'score': variety_score, 'max': 25, 'details': variety_findings}

        pattern_score, pattern_findings = self.check_patterns(password)
        results['checks']['patterns'] = {'score': pattern_score, 'max': 25, 'details': pattern_findings}

        dict_score, dict_findings = self.check_dictionary_words(password)
        results['checks']['dictionary'] = {'score': dict_score, 'max': 15, 'details': dict_findings}

        # Calculate total score
        results['total_score'] = sum(check['score'] for check in results['checks'].values())

        # Determine strength rating
        score = results['total_score']
        if score >= 90:
            results['strength'] = 'EXCELLENT'
        elif score >= 70:
            results['strength'] = 'STRONG'
        elif score >= 50:
            results['strength'] = 'MODERATE'
        elif score >= 30:
            results['strength'] = 'WEAK'
        else:
            results['strength'] = 'VERY WEAK'

        # Generate recommendations
        if length_score < 20:
            results['recommendations'].append("Increase password length to at least 12 characters")
        if variety_score < 20:
            results['recommendations'].append("Add more character types (uppercase, lowercase, numbers, symbols)")
        if pattern_score < 20:
            results['recommendations'].append("Avoid common patterns and sequences")
        if dict_score < 10:
            results['recommendations'].append("Avoid using common dictionary words")
        if results['entropy_bits'] < 60:
            results['recommendations'].append("Increase password complexity for better entropy")

        return results

    def check_breach_hash(self, password: str) -> str:
        """Generate SHA-1 hash for checking against breach databases."""
        sha1_hash = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
        return sha1_hash

    def print_report(self, results: Dict):
        """Print a formatted password analysis report."""
        print("\n" + "=" * 60)
        print("PASSWORD STRENGTH ANALYSIS REPORT")
        print("=" * 60)

        print(f"\nPassword Length: {results['password_length']} characters")
        print(f"Entropy: {results['entropy_bits']} bits")
        print(f"Overall Score: {results['total_score']}/{results['max_score']}")
        print(f"Strength Rating: {results['strength']}")

        print("\n" + "-" * 40)
        print("DETAILED ANALYSIS")
        print("-" * 40)

        for check_name, check_data in results['checks'].items():
            print(f"\n{check_name.replace('_', ' ').title()}:")
            print(f"  Score: {check_data['score']}/{check_data['max']}")
            for detail in check_data['details']:
                print(f"  {detail}")

        if results['recommendations']:
            print("\n" + "-" * 40)
            print("RECOMMENDATIONS")
            print("-" * 40)
            for i, rec in enumerate(results['recommendations'], 1):
                print(f"{i}. {rec}")

        print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Analyze password strength and security'
    )
    parser.add_argument(
        '-p', '--password',
        help='Password to analyze (will prompt if not provided)'
    )
    parser.add_argument(
        '-f', '--file',
        help='File containing passwords to analyze (one per line)'
    )
    parser.add_argument(
        '--hash',
        action='store_true',
        help='Show SHA-1 hash for breach database checking'
    )

    args = parser.parse_args()
    checker = PasswordStrengthChecker()

    passwords = []

    if args.file:
        file_path = Path(args.file)
        if file_path.exists():
            with open(file_path) as f:
                passwords = [line.strip() for line in f if line.strip()]
        else:
            print(f"Error: File not found: {args.file}")
            return
    elif args.password:
        passwords = [args.password]
    else:
        import getpass
        password = getpass.getpass("Enter password to analyze: ")
        passwords = [password]

    for password in passwords:
        results = checker.analyze_password(password)
        checker.print_report(results)

        if args.hash:
            sha1_hash = checker.check_breach_hash(password)
            print(f"\nSHA-1 Hash (for breach checking): {sha1_hash}")
            print("Use first 5 characters to query haveibeenpwned.com API")
            print(f"Query prefix: {sha1_hash[:5]}")


if __name__ == '__main__':
    main()
