"""Real scanner journeys through Asgard's public L13 CLI contract."""

import json
import tempfile
from pathlib import Path

from Asgard.cli import main
from Asgard.hercules_l13 import COMPLETION_PREFIX, CONTRACT_VERSION, FINDING_PREFIX


def _read_contract(path):
    findings = []
    completion = None
    for line in path.read_text().splitlines():
        if line.startswith(FINDING_PREFIX):
            findings.append(json.loads(line[len(FINDING_PREFIX):]))
        elif line.startswith(COMPLETION_PREFIX):
            completion = json.loads(line[len(COMPLETION_PREFIX):])
    return findings, completion


def _run(target, output):
    return main(
        [
            "scan",
            "--contract-version",
            CONTRACT_VERSION,
            f"--target={target}",
            f"--output={output}",
        ]
    )


def test_real_scanner_distinguishes_findings_from_execution_failure():
    # Keep the disposable provider fixture outside pytest's ``test_*`` path:
    # Asgard deliberately excludes repository test trees from normal scans.
    with tempfile.TemporaryDirectory(prefix="asgard-l13-fixture-") as fixture:
        fixture_path = Path(fixture)
        target = fixture_path / "vulnerable project Ω"
        target.mkdir()
        (target / "odd file name.py").write_text(
            "import os\n\n"
            "def run(user_input):\n"
            "    return os.system('ping ' + user_input)\n"
        )
        output = fixture_path / "findings output Ω.jsonl"

        code = _run(target, output)
        findings, completion = _read_contract(output)

    assert code == 0
    assert completion["status"] == "findings"
    assert completion["finding_count"] == len(findings)
    assert findings
    assert any("command" in finding["rule"] for finding in findings)
    for finding in findings:
        assert set(finding) == {"id", "location", "message", "rule", "severity"}
        assert finding["location"]["path"] == "odd file name.py"


def test_real_scanner_emits_explicit_clean_result():
    with tempfile.TemporaryDirectory(prefix="asgard-l13-fixture-") as fixture:
        fixture_path = Path(fixture)
        target = fixture_path / "clean project"
        target.mkdir()
        (target / "safe.py").write_text(
            "def normalize(value):\n"
            "    return value.strip()\n"
        )
        output = fixture_path / "clean result.jsonl"

        code = _run(target, output)
        findings, completion = _read_contract(output)

    assert code == 0
    assert findings == []
    assert completion["status"] == "clean"
    assert completion["finding_count"] == 0


def test_real_scanner_refuses_an_input_heimdall_would_partially_skip():
    with tempfile.TemporaryDirectory(prefix="asgard-l13-fixture-") as fixture:
        fixture_path = Path(fixture)
        target = fixture_path / "capped project"
        target.mkdir()
        (target / "oversized.py").write_bytes(b"x" * 1_048_577)
        output = fixture_path / "preserved-result.jsonl"
        output.write_text("previous\n")

        code = _run(target, output)

        assert code == 3
        assert output.read_text() == "previous\n"
