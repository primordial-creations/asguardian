"""Benchmark for the Container/IaC CIS/NIST compliance mapping (plan
07.8). Vulnerable/safe pair: a root-user Dockerfile must carry a CIS
Docker Benchmark control id and mechanism_id; a hardened Dockerfile
produces no findings to map.
"""
import tempfile
from pathlib import Path

from Asgard.Heimdall.Security.Container.services.dockerfile_analyzer import (
    DockerfileAnalyzer,
)


def _scan(dockerfile_text: str):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "Dockerfile").write_text(dockerfile_text)
        return DockerfileAnalyzer().scan(tmp_path)


def test_root_user_finding_carries_cis_and_mechanism_id():
    report = _scan("FROM python:3.11\nCOPY . /app\nCMD [\"python\", \"app.py\"]\n")
    root_hits = [f for f in report.findings if f.finding_type == "root_user"]
    assert root_hits, "missing USER directive should be flagged"
    assert root_hits[0].mechanism_id == "container.root_user"
    assert root_hits[0].cis_docker_benchmark == "CIS-Docker-4.1"
    assert root_hits[0].nist_800_190


def test_hardened_dockerfile_has_no_root_user_finding():
    report = _scan(
        "FROM python:3.11-slim\n"
        "RUN useradd -m appuser\n"
        "COPY . /app\n"
        "USER appuser\n"
        "HEALTHCHECK CMD python -c \"pass\"\n"
        "CMD [\"python\", \"app.py\"]\n"
    )
    assert not any(f.finding_type == "root_user" for f in report.findings)


def test_every_finding_gets_a_mechanism_id():
    report = _scan(
        "FROM ubuntu:latest\n"
        "RUN chmod 777 /app\n"
        "RUN apt-get install -y sudo\n"
    )
    assert report.findings
    assert all(f.mechanism_id for f in report.findings), (
        "plan 07.8: every upgraded rule must emit a mechanism_id for the "
        "plan-06 normalization engine"
    )
