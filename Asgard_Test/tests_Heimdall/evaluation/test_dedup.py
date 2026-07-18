"""Semantic-instance dedup by (file, sink, cwe) (plan 10 s2 / plan 04 parity)."""

from Asgard.Heimdall.evaluation.corpus import ReportedFinding
from Asgard.Heimdall.evaluation.dedup import dedup_findings


def test_dedup_collapses_same_sink_and_cwe():
    findings = [
        ReportedFinding(file_path="a.py", line=10, cwe="CWE-89", confidence=0.6, sink_node_id="sink1"),
        ReportedFinding(file_path="a.py", line=10, cwe="CWE-89", confidence=0.9, sink_node_id="sink1"),
    ]
    out = dedup_findings(findings)
    assert len(out) == 1
    assert out[0].confidence == 0.9


def test_dedup_keeps_distinct_cwe_at_same_sink():
    findings = [
        ReportedFinding(file_path="a.py", line=10, cwe="CWE-89", confidence=0.6, sink_node_id="sink1"),
        ReportedFinding(file_path="a.py", line=10, cwe="CWE-78", confidence=0.6, sink_node_id="sink1"),
    ]
    out = dedup_findings(findings)
    assert len(out) == 2


def test_dedup_falls_back_to_line_when_no_sink_id():
    findings = [
        ReportedFinding(file_path="a.py", line=42, cwe="CWE-89", confidence=0.5),
        ReportedFinding(file_path="a.py", line=42, cwe="CWE-89", confidence=0.7),
        ReportedFinding(file_path="a.py", line=43, cwe="CWE-89", confidence=0.5),
    ]
    out = dedup_findings(findings)
    assert len(out) == 2
    lines = sorted(f.line for f in out)
    assert lines == [42, 43]


def test_dedup_distinct_files_not_collapsed():
    findings = [
        ReportedFinding(file_path="a.py", line=10, cwe="CWE-89", confidence=0.6, sink_node_id="sink1"),
        ReportedFinding(file_path="b.py", line=10, cwe="CWE-89", confidence=0.6, sink_node_id="sink1"),
    ]
    out = dedup_findings(findings)
    assert len(out) == 2
