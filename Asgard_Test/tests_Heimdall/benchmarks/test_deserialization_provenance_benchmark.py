"""Benchmark corpus for deserialization provenance classification (plan 07.5).

`pickle.loads`/`yaml.load` on attacker-influenced data must be a real
finding (mechanism `deserialization.untrusted`); the same sink on
internal/static data must be reported as a hotspot for review
(`deserialization.hotspot`, LOW severity) -- never a confident claim of
exploitability, since gadget-chain existence is statically unprovable.
"""
from pathlib import Path

from Asgard.Heimdall.Security.Deserialization.models.deserialization_models import (
    DeserializationScanConfig,
)
from Asgard.Heimdall.Security.Deserialization.services.deserialization_scanner import (
    DeserializationScanner,
)


def _scan(tmp_path: Path, code: str):
    (tmp_path / "app.py").write_text(code)
    return DeserializationScanner().scan(DeserializationScanConfig(scan_path=tmp_path))


def test_pickle_from_flask_request_is_untrusted_finding(tmp_path):
    report = _scan(tmp_path, """
import pickle
from flask import request

def handler():
    payload = request.data
    return pickle.loads(payload)
""")
    assert report.total_findings == 1
    f = report.findings[0]
    assert f.is_hotspot is False
    assert f.mechanism_id == "deserialization.untrusted"
    assert f.provenance == "untrusted"
    assert f.confidence >= 0.8
    assert f.severity == "CRITICAL"


def test_pickle_from_local_config_file_is_hotspot(tmp_path):
    report = _scan(tmp_path, """
import pickle
from pathlib import Path

def load_cache():
    raw = Path("internal_cache.bin").read_bytes()
    return pickle.loads(raw)
""")
    assert report.total_findings == 1
    f = report.findings[0]
    assert f.is_hotspot is True
    assert f.mechanism_id == "deserialization.hotspot"
    assert f.provenance == "internal"
    assert f.severity == "LOW"
    assert "hotspot" in f.description.lower()


def test_pickle_with_unknown_provenance_is_needs_review_medium(tmp_path):
    # Post-review fix (BLOCKER-1): an unresolvable origin must NEVER be
    # silently folded into the low-severity hotspot bucket -- "unknown"
    # is not "safe". A bare parameter with no untrusted OR internal
    # naming/structural signal surfaces as a needs-review MEDIUM finding.
    report = _scan(tmp_path, """
import pickle

def load_thing(data):
    return pickle.loads(data)
""")
    assert report.total_findings == 1
    f = report.findings[0]
    assert f.is_hotspot is False
    assert f.provenance == "unknown"
    assert f.severity == "MEDIUM"
    assert "needs-review" in f.description.lower() or "needs review" in f.description.lower()


def test_php_unserialize_from_superglobal_is_untrusted(tmp_path):
    (tmp_path / "app.php").write_text("<?php\n$obj = unserialize($_GET['data']);\n")
    report = DeserializationScanner().scan(DeserializationScanConfig(scan_path=tmp_path))
    findings = [f for f in report.findings if f.language == "php"]
    assert findings
    untrusted = [f for f in findings if f.provenance == "untrusted"]
    assert untrusted, "PHP unserialize on a superglobal must be classified untrusted"


def test_yaml_load_from_kafka_message_is_untrusted(tmp_path):
    report = _scan(tmp_path, """
import yaml

def consume(msg):
    payload = kafka_consumer.poll()
    return yaml.load(payload)
""")
    assert report.total_findings == 1
    assert report.findings[0].provenance == "untrusted"
    assert report.findings[0].is_hotspot is False
