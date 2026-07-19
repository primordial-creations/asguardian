"""
Benchmark corpus runner for the taint engine (plan 04 Testing; plan 01
acceptance gate: migrated rules must ship benchmark corpus cases).

Each fixture in ``corpus/taint/`` is scanned in isolation and the outcome is
checked against ``manifest.yml``: TP fixtures must produce exactly the
expected flows in the expected confidence bucket; FP siblings must be clean
at the default reporting threshold.
"""

import shutil
import tempfile
from pathlib import Path

import pytest
import yaml

from Asgard.Heimdall.Security.TaintAnalysis import TaintAnalyzer, TaintConfig

CORPUS_DIR = Path(__file__).parent / "corpus" / "taint"
MANIFEST = yaml.safe_load((CORPUS_DIR / "manifest.yml").read_text())
CASES = MANIFEST["cases"]


def _scan_fixture(fixture_name: str):
    """Scan one corpus file in isolation (fixture names carry tp_/fp_
    prefixes, which must not trip test-file exclusion heuristics)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "fixture.py"
        shutil.copyfile(CORPUS_DIR / fixture_name, target)
        config = TaintConfig(exclude_patterns=["__pycache__", ".git"])
        return TaintAnalyzer(config=config).scan(Path(tmpdir))


@pytest.mark.parametrize(
    "case", CASES, ids=[c["file"].removesuffix(".py") for c in CASES]
)
def test_corpus_case(case):
    report = _scan_fixture(case["file"])
    if case["expect"] == "no_flow":
        assert report.flows == [], (
            f"{case['file']}: expected clean, got "
            f"{[(f.sink_type, f.confidence) for f in report.flows]}"
        )
        return
    assert len(report.flows) == case["count"], (
        f"{case['file']}: expected {case['count']} flow(s), got "
        f"{[(f.sink_type, f.confidence) for f in report.flows]}"
    )
    flow = report.flows[0]
    assert flow.severity == case["severity"]
    assert flow.confidence_bucket in case["bucket_in"], (
        f"{case['file']}: bucket {flow.confidence_bucket} "
        f"(confidence {flow.confidence}) not in {case['bucket_in']}"
    )
    if case.get("cwe"):
        assert flow.cwe_id == case["cwe"]
    if case.get("finding_class"):
        # WS5 dynamic-construct surfacing: eval/exec/getattr-dispatch/
        # __import__ findings are tagged with a distinct finding_class
        # ("dynamic_construct") and needs_review confidence bucket rather
        # than the default "taint_flow" -- never certain, since the
        # analysis cannot statically prove what the dynamic construct does.
        assert flow.finding_class == case["finding_class"]


def test_corpus_determinism():
    """Two consecutive scans on identical input yield identical findings."""
    for case in CASES[:4]:
        r1 = _scan_fixture(case["file"])
        r2 = _scan_fixture(case["file"])
        strip = {"scan_duration_seconds", "scanned_at", "scan_path"}
        d1 = r1.model_dump(exclude=strip)
        d2 = r2.model_dump(exclude=strip)
        # file paths differ per tempdir; compare flows modulo path prefix
        for d in (d1, d2):
            for flow in d["flows"]:
                for loc in (flow["source_location"], flow["sink_location"]):
                    loc["file_path"] = Path(loc["file_path"]).name
                for step in flow["intermediate_steps"]:
                    step["file_path"] = Path(step["file_path"]).name
        assert d1 == d2
