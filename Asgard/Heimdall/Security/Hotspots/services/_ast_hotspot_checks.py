"""
Heimdall AST Hotspot Checks

AST-based hotspot detection logic for HotspotDetector.
"""

import ast
from typing import List

from Asgard.Heimdall.Security.Hotspots.models.hotspot_models import (
    HotspotCategory,
    HotspotConfig,
    ReviewPriority,
    ReviewStatus,
    SecurityHotspot,
)


def detect_ast_hotspots(
    tree: ast.AST,
    file_path: str,
    lines: List[str],
    config: HotspotConfig,
    get_line_fn,
    get_call_name_fn,
) -> List[SecurityHotspot]:
    """Perform AST-based hotspot detection."""
    hotspots: List[SecurityHotspot] = []

    for node in ast.walk(tree):
        if HotspotCategory.DYNAMIC_EXECUTION in config.enabled_categories:
            if isinstance(node, ast.Call):
                func_name = get_call_name_fn(node)
                if func_name in ("eval", "exec", "compile", "__import__"):
                    snippet = get_line_fn(lines, node.lineno)
                    hotspots.append(SecurityHotspot(
                        file_path=file_path,
                        line_number=node.lineno,
                        category=HotspotCategory.DYNAMIC_EXECUTION,
                        review_priority=ReviewPriority.HIGH,
                        title=f"Dynamic code execution: {func_name}()",
                        description=(
                            f"Call to '{func_name}()' executes arbitrary code. "
                            "Ensure the input is never derived from user-controlled data."
                        ),
                        code_snippet=snippet,
                        review_guidance=(
                            "Verify the argument cannot be influenced by external input. "
                            "Consider replacing with safer alternatives such as ast.literal_eval "
                            "for data parsing."
                        ),
                        review_status=ReviewStatus.TO_REVIEW,
                        owasp_category="A03:Injection",
                        cwe_id="CWE-94",
                    ))

        if HotspotCategory.INSECURE_DESERIALIZATION in config.enabled_categories:
            if isinstance(node, ast.Call):
                func_name = get_call_name_fn(node)
                if func_name in ("pickle.loads", "pickle.load", "marshal.loads", "marshal.load"):
                    snippet = get_line_fn(lines, node.lineno)
                    hotspots.append(SecurityHotspot(
                        file_path=file_path,
                        line_number=node.lineno,
                        category=HotspotCategory.INSECURE_DESERIALIZATION,
                        review_priority=ReviewPriority.HIGH,
                        title=f"Insecure deserialization: {func_name}()",
                        description=(
                            f"'{func_name}()' deserializes untrusted data which can "
                            "lead to arbitrary code execution."
                        ),
                        code_snippet=snippet,
                        review_guidance=(
                            "Verify the data source is trusted and cannot be tampered with. "
                            "Consider using JSON or another safer serialization format."
                        ),
                        review_status=ReviewStatus.TO_REVIEW,
                        owasp_category="A08:Software and Data Integrity Failures",
                        cwe_id="CWE-502",
                    ))

        if HotspotCategory.CRYPTO_USAGE in config.enabled_categories:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in ("hashlib", "hmac", "cryptography", "Crypto"):
                        hotspots.append(SecurityHotspot(
                            file_path=file_path,
                            line_number=node.lineno,
                            category=HotspotCategory.CRYPTO_USAGE,
                            review_priority=ReviewPriority.LOW,
                            title=f"Cryptographic module import: {alias.name}",
                            description=(
                                f"Import of '{alias.name}' detected. Review cryptographic "
                                "implementation for algorithm strength and correct usage."
                            ),
                            code_snippet=get_line_fn(lines, node.lineno),
                            review_guidance=(
                                "Ensure strong algorithms are used (SHA-256+, AES-128+). "
                                "Avoid MD5, SHA-1 for security-sensitive operations. "
                                "Ensure keys and IVs are generated securely."
                            ),
                            review_status=ReviewStatus.TO_REVIEW,
                            owasp_category="A02:Cryptographic Failures",
                            cwe_id="CWE-327",
                        ))
            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] in ("hashlib", "hmac", "cryptography", "Crypto"):
                    hotspots.append(SecurityHotspot(
                        file_path=file_path,
                        line_number=node.lineno,
                        category=HotspotCategory.CRYPTO_USAGE,
                        review_priority=ReviewPriority.LOW,
                        title=f"Cryptographic module import: {node.module}",
                        description=(
                            f"Import from '{node.module}' detected. Review cryptographic "
                            "implementation for algorithm strength and correct usage."
                        ),
                        code_snippet=get_line_fn(lines, node.lineno),
                        review_guidance=(
                            "Ensure strong algorithms are used (SHA-256+, AES-128+). "
                            "Avoid MD5, SHA-1 for security-sensitive operations."
                        ),
                        review_status=ReviewStatus.TO_REVIEW,
                        owasp_category="A02:Cryptographic Failures",
                        cwe_id="CWE-327",
                    ))

        if HotspotCategory.XXE in config.enabled_categories:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in ("xml.etree.ElementTree", "xml.etree", "lxml", "minidom"):
                        hotspots.append(SecurityHotspot(
                            file_path=file_path,
                            line_number=node.lineno,
                            category=HotspotCategory.XXE,
                            review_priority=ReviewPriority.MEDIUM,
                            title=f"XML parsing library imported: {alias.name}",
                            description=(
                                f"Import of '{alias.name}' detected. XML parsers may be "
                                "vulnerable to XXE attacks if external entity processing is enabled."
                            ),
                            code_snippet=get_line_fn(lines, node.lineno),
                            review_guidance=(
                                "Disable external entity processing. For lxml, use "
                                "etree.XMLParser(resolve_entities=False). For xml.etree, "
                                "external entities are disabled by default in Python 3.8+."
                            ),
                            review_status=ReviewStatus.TO_REVIEW,
                            owasp_category="A05:Security Misconfiguration",
                            cwe_id="CWE-611",
                        ))
            if isinstance(node, ast.ImportFrom):
                if node.module and any(
                    node.module.startswith(m) for m in ("xml.etree", "lxml", "xml.dom.minidom")
                ):
                    hotspots.append(SecurityHotspot(
                        file_path=file_path,
                        line_number=node.lineno,
                        category=HotspotCategory.XXE,
                        review_priority=ReviewPriority.MEDIUM,
                        title=f"XML parsing module imported: {node.module}",
                        description=(
                            f"Import from '{node.module}' detected. Verify external entity "
                            "processing is disabled."
                        ),
                        code_snippet=get_line_fn(lines, node.lineno),
                        review_guidance=(
                            "Ensure external entity resolution is disabled for all XML parsing. "
                            "Use defusedxml library for untrusted XML input."
                        ),
                        review_status=ReviewStatus.TO_REVIEW,
                        owasp_category="A05:Security Misconfiguration",
                        cwe_id="CWE-611",
                    ))

        if HotspotCategory.INSECURE_RANDOM in config.enabled_categories:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "random":
                        hotspots.append(SecurityHotspot(
                            file_path=file_path,
                            line_number=node.lineno,
                            category=HotspotCategory.INSECURE_RANDOM,
                            review_priority=ReviewPriority.MEDIUM,
                            title="Use of random module (not cryptographically secure)",
                            description=(
                                "The 'random' module uses a pseudo-random number generator "
                                "unsuitable for security-sensitive operations."
                            ),
                            code_snippet=get_line_fn(lines, node.lineno),
                            review_guidance=(
                                "If used for security-sensitive operations (tokens, passwords, "
                                "session IDs), replace with the 'secrets' module."
                            ),
                            review_status=ReviewStatus.TO_REVIEW,
                            owasp_category="A02:Cryptographic Failures",
                            cwe_id="CWE-338",
                        ))
            if isinstance(node, ast.ImportFrom):
                if node.module == "random":
                    hotspots.append(SecurityHotspot(
                        file_path=file_path,
                        line_number=node.lineno,
                        category=HotspotCategory.INSECURE_RANDOM,
                        review_priority=ReviewPriority.MEDIUM,
                        title="Import from random module (not cryptographically secure)",
                        description=(
                            "Import from 'random' module detected. The random module is not "
                            "suitable for security-sensitive operations."
                        ),
                        code_snippet=get_line_fn(lines, node.lineno),
                        review_guidance=(
                            "Replace with 'secrets' module for security-sensitive operations."
                        ),
                        review_status=ReviewStatus.TO_REVIEW,
                        owasp_category="A02:Cryptographic Failures",
                        cwe_id="CWE-338",
                    ))

        if HotspotCategory.PERMISSION_CHECK in config.enabled_categories:
            if isinstance(node, ast.Call):
                func_name = get_call_name_fn(node)
                if func_name in ("os.chmod", "os.access", "os.chown"):
                    snippet = get_line_fn(lines, node.lineno)
                    hotspots.append(SecurityHotspot(
                        file_path=file_path,
                        line_number=node.lineno,
                        category=HotspotCategory.PERMISSION_CHECK,
                        review_priority=ReviewPriority.LOW,
                        title=f"Permission management call: {func_name}()",
                        description=(
                            f"Call to '{func_name}()' modifies or checks file permissions. "
                            "Verify that permissions are set securely and not too permissive."
                        ),
                        code_snippet=snippet,
                        review_guidance=(
                            "Ensure file permissions follow the principle of least privilege. "
                            "Avoid world-writable (0o777) or overly permissive modes."
                        ),
                        review_status=ReviewStatus.TO_REVIEW,
                        owasp_category="A01:Broken Access Control",
                        cwe_id="CWE-269",
                    ))

        if HotspotCategory.SSRF in config.enabled_categories:
            if isinstance(node, ast.Call):
                func_name = get_call_name_fn(node)
                ssrf_funcs = (
                    "requests.get", "requests.post", "requests.put",
                    "requests.delete", "requests.request", "requests.patch",
                    "urllib.request.urlopen", "urllib.urlopen",
                )
                if func_name in ssrf_funcs:
                    if node.args and isinstance(node.args[0], ast.Name):
                        snippet = get_line_fn(lines, node.lineno)
                        hotspots.append(SecurityHotspot(
                            file_path=file_path,
                            line_number=node.lineno,
                            category=HotspotCategory.SSRF,
                            review_priority=ReviewPriority.HIGH,
                            title=f"Potential SSRF: {func_name}() with variable URL",
                            description=(
                                f"'{func_name}()' is called with a variable URL argument. "
                                "If the URL originates from user input, this may be vulnerable to SSRF."
                            ),
                            code_snippet=snippet,
                            review_guidance=(
                                "Validate and whitelist allowed URL schemes and hosts. "
                                "Reject requests to internal IP ranges (RFC 1918). "
                                "Use an allow-list of permitted external hosts."
                            ),
                            review_status=ReviewStatus.TO_REVIEW,
                            owasp_category="A10:Server-Side Request Forgery",
                            cwe_id="CWE-918",
                        ))

    return hotspots
