"""Benchmark for the input-validation control-flow-barrier structural
checks (plan 07.12, RESEARCH_18): raw request access, Jinja2 autoescape,
mark_safe on tainted data, mass-assignment advisory, CWE-179 early
validation. Vulnerable/safe pairs per check.
"""
import tempfile
from pathlib import Path

from Asgard.Heimdall.Security.InputValidation.services.input_validation_scanner import (
    InputValidationScanner,
)
from Asgard.Heimdall.Security.InputValidation.models.input_validation_models import (
    InputValidationScanConfig,
)


def _scan_source(source: str):
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "app.py"
        file_path.write_text(source)
        config = InputValidationScanConfig(scan_path=file_path)
        return InputValidationScanner().scan(config)


def _hits(report, issue_type: str):
    return [f for f in report.findings if f.issue_type == issue_type]


def test_raw_django_post_access_without_barrier_flagged():
    report = _scan_source(
        "def view(request):\n"
        "    name = request.POST['name']\n"
        "    return name\n"
    )
    hits = _hits(report, "raw_request_access")
    assert hits
    assert hits[0].mechanism_id == "input_validation.raw_request_access"
    assert hits[0].severity == "MEDIUM"


def test_raw_django_post_access_with_barrier_downgraded():
    report = _scan_source(
        "def view(request):\n"
        "    form = MyForm(request.POST)\n"
        "    if form.is_valid():\n"
        "        data = form.cleaned_data\n"
        "    name = request.POST['name']\n"
        "    return name\n"
    )
    hits = _hits(report, "raw_request_access")
    assert hits
    assert hits[0].severity == "LOW"


def test_fastapi_raw_body_bypass_flagged():
    report = _scan_source(
        "async def endpoint(request):\n"
        "    raw = await request.body()\n"
        "    return raw\n"
    )
    assert _hits(report, "raw_body_bypass")


def test_jinja2_autoescape_disabled_flagged_critical():
    report = _scan_source(
        "from jinja2 import Environment\n"
        "env = Environment(autoescape=False)\n"
    )
    hits = _hits(report, "jinja2_autoescape_disabled")
    assert hits
    assert hits[0].severity == "CRITICAL"


def test_jinja2_autoescape_enabled_not_flagged():
    report = _scan_source(
        "from jinja2 import Environment, select_autoescape\n"
        "env = Environment(autoescape=select_autoescape(['html', 'xml']))\n"
    )
    assert not _hits(report, "jinja2_autoescape_disabled")


def test_mark_safe_on_variable_flagged():
    report = _scan_source(
        "from django.utils.safestring import mark_safe\n"
        "def view(user_input):\n"
        "    return mark_safe(user_input)\n"
    )
    hits = _hits(report, "mark_safe_tainted")
    assert hits
    assert hits[0].severity == "HIGH"


def test_mark_safe_on_string_literal_not_flagged():
    report = _scan_source(
        "from django.utils.safestring import mark_safe\n"
        "def view():\n"
        "    return mark_safe('<b>static</b>')\n"
    )
    assert not _hits(report, "mark_safe_tainted")


def test_mass_assignment_advisory_flagged_without_extra_forbid():
    report = _scan_source(
        "from pydantic import BaseModel\n\n"
        "class UserUpdate(BaseModel):\n"
        "    name: str = None\n"
        "    is_admin: bool = None\n"
    )
    hits = _hits(report, "mass_assignment_advisory")
    assert hits
    assert hits[0].is_advisory is True
    assert hits[0].severity == "LOW"


def test_mass_assignment_not_flagged_with_extra_forbid():
    report = _scan_source(
        "from pydantic import BaseModel, ConfigDict\n\n"
        "class UserUpdate(BaseModel):\n"
        "    model_config = ConfigDict(extra='forbid')\n"
        "    name: str = None\n"
    )
    assert not _hits(report, "mass_assignment_advisory")


def test_cwe179_early_validation_late_mutation_flagged():
    report = _scan_source(
        "def handle(token):\n"
        "    if len(token) < 100:\n"
        "        decoded = token.decode()\n"
        "        use(decoded)\n"
    )
    hits = _hits(report, "early_validation_late_mutation")
    assert hits
    assert hits[0].cwe_id == "CWE-179"


def test_every_finding_has_mechanism_id():
    report = _scan_source(
        "from django.utils.safestring import mark_safe\n"
        "def view(request, user_input):\n"
        "    name = request.POST['name']\n"
        "    return mark_safe(user_input)\n"
    )
    assert report.findings
    assert all(f.mechanism_id for f in report.findings)
