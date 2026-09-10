"""Actual process/engine checks for the initial protocol profile."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from Asgard.sdk_protocol import MAX_REQUEST_BYTES


def invoke(request):
    process = subprocess.run(
        [sys.executable, "-m", "Asgard.sdk_protocol"],
        input=request if isinstance(request, bytes) else json.dumps(request).encode(),
        capture_output=True, timeout=20, check=False,
    )
    return process.returncode, json.loads(process.stdout)


def request(tmp_path, **changes):
    return dict(protocol_version=1, correlation_id="fixture-1", operation="scan",
                profile="quality.file-length", authorized_root=str(tmp_path.resolve()),
                target=str(tmp_path.resolve()), **changes)


def test_handshake_without_engine_import():
    code, result = invoke(dict(protocol_version=1, correlation_id="handshake", operation="handshake"))
    assert code == 0 and result["state"] == "ready"
    assert result["capabilities"]["profiles"] == ["quality.file-length", "security.hotspots"]
    assert result["capabilities"]["remote"] is False


def test_real_clean_then_nonzero_with_findings(tmp_path):
    (tmp_path / "source with spaces.py").write_text("one\n")
    code, result = invoke(request(tmp_path))
    assert code == 0 and result["complete"] and not result["findings"]
    (tmp_path / "source with spaces.py").write_text("one\n" * 301)
    code, result = invoke(request(tmp_path))
    assert code == 1 and result["complete"] and not result["truncated"]
    assert result["correlation_id"] == "fixture-1"
    assert result["findings"][0]["relative_path"] == "source with spaces.py"
    assert result["findings"][0]["lines_over"] == 1


def test_output_limit_is_incomplete(tmp_path):
    for name in ("one.py", "two.py"):
        (tmp_path / name).write_text("one\n" * 301)
    code, result = invoke(request(tmp_path, max_findings=1))
    assert code == 1 and result["state"] == "incomplete"
    assert result["truncated"] and not result["complete"]
    assert len(result["findings"]) == 1
    assert result["summary"]["files_exceeding_threshold"] == 2


def test_escaping_child_link_is_incomplete(tmp_path):
    (tmp_path / "escape.py").symlink_to(Path(__file__).resolve())
    code, result = invoke(request(tmp_path))
    assert code == 1 and not result["complete"]
    assert result["errors"][0]["code"] == "scan_io_failure"
    assert not result["findings"]


@pytest.mark.parametrize("change,expected", [
    ({"protocol_version": 2}, "version_mismatch"),
    ({"protocol_version": True}, "version_mismatch"),
    ({"profile": "security"}, "unsupported_operation"),
    ({"target": "/"}, "invalid_request"),
    ({"max_findings": True}, "invalid_request"),
    ({"fix_mode": True}, "invalid_request"),
])
def test_rejections_are_not_clean(tmp_path, change, expected):
    payload = request(tmp_path)
    payload.update(change)
    code, result = invoke(payload)
    assert code == 2 and not result["complete"]
    assert result["errors"][0]["code"] == expected


@pytest.mark.parametrize("raw", [b"{", b"[]", b"x" * (MAX_REQUEST_BYTES + 1)])
def test_invalid_wire_input(raw):
    code, result = invoke(raw)
    assert code == 2 and not result["complete"]
    assert result["errors"][0]["code"] == "invalid_request"
