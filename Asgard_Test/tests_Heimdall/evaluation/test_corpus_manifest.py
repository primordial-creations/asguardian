"""CorpusManifest loading + CVE-holdout resolution (plan 10 s1)."""

import json
from pathlib import Path

from Asgard.Heimdall.evaluation.corpus import CorpusManifest

MANIFEST_PATH = Path(__file__).parent / "corpus" / "manifest.json"


def test_seed_manifest_loads_and_has_stratification_schema():
    manifest = CorpusManifest.load(MANIFEST_PATH)
    assert manifest.cve_holdouts == []
    assert manifest.clean_repos == []
    assert "framework" in manifest.stratification
    assert manifest.ground_truth_instances() == []


def test_ground_truth_instances_resolved_from_synthetic_entry(tmp_path):
    repo_dir = tmp_path / "some_repo"
    (repo_dir / "app").mkdir(parents=True)
    target = repo_dir / "app" / "views.py"
    target.write_text("\n".join(f"line {i}" for i in range(1, 30)), encoding="utf-8")

    manifest_data = {
        "cve_holdouts": [
            {
                "cve_id": "CVE-2024-0001",
                "repo_path": "some_repo",
                "commit_sha": "deadbeef",
                "patch_spans": [
                    {"file": "app/views.py", "start_line": 10, "end_line": 12, "cwe": "CWE-89"}
                ],
            }
        ],
        "clean_repos": [],
        "stratification": {},
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    manifest = CorpusManifest.load(manifest_path)
    instances = manifest.ground_truth_instances(checkout_root=tmp_path)
    assert len(instances) == 1
    inst = instances[0]
    assert inst.cwe == "CWE-89"
    assert inst.source == "cve_holdout"
    assert inst.span.start_line == 10
    assert inst.span.end_line == 12
    assert inst.file_path == str(target)


def test_ground_truth_instances_skips_missing_checkout_gracefully(tmp_path):
    manifest_data = {
        "cve_holdouts": [
            {
                "cve_id": "CVE-2024-0002",
                "repo_path": "not_checked_out",
                "patch_spans": [
                    {"file": "x.py", "start_line": 1, "end_line": 1, "cwe": "CWE-78"}
                ],
            }
        ]
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")
    manifest = CorpusManifest.load(manifest_path)
    # Resolution does not raise even though the repo isn't checked out --
    # it still produces a GroundTruthInstance (the harness treats "not
    # checked out" as the caller's responsibility to filter/skip when
    # actually scanning; this test documents that behaviour is
    # non-raising, matching run_corpus's tolerance of unmatched GT).
    instances = manifest.ground_truth_instances(checkout_root=manifest_path.parent)
    assert len(instances) == 1
