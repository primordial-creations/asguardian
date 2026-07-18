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
from Asgard.Heimdall.Security.normalization.priority import confidence_bucket

# Plan 07.5: backward-window provenance markers. These are intentionally
# textual (not full inter-procedural taint -- that lives in TaintAnalysis
# and is a larger lift) but give a "near-free" precision win: a sink fed by
# an obviously untrusted source nearby is a real finding; one fed by a
# static/internal source is a hotspot, not a finding. Documented FN: a
# variable renamed/reassigned outside the window, or untrusted data that
# arrives via a call several functions away, is not traced (silently
# treated as unknown -> hotspot, never silently dropped).
_UNTRUSTED_MARKERS = re.compile(
    r"(?:request\.|req\.|flask\.request|django\.http|self\.request|"
    r"socket\.(?:recv|accept)|urlopen|urlretrieve|sys\.stdin|input\(|"
    r"\.body\b|\.data\b|\.get_json|\.form\[|\.args\[|"
    r"kafka|rabbitmq|celery|redis\.get|sqs|websocket|ws\.recv|"
    r"\$_(?:GET|POST|REQUEST|COOKIE)|params\[|query\[|"
    # Common untrusted-input parameter-naming convention: a function
    # parameter literally named user_data/user_input/etc is the standard
    # textual signal SAST tools use to infer a taint source when no
    # framework decorator is present.
    r"user_data|user_input|untrusted|client_data|raw_input)",
    re.IGNORECASE,
)
_INTERNAL_MARKERS = re.compile(
    r"(?:open\(|Path\(|\.read_text\(|\.read_bytes\(|importlib|"
    r"pkgutil|pkg_resources|__file__|os\.path\.join\(.*(?:config|internal|fixtures))",
    re.IGNORECASE,
)
# Backward window size (lines) for the textual provenance scan.
_PROVENANCE_WINDOW = 15

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
                    provenance, confidence, is_hotspot = self._classify_provenance(lines, line_num)
                    finding_severity = severity
                    description = desc
                    if is_hotspot:
                        # Never claim gadget-chain proof for data whose origin we
                        # can't demonstrate is attacker-influenced -- downgrade
                        # to a hotspot instead of an actionable finding.
                        finding_severity = "LOW"
                        description = (
                            f"{desc} (data provenance not confirmed attacker-influenced "
                            f"-- reported as a hotspot for review, provenance={provenance})"
                        )
                    else:
                        description = f"{desc} (deserialization of attacker-influenced data)"

                    findings.append(DeserializationFinding(
                        file_path=str(file_path),
                        line_number=line_num,
                        severity=DeserializationSeverity(finding_severity),
                        language=lang,
                        pattern_type=ptype,
                        code_snippet=line.strip()[:150],
                        description=description,
                        recommendation=rec,
                        mechanism_id="deserialization.hotspot" if is_hotspot else "deserialization.untrusted",
                        confidence=confidence,
                        confidence_bucket=confidence_bucket(confidence),
                        is_hotspot=is_hotspot,
                        provenance=provenance,
                    ))

        return findings

    def _classify_provenance(self, lines: List[str], line_num: int):
        """
        Plan 07.5 provenance heuristic: scan a backward window of source
        lines around the deserialization sink for untrusted-source or
        internal-source textual markers.

        Returns (provenance, confidence, is_hotspot). Documented limitation:
        this is a textual backward scan, not inter-procedural taint --
        sources several call-frames away are not traced and default to
        "unknown" (treated as a hotspot, never silently dropped and never
        confidently claimed as attacker-controlled without evidence).
        """
        start = max(0, line_num - 1 - _PROVENANCE_WINDOW)
        window = "\n".join(lines[start:line_num])

        if _UNTRUSTED_MARKERS.search(window):
            return "untrusted", 0.85, False
        if _INTERNAL_MARKERS.search(window):
            return "internal", 0.3, True
        return "unknown", 0.5, True
