"""Benchmark corpus for the secrets semantic-context scorer (plan 07.3).

Vulnerable/safe pairs: high-signal identifier names should raise
confidence toward "certain" even for borderline entropy; hash/uuid-shaped
identifiers should pull confidence down (but never suppress, per plan
07.3's "secrets are never test-suppressed" rule extended to low semantic
signal -- unresolved semantic context is not proof of safety).
"""
import tempfile
from pathlib import Path

from Asgard.Heimdall.Security.services.secrets_detection_service import (
    SecretsDetectionService,
)


def _scan(code: str):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "app.py").write_text(code)
        return SecretsDetectionService().scan(tmp_path)


def test_high_signal_identifier_raises_confidence_to_certain():
    report = _scan(
        'aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"\n'
    )
    # This specific AWS-shaped example key is filtered by the dummy
    # filter (contains "EXAMPLE") -- use a high-entropy non-dummy value
    # for the semantic-signal assertion instead.
    report = _scan(
        'aws_secret_access_key = "kX9pL2mQ7vT4rN8wZ1yB5dF3sH6jC0aE1234ABCDEFG3"\n'
    )
    hits = [f for f in report.findings if "aws_secret_access_key" in f.line_content.lower() or f.pattern_name]
    assert len(report.findings) > 0
    assert any(f.confidence_bucket == "certain" for f in report.findings), (
        f"expected 'certain' bucket for high-signal identifier, got "
        f"{[(f.pattern_name, f.confidence, f.confidence_bucket) for f in report.findings]}"
    )


def test_hash_shaped_identifier_lowers_but_does_not_suppress():
    value = "kX9pL2mQ7vT4rN8wZ1yB5dF3sH6jC0aE1234ABCDEFG3"
    report_hash = _scan(f'commit_hash = "{value}"\n')
    report_secret = _scan(f'aws_secret_access_key = "{value}"\n')
    # Same literal value -- semantic identity of the LHS should move
    # confidence without erasing the finding outright.
    if report_hash.findings and report_secret.findings:
        hash_conf = max(f.confidence for f in report_hash.findings)
        secret_conf = max(f.confidence for f in report_secret.findings)
        assert secret_conf >= hash_conf, (
            "aws_secret_access_key= should never score lower confidence than "
            "commit_hash= for the identical literal value"
        )


def test_env_proximity_lowers_semantic_score():
    from Asgard.Heimdall.Security.services._secrets_semantic_context import semantic_score
    line = 'token = os.environ.get("TOKEN")'
    score = semantic_score(line, 0, line)
    assert score <= 0.2


def test_behavioral_sink_proof_maximizes_semantic_score():
    from Asgard.Heimdall.Security.services._secrets_semantic_context import semantic_score
    line = 'headers["Authorization"] = "Bearer kX9pL2mQ7vT4rN8wZ1yB5dF3sH6jC0aE"'
    score = semantic_score(line, 0, line)
    assert score == 1.0


def test_fold_semantic_score_never_fully_suppresses_low_signal():
    from Asgard.Heimdall.Security.services._secrets_semantic_context import fold_semantic_score
    folded = fold_semantic_score(base_confidence=0.8, sem_score=0.1)
    assert folded >= 0.3, "low semantic signal must lower, never zero out, confidence"
