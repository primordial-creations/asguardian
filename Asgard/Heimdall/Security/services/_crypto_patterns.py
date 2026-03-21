"""
Heimdall Cryptographic Validation Patterns

Pattern definitions for detecting cryptographic issues.
"""

import re
from typing import List, Optional, Set

from Asgard.Heimdall.Security.models.security_models import SecuritySeverity


class CryptoPattern:
    """Defines a pattern for detecting cryptographic issues."""

    def __init__(
        self,
        name: str,
        pattern: str,
        severity: SecuritySeverity,
        issue_type: str,
        algorithm: str,
        description: str,
        recommendation: str,
        file_types: Optional[Set[str]] = None,
    ):
        self.name = name
        self.pattern = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
        self.severity = severity
        self.issue_type = issue_type
        self.algorithm = algorithm
        self.description = description
        self.recommendation = recommendation
        self.file_types = file_types or {".py", ".js", ".ts", ".java", ".go", ".rb", ".php"}


CRYPTO_PATTERNS: List[CryptoPattern] = [
    CryptoPattern(
        name="md5_hash",
        pattern=r"""(?:hashlib\.md5|MD5\.new|md5\(|createHash\(['""]md5['""]|MessageDigest\.getInstance\(['""]MD5['""])""",
        severity=SecuritySeverity.HIGH,
        issue_type="weak_hash",
        algorithm="MD5",
        description="MD5 is cryptographically broken and should not be used for security purposes.",
        recommendation="Use SHA-256 or SHA-3 for hashing. For passwords, use bcrypt, scrypt, or Argon2.",
    ),
    CryptoPattern(
        name="sha1_hash",
        pattern=r"""(?:hashlib\.sha1|SHA1\.new|sha1\(|createHash\(['""]sha1['""]|MessageDigest\.getInstance\(['""]SHA-?1['""])""",
        severity=SecuritySeverity.MEDIUM,
        issue_type="weak_hash",
        algorithm="SHA-1",
        description="SHA-1 is deprecated and vulnerable to collision attacks.",
        recommendation="Use SHA-256 or SHA-3 for hashing. For passwords, use bcrypt, scrypt, or Argon2.",
    ),
    CryptoPattern(
        name="des_encryption",
        pattern=r"""(?:DES\.new|DES3\.new|TripleDES|createCipheriv\(['""]des|Cipher\.getInstance\(['""]DES)""",
        severity=SecuritySeverity.HIGH,
        issue_type="weak_cipher",
        algorithm="DES/3DES",
        description="DES and 3DES are deprecated due to small block and key sizes.",
        recommendation="Use AES-256-GCM or ChaCha20-Poly1305 for symmetric encryption.",
    ),
    CryptoPattern(
        name="ecb_mode",
        pattern=r"""(?:MODE_ECB|AES\.MODE_ECB|mode\s*[:=]\s*['""]ECB['""]|createCipheriv\(['""]aes-\d+-ecb)""",
        severity=SecuritySeverity.HIGH,
        issue_type="insecure_mode",
        algorithm="ECB Mode",
        description="ECB mode leaks information about plaintext patterns.",
        recommendation="Use GCM, CCM, or CBC with HMAC for authenticated encryption.",
    ),
    CryptoPattern(
        name="static_iv",
        pattern=r"""(?:iv\s*=\s*['""][A-Za-z0-9+/=]{16,}['""]|IV\s*=\s*['""][A-Za-z0-9+/=]{16,}['""]|nonce\s*=\s*['""][^'"]+['""])""",
        severity=SecuritySeverity.HIGH,
        issue_type="static_iv",
        algorithm="Static IV/Nonce",
        description="Static IV or nonce reuse can compromise encryption security.",
        recommendation="Generate a random IV/nonce for each encryption operation.",
    ),
    CryptoPattern(
        name="hardcoded_key",
        pattern=r"""(?:(?:secret|encryption|aes|private)[_-]?key\s*=\s*['""][A-Za-z0-9+/=]{16,}['""])""",
        severity=SecuritySeverity.CRITICAL,
        issue_type="hardcoded_key",
        algorithm="Hardcoded Key",
        description="Cryptographic keys should never be hardcoded in source code.",
        recommendation="Store keys in environment variables, key vaults, or secure key management systems.",
    ),
    CryptoPattern(
        name="weak_random",
        pattern=r"""(?:random\.random\(\)|random\.randint|Math\.random\(\)|rand\(\)|mt_rand)(?![A-Za-z])""",
        severity=SecuritySeverity.MEDIUM,
        issue_type="insecure_random",
        algorithm="Weak PRNG",
        description="Standard random functions are not cryptographically secure.",
        recommendation="Use secrets module (Python), crypto.randomBytes (Node.js), or SecureRandom (Java).",
    ),
    CryptoPattern(
        name="rsa_small_key",
        pattern=r"""(?:RSA\.generate\(\s*(?:512|768|1024)|key_size\s*=\s*(?:512|768|1024)|RSAKeyGenParameterSpec\(\s*(?:512|768|1024))""",
        severity=SecuritySeverity.HIGH,
        issue_type="weak_key_size",
        algorithm="RSA",
        description="RSA key sizes below 2048 bits are considered insecure.",
        recommendation="Use RSA-2048 or higher. Consider using RSA-4096 for long-term security.",
    ),
    CryptoPattern(
        name="password_hash_sha",
        pattern=r"""(?:hashlib\.sha(?:256|512)\([^)]*password|SHA(?:256|512)\.new\([^)]*password|digest\([^)]*password)""",
        severity=SecuritySeverity.HIGH,
        issue_type="weak_password_hash",
        algorithm="SHA for passwords",
        description="Raw SHA hashes are too fast for password hashing and vulnerable to brute force.",
        recommendation="Use bcrypt, scrypt, Argon2, or PBKDF2 with high iteration count for passwords.",
    ),
    CryptoPattern(
        name="bcrypt_low_rounds",
        pattern=r"""(?:bcrypt\.hash(?:pw)?\([^)]*rounds?\s*=\s*[1-9](?!\d)|gensalt\(\s*[1-9](?!\d)|BCrypt\.hashpw\([^)]*\$2[ab]\$0[1-9])""",
        severity=SecuritySeverity.MEDIUM,
        issue_type="weak_work_factor",
        algorithm="bcrypt",
        description="Low bcrypt work factor makes passwords easier to crack.",
        recommendation="Use work factor of at least 12 for bcrypt.",
    ),
    CryptoPattern(
        name="ssl_verify_false",
        pattern=r"""(?:verify\s*=\s*False|CERT_NONE|SSL_VERIFY_NONE|verify_ssl\s*=\s*False|rejectUnauthorized\s*:\s*false)""",
        severity=SecuritySeverity.HIGH,
        issue_type="disabled_verification",
        algorithm="SSL/TLS",
        description="Disabling SSL certificate verification enables man-in-the-middle attacks.",
        recommendation="Always verify SSL certificates in production. Use proper CA certificates.",
    ),
    CryptoPattern(
        name="ssl_v2_v3",
        pattern=r"""(?:SSLv2|SSLv3|ssl\.PROTOCOL_SSLv2|ssl\.PROTOCOL_SSLv3|TLSv1[^.12])""",
        severity=SecuritySeverity.CRITICAL,
        issue_type="deprecated_protocol",
        algorithm="SSLv2/SSLv3/TLSv1.0",
        description="SSL 2.0, SSL 3.0, and TLS 1.0 have known vulnerabilities.",
        recommendation="Use TLS 1.2 or TLS 1.3 only. Disable all older protocols.",
    ),
    CryptoPattern(
        name="jwt_none_algorithm",
        pattern=r"""(?:algorithm\s*=\s*['""]none['""]|algorithms?\s*[=:]\s*\[['""]none['""])""",
        severity=SecuritySeverity.CRITICAL,
        issue_type="jwt_vulnerability",
        algorithm="JWT none",
        description="JWT 'none' algorithm bypasses signature verification entirely.",
        recommendation="Never allow 'none' algorithm. Explicitly specify allowed algorithms.",
    ),
    CryptoPattern(
        name="jwt_hs256_weak_secret",
        pattern=r"""(?:jwt\.(?:encode|sign)\([^)]*['""](?:secret|password|key)['""])""",
        severity=SecuritySeverity.MEDIUM,
        issue_type="weak_jwt_secret",
        algorithm="JWT HS256",
        description="JWT with predictable secret names may indicate weak secrets.",
        recommendation="Use cryptographically random secrets of at least 256 bits for JWT.",
    ),
    CryptoPattern(
        name="pbkdf2_low_iterations",
        pattern=r"""(?:PBKDF2|pbkdf2_hmac)\([^)]*iterations?\s*=\s*(?:[1-9]\d{0,3}|10000)(?!\d)""",
        severity=SecuritySeverity.MEDIUM,
        issue_type="weak_work_factor",
        algorithm="PBKDF2",
        description="PBKDF2 iteration count below 100,000 is insufficient for modern hardware.",
        recommendation="Use at least 100,000 iterations for PBKDF2, or prefer Argon2.",
    ),
    CryptoPattern(
        name="cipher_without_auth",
        pattern=r"""(?:AES\.new\([^)]*(?:MODE_CBC|MODE_CTR|MODE_CFB|MODE_OFB)[^)]*\)(?!.*(?:hmac|HMAC|verify)))""",
        severity=SecuritySeverity.MEDIUM,
        issue_type="unauthenticated_encryption",
        algorithm="AES-CBC/CTR",
        description="Encryption without authentication is vulnerable to padding oracle and other attacks.",
        recommendation="Use authenticated encryption modes like GCM, or encrypt-then-MAC.",
        file_types={".py"},
    ),
    CryptoPattern(
        name="base64_as_encryption",
        pattern=r"""(?:base64\.(?:b64encode|encode)|btoa)\([^)]*(?:password|secret|credential|token)""",
        severity=SecuritySeverity.HIGH,
        issue_type="encoding_not_encryption",
        algorithm="Base64",
        description="Base64 is encoding, not encryption. It provides no security.",
        recommendation="Use proper encryption (AES-GCM) for sensitive data.",
    ),
]
