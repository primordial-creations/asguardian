"""Benchmark corpus for the TOCTOU/race-condition AST detector (plan 07.7).

Vulnerable/safe pairs for the two canonical patterns: exists()-then-open()
file races, and ORM get/mutate/save without select_for_update(). Uses
``tempfile.TemporaryDirectory`` (not pytest's ``tmp_path``) so paths don't
carry a ``test_*`` segment that the test-context engine would treat as
TEST_UNIT and downgrade confidence on -- these fixtures assert on
PRODUCTION-context severity/confidence.
"""
import tempfile
from pathlib import Path

from Asgard.Heimdall.Security.RaceCondition.services.race_condition_detector import (
    RaceConditionDetector,
)
from Asgard.Heimdall.Security.RaceCondition.models.race_condition_models import (
    RaceConditionScanConfig,
)


def _scan(code: str):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "app.py").write_text(code)
        return RaceConditionDetector().scan(RaceConditionScanConfig(scan_path=tmp_path))


def test_exists_then_write_open_is_flagged_medium():
    report = _scan(
        "import os\n"
        "def save(path, data):\n"
        "    if not os.path.exists(path):\n"
        "        with open(path, 'w') as f:\n"
        "            f.write(data)\n"
    )
    hits = [f for f in report.findings if f.issue_type == "toctou_exists_then_open"]
    assert hits, "exists()-then-open('w') is the canonical TOCTOU file race"
    assert hits[0].severity == "MEDIUM"
    assert hits[0].mechanism_id == "race_condition.toctou_file"


def test_exists_then_read_open_is_flagged_low_not_medium():
    report = _scan(
        "import os\n"
        "def read(path):\n"
        "    if os.path.exists(path):\n"
        "        with open(path) as f:\n"
        "            return f.read()\n"
    )
    hits = [f for f in report.findings if f.issue_type == "toctou_exists_then_open"]
    assert hits
    assert hits[0].severity == "LOW", "read-mode race is weaker than write-mode -- must not over-claim MEDIUM"


def test_open_without_prior_exists_check_is_not_flagged():
    report = _scan(
        "def read(path):\n"
        "    try:\n"
        "        with open(path) as f:\n"
        "            return f.read()\n"
        "    except FileNotFoundError:\n"
        "        return None\n"
    )
    assert not any(f.issue_type == "toctou_exists_then_open" for f in report.findings)


def test_get_mutate_save_without_select_for_update_is_flagged():
    report = _scan(
        "from django.db import transaction\n"
        "def withdraw(account_id, amount):\n"
        "    with transaction.atomic():\n"
        "        acct = Account.objects.get(pk=account_id)\n"
        "        acct.balance -= amount\n"
        "        acct.save()\n"
    )
    hits = [f for f in report.findings if f.issue_type == "toctou_orm_get_mutate_save"]
    assert hits, "get/mutate/save inside atomic() without select_for_update() is the canonical ORM race"
    assert hits[0].mechanism_id == "race_condition.toctou_orm"


def test_get_mutate_save_with_select_for_update_in_atomic_is_not_flagged_as_unsafe():
    report = _scan(
        "from django.db import transaction\n"
        "def withdraw(account_id, amount):\n"
        "    with transaction.atomic():\n"
        "        acct = Account.objects.select_for_update().get(pk=account_id)\n"
        "        acct.balance -= amount\n"
        "        acct.save()\n"
    )
    assert not any(f.issue_type == "toctou_orm_get_mutate_save" for f in report.findings)
    assert not any(f.issue_type == "select_for_update_without_atomic" for f in report.findings)


def test_select_for_update_without_atomic_is_flagged_as_meaningless_lock():
    report = _scan(
        "def withdraw(account_id, amount):\n"
        "    acct = Account.objects.select_for_update().get(pk=account_id)\n"
        "    acct.balance -= amount\n"
        "    acct.save()\n"
    )
    hits = [f for f in report.findings if f.issue_type == "select_for_update_without_atomic"]
    assert hits, "select_for_update() outside a transaction takes no durable lock"


def test_mktemp_is_flagged_for_non_python_language_fallback():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "app.rb").write_text("Tempfile.mktemp('foo')\n")
        report = RaceConditionDetector().scan(RaceConditionScanConfig(scan_path=tmp_path))
    assert any(f.issue_type == "mktemp_toctou" for f in report.findings)


def test_toctou_never_reaches_high_or_critical_severity():
    report = _scan(
        "import os\n"
        "def save(path, data):\n"
        "    if not os.path.exists(path):\n"
        "        with open(path, 'w') as f:\n"
        "            f.write(data)\n"
    )
    assert all(f.severity in ("LOW", "MEDIUM") for f in report.findings), (
        "plan 07.7: TOCTOU is precision-first and never gate-blocking -- "
        "HIGH/CRITICAL would wrongly claim confirmed exploitability"
    )
