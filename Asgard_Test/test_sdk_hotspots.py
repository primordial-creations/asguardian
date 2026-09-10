"""Strict hotspot engine and source-protocol regressions."""
from pathlib import Path
import pytest
from Asgard.sdk_protocol import respond
from Asgard.Heimdall.Security.Hotspots.models.hotspot_models import HotspotConfig
from Asgard.Heimdall.Security.Hotspots.services.hotspot_detector import HotspotDetector
from Asgard.Heimdall.cli.handlers._security_dispatch import load_heimdall_yml

SOURCE = "import hashlib\nhashlib.md5(b'x')\n"

def request(root, limit=1000):
    return dict(protocol_version=1, operation='scan', correlation_id='hotspot-fixture',
                profile='security.hotspots', authorized_root=str(root.resolve()),
                target=str(root.resolve()), max_findings=limit)


def test_manual_review_not_vulnerability_and_parse_failure_retains_it(tmp_path):
    (tmp_path / '.heimdall.yml').write_text('test_context_enabled: false\n')
    (tmp_path / 'main.py').write_text(SOURCE)
    report, code = respond(request(tmp_path))
    assert code == 1 and report['complete'] and report['finding_kind'] == 'security_hotspot'
    finding = report['findings'][0]
    assert finding['category'] == 'weak_hashing'
    assert finding['review_priority'] == 'medium' and finding['review_status'] == 'to_review'
    (tmp_path / 'broken.py').write_text('def broken(:\n')
    report, code = respond(request(tmp_path))
    assert code == 1 and not report['complete'] and report['findings']
    assert report['errors'][0]['stage'] == 'parse'


def test_strict_failed_read_does_not_become_empty_clean(tmp_path, monkeypatch):
    good, bad = tmp_path / 'main.py', tmp_path / 'unreadable.py'
    good.write_text(SOURCE); bad.write_text(SOURCE)
    original = Path.read_text
    def read(path, *args, **kwargs):
        if path == bad: raise PermissionError('controlled fixture')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read)
    report = HotspotDetector(HotspotConfig(test_context_enabled=False)).scan(tmp_path, strict_io=True)
    assert not report.analysis_complete and report.total_hotspots == 1
    assert report.analysis_errors[0]['error_type'] == 'PermissionError'


def test_symlink_and_truncation_are_incomplete(tmp_path):
    (tmp_path / '.heimdall.yml').write_text('test_context_enabled: false\n')
    (tmp_path / 'main.py').write_text(SOURCE * 2)
    report, _ = respond(request(tmp_path, 1))
    assert report['truncated'] and not report['complete'] and len(report['findings']) == 1
    (tmp_path / 'escape.py').symlink_to(Path(__file__).resolve())
    report, _ = respond(request(tmp_path))
    assert not report['complete'] and any(e['stage'] == 'discovery' for e in report['errors'])


@pytest.mark.parametrize('content', ['[broken', '[]', 'test_context_enabled: []', 'strict_scan_paths: ["["]'])
def test_invalid_configuration_is_not_defaulted(tmp_path, content):
    (tmp_path / '.heimdall.yml').write_text(content)
    report, code = respond(request(tmp_path))
    assert code == 1 and report['state'] == 'incomplete'
    assert report['errors'][0]['code'] == 'scan_configuration_error'


def test_configuration_link_rejected_and_legacy_loader_compatible(tmp_path):
    source = tmp_path / 'other.yml'; source.write_text('test_context_enabled: false')
    (tmp_path / '.heimdall.yml').symlink_to(source)
    assert load_heimdall_yml(tmp_path) == {'test_context_enabled': False}
    report, _ = respond(request(tmp_path))
    assert not report['complete'] and report['errors'][0]['code'] == 'scan_configuration_error'
