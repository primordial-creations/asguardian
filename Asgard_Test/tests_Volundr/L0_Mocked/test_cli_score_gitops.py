"""
CLI wiring tests: volundr score, volundr gitops validate, and the
--digest/--secret-mount/--edge-service generation flags.
"""

import pytest

from Asgard.Volundr.cli import main as volundr_main
from Asgard.Volundr.cli._parser import create_parser

DEPLOYMENT = """\
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 1
  selector:
    matchLabels: {app: web}
  template:
    metadata:
      labels: {app: web}
    spec:
      containers:
        - name: web
          image: nginx:latest
"""

ARGO_APP = """\
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp
spec:
  project: default
  source:
    repoURL: https://github.com/org/repo
    targetRevision: HEAD
    path: k8s
  destination:
    server: https://kubernetes.default.svc
    namespace: prod
  syncPolicy:
    automated:
      prune: true
"""


def _run(argv):
    with pytest.raises(SystemExit) as exc:
        volundr_main(argv)
    return exc.value.code


# ---------------------------------------------------------------- parsing

def test_parser_accepts_score():
    args = create_parser().parse_args(
        ["score", "x.yaml", "--threshold", "80", "--format", "json"]
    )
    assert args.command == "score"
    assert args.threshold == 80.0


def test_parser_accepts_gitops_validate():
    args = create_parser().parse_args(["gitops", "validate", "app.yaml"])
    assert args.gitops_command == "validate"


def test_parser_accepts_generation_flags():
    args = create_parser().parse_args(
        ["docker", "dockerfile", "--name", "a", "--base", "python:3.12",
         "--digest", "sha256:abc", "--secret-mount", "tok:/run/secrets/t"]
    )
    assert args.digest == "sha256:abc"
    assert args.secret_mounts == ["tok:/run/secrets/t"]

    args = create_parser().parse_args(
        ["compose", "generate", "proj", "--service", "web:nginx:80",
         "--edge-service", "web"]
    )
    assert args.edge_services == ["web"]


# ---------------------------------------------------------------- score

def test_score_grades_hardening_gaps(tmp_path, capsys):
    f = tmp_path / "dep.yaml"
    f.write_text(DEPLOYMENT)
    code = _run(["score", str(f)])
    out = capsys.readouterr().out
    assert "grade" in out
    assert "VOL-K8S-0001" in out  # remediation hint present
    assert code == 0  # composite above the default threshold


def test_score_exits_nonzero_below_threshold(tmp_path):
    f = tmp_path / "dep.yaml"
    f.write_text(DEPLOYMENT)
    assert _run(["score", str(f), "--threshold", "99"]) == 1


def test_score_missing_path_exits_2(capsys):
    assert _run(["score", "/nonexistent/x.yaml"]) == 2


# ---------------------------------------------------------------- gitops

def test_gitops_validate_flags_antipatterns(tmp_path, capsys):
    f = tmp_path / "app.yaml"
    f.write_text(ARGO_APP)
    code = _run(["gitops", "validate", str(f)])
    out = capsys.readouterr().out
    assert "VOL-GITOPS-0001" in out  # HEAD revision
    assert "VOL-GITOPS-0002" in out  # default project
    assert code == 1


def test_gitops_validate_no_applications_exits_2(tmp_path, capsys):
    f = tmp_path / "not_app.yaml"
    f.write_text(DEPLOYMENT)
    assert _run(["gitops", "validate", str(f)]) == 2


# ---------------------------------------------------------------- generation

def test_dockerfile_digest_and_secret_mount(tmp_path):
    _run([
        "docker", "dockerfile", "--name", "app",
        "--base", "python:3.12-slim",
        "--digest", "sha256:abc123", "--secret-mount", "pip_token",
        "--output-dir", str(tmp_path),
    ])
    content = (tmp_path / "Dockerfile").read_text()
    assert "python:3.12-slim@sha256:abc123" in content
    assert "--mount=type=secret,id=pip_token" in content


def test_compose_edge_service_loopback_rewrite(tmp_path):
    _run([
        "compose", "generate", "proj",
        "--service", "web:nginx:80", "--service", "db:postgres:5432",
        "--edge-service", "web",
        "--output-dir", str(tmp_path),
    ])
    content = (tmp_path / "docker-compose.yaml").read_text()
    assert "127.0.0.1:5432:5432" in content   # non-edge bound to loopback
    assert "127.0.0.1:80:80" not in content   # edge service left published
