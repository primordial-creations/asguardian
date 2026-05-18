"""Insecure deserialization scanner."""

import os
import re
from pathlib import Path
from typing import List

from Asgard.Heimdall.Security.Deserialization.models.deserialization_models import (
    DeserializationFinding,
    DeserializationScanConfig,
    DeserializationScanReport,
    DeserializationSeverity,
)

_LANG_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "javascript",
    ".java": "java",
    ".php": "php",
    ".rb": "ruby",
    ".cs": "csharp",
    ".go": "go",
}

_VULNERABILITY_PATTERNS: dict = {
    "python": [
        (r"pickle\.loads?\s*\(", "CRITICAL", "pickle_load", "pickle deserialization allows arbitrary code execution", "Use JSON or other safe serialization formats"),
        (r"cPickle\.loads?\s*\(", "CRITICAL", "cpickle_load", "cPickle is equally vulnerable as pickle", "Use JSON or safe alternatives"),
        (r"marshal\.loads?\s*\(", "CRITICAL", "marshal_load", "marshal deserialization is unsafe", "Use JSON for untrusted data"),
        (r"shelve\.open\s*\(", "HIGH", "shelve_open", "shelve uses pickle internally", "Avoid shelve with untrusted data"),
        (r"yaml\.load\s*\([^)]*\)(?!\s*,\s*Loader)", "CRITICAL", "yaml_unsafe_load", "yaml.load without Loader is unsafe", "Use yaml.safe_load()"),
        (r"jsonpickle\.decode\s*\(", "CRITICAL", "jsonpickle_decode", "jsonpickle can execute arbitrary code", "Use standard json module"),
        (r"dill\.loads?\s*\(", "CRITICAL", "dill_load", "dill allows arbitrary code execution", "Use JSON for untrusted data"),
    ],
    "javascript": [
        (r"node-serialize|serialize-javascript.*unserialize", "CRITICAL", "node_serialize", "node-serialize allows code execution", "Use JSON.parse() instead"),
        (r"\.deserialize\s*\([^)]*(?:req\.|request\.|body\.)", "HIGH", "deserialize_from_input", "Deserialization from user input", "Validate and sanitize before deserializing"),
    ],
    "java": [
        (r"ObjectInputStream\s*\(\s*(?!.*trusted)", "CRITICAL", "object_input_stream", "Java ObjectInputStream is dangerous with untrusted data", "Use serialization filters (Java 9+)"),
        (r"readObject\s*\(\s*\)", "CRITICAL", "read_object", "readObject can execute attacker-controlled code", "Implement serialization filter"),
        (r"XStream.*fromXML", "CRITICAL", "xstream_xml", "XStream XML deserialization is vulnerable", "Configure XStream security framework"),
    ],
    "php": [
        (r"unserialize\s*\(\s*\$_(?:GET|POST|REQUEST|COOKIE)", "CRITICAL", "php_unserialize_input", "PHP unserialize from user input allows object injection", "Use JSON instead of PHP serialization"),
        (r"unserialize\s*\(", "HIGH", "php_unserialize", "PHP unserialize can trigger object injection", "Validate data source before unserializing"),
    ],
    "ruby": [
        (r"Marshal\.load\s*\(", "CRITICAL", "ruby_marshal_load", "Ruby Marshal.load allows arbitrary code execution", "Use JSON for untrusted data"),
        (r"YAML\.load\s*\(", "CRITICAL", "ruby_yaml_load", "Ruby YAML.load with untrusted data is dangerous", "Use YAML.safe_load()"),
    ],
    "csharp": [
        (r"BinaryFormatter.*Deserialize", "CRITICAL", "binary_formatter", "BinaryFormatter is insecure", "Use System.Text.Json or DataContractSerializer"),
        (r"JavaScriptSerializer.*Deserialize", "HIGH", "js_serializer", "JavaScriptSerializer can be exploited", "Use System.Text.Json"),
    ],
}


class DeserializationScanner:
    """Scans source code for insecure deserialization vulnerabilities."""

    def __init__(self) -> None:
        self._compiled: dict = {}
        for lang, patterns in _VULNERABILITY_PATTERNS.items():
            self._compiled[lang] = [
                (re.compile(p, re.IGNORECASE), severity, ptype, desc, rec)
                for p, severity, ptype, desc, rec in patterns
            ]

    def scan(self, config: DeserializationScanConfig) -> DeserializationScanReport:
        findings: List[DeserializationFinding] = []
        files_scanned = 0
        target = config.scan_path
        skip = set(config.skip_dirs)

        if target.is_file():
            findings = self._scan_file(target)
            files_scanned = 1
        else:
            for root, dirs, files in os.walk(target):
                dirs[:] = [d for d in dirs if d not in skip]
                for name in files:
                    fp = Path(root) / name
                    ff = self._scan_file(fp)
                    if ff:
                        findings.extend(ff)
                        files_scanned += 1

        by_severity: dict = {}
        by_language: dict = {}
        for f in findings:
            by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1
            by_language[f.language] = by_language.get(f.language, 0) + 1

        return DeserializationScanReport(
            scan_path=str(config.scan_path),
            total_findings=len(findings),
            files_scanned=files_scanned,
            findings=findings,
            by_severity=by_severity,
            by_language=by_language,
        )

    def _scan_file(self, file_path: Path) -> List[DeserializationFinding]:
        findings: List[DeserializationFinding] = []
        lang = _LANG_EXTENSIONS.get(file_path.suffix.lower())
        if not lang or lang not in self._compiled:
            return findings

        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return findings

        for line_num, line in enumerate(lines, 1):
            for regex, severity, ptype, desc, rec in self._compiled[lang]:
                if regex.search(line):
                    findings.append(DeserializationFinding(
                        file_path=str(file_path),
                        line_number=line_num,
                        severity=DeserializationSeverity(severity),
                        language=lang,
                        pattern_type=ptype,
                        code_snippet=line.strip()[:150],
                        description=desc,
                        recommendation=rec,
                    ))

        return findings
