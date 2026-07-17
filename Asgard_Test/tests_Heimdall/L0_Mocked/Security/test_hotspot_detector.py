"""
Tests for Heimdall Hotspot Detector Service (plan 08 Part A).

Exception-only hotspot discipline: exactly six pattern families, each a
question only extrinsic context can answer. Tests write real source code
to temporary files and run HotspotDetector against them.
"""

import tempfile
from pathlib import Path

import pytest

from Asgard.Heimdall.Security.Hotspots.models.hotspot_models import (
    PR_HOTSPOT_CAP,
    HotspotCategory,
    HotspotConfig,
    HotspotReport,
    ReviewPriority,
    ReviewStatus,
    SecurityHotspot,
)
from Asgard.Heimdall.Security.Hotspots.services.hotspot_detector import HotspotDetector
from Asgard.Heimdall.Security.Hotspots.services.pr_summary import (
    build_pr_hotspot_comments,
)


def _scan_source(code: str, filename: str = "app.py", config: HotspotConfig = None):
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / filename
        path.write_text(code)
        detector = HotspotDetector(config=config)
        return detector.scan(Path(tmpdir))


def _categories(report) -> set:
    return {h.category for h in report.hotspots}


class TestHotspotDetectorInitialization:
    def test_default_initialization(self):
        detector = HotspotDetector()
        assert detector.config is not None

    def test_custom_config_initialization(self):
        config = HotspotConfig(min_priority=ReviewPriority.HIGH)
        detector = HotspotDetector(config=config)
        assert detector.config.min_priority == ReviewPriority.HIGH.value

    def test_scan_nonexistent_path_raises(self):
        detector = HotspotDetector()
        with pytest.raises(FileNotFoundError):
            detector.scan(Path("/nonexistent/path/that/does/not/exist"))

    def test_empty_directory_returns_empty_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = HotspotDetector().scan(Path(tmpdir))
            assert report.total_hotspots == 0
            assert isinstance(report, HotspotReport)


class TestCategorySetDiscipline:
    """The enum is exactly the six defensible families (DEEPTHINK_10 s5)."""

    def test_exactly_six_families(self):
        assert len(HotspotCategory) == 6

    def test_cop_out_categories_removed(self):
        names = {c.name for c in HotspotCategory}
        for removed in ("REGEX_DOS", "SSRF", "PERMISSION_CHECK", "XXE",
                        "CRYPTO_USAGE", "DYNAMIC_EXECUTION", "COOKIE_CONFIG",
                        "INSECURE_RANDOM", "TLS_VERIFICATION"):
            assert removed not in names

    def test_no_acknowledged_risk_status(self):
        assert "ACKNOWLEDGED_RISK" not in {s.name for s in ReviewStatus}
        assert {s.value for s in ReviewStatus} == {"to_review", "safe_in_context", "fixed"}


class TestWeakHashing:
    def test_md5_call_detected(self):
        report = _scan_source("import hashlib\nh = hashlib.md5(data)\n")
        assert HotspotCategory.WEAK_HASHING.value in _categories(report)

    def test_sha1_call_detected(self):
        report = _scan_source("import hashlib\nh = hashlib.sha1(data)\n")
        assert HotspotCategory.WEAK_HASHING.value in _categories(report)

    def test_usedforsecurity_false_not_flagged(self):
        report = _scan_source(
            "import hashlib\nh = hashlib.md5(data, usedforsecurity=False)\n"
        )
        assert HotspotCategory.WEAK_HASHING.value not in _categories(report)

    def test_sha256_not_flagged(self):
        report = _scan_source("import hashlib\nh = hashlib.sha256(data)\n")
        assert HotspotCategory.WEAK_HASHING.value not in _categories(report)

    def test_bare_hashlib_import_not_flagged(self):
        """Generic 'any use of hashlib' flagging is a removed cop-out."""
        report = _scan_source("import hashlib\n")
        assert report.total_hotspots == 0


class TestStandardPRNG:
    def test_random_call_detected(self):
        report = _scan_source("import random\ntoken = random.randint(0, 99)\n")
        assert HotspotCategory.STANDARD_PRNG.value in _categories(report)

    def test_bare_random_import_not_flagged(self):
        report = _scan_source("import random\n")
        assert report.total_hotspots == 0

    def test_secrets_module_not_flagged(self):
        report = _scan_source("import secrets\nt = secrets.token_hex(16)\n")
        assert report.total_hotspots == 0


class TestDisabledTLS:
    def test_verify_false_kwarg_detected(self):
        report = _scan_source(
            "import requests\nrequests.get('https://x', verify=False)\n"
        )
        assert HotspotCategory.DISABLED_TLS.value in _categories(report)

    def test_unverified_context_detected(self):
        report = _scan_source("import ssl\nctx = ssl._create_unverified_context()\n")
        assert HotspotCategory.DISABLED_TLS.value in _categories(report)

    def test_verify_true_not_flagged(self):
        report = _scan_source(
            "import requests\nrequests.get('https://x', verify=True)\n"
        )
        assert HotspotCategory.DISABLED_TLS.value not in _categories(report)


class TestPermissiveBinding:
    def test_bind_all_interfaces_detected(self):
        report = _scan_source("app.run(host='0.0.0.0', port=8000)\n")
        assert HotspotCategory.PERMISSIVE_BINDING.value in _categories(report)

    def test_wildcard_cors_detected(self):
        report = _scan_source(
            "app.add_middleware(CORSMiddleware, allow_origins=['*'])\n"
        )
        assert HotspotCategory.PERMISSIVE_BINDING.value in _categories(report)

    def test_loopback_bind_not_flagged(self):
        report = _scan_source("app.run(host='127.0.0.1', port=8000)\n")
        assert HotspotCategory.PERMISSIVE_BINDING.value not in _categories(report)


class TestOpaqueDeserialization:
    def test_pickle_loads_detected(self):
        report = _scan_source("import pickle\nobj = pickle.loads(blob)\n")
        assert HotspotCategory.OPAQUE_DESERIALIZATION.value in _categories(report)

    def test_marshal_load_detected(self):
        report = _scan_source("import marshal\nobj = marshal.load(fh)\n")
        assert HotspotCategory.OPAQUE_DESERIALIZATION.value in _categories(report)

    def test_yaml_load_without_safeloader_detected(self):
        report = _scan_source("import yaml\ncfg = yaml.load(text)\n")
        assert HotspotCategory.OPAQUE_DESERIALIZATION.value in _categories(report)

    def test_yaml_load_with_safeloader_not_flagged(self):
        report = _scan_source(
            "import yaml\ncfg = yaml.load(text, Loader=yaml.SafeLoader)\n"
        )
        assert HotspotCategory.OPAQUE_DESERIALIZATION.value not in _categories(report)

    def test_yaml_safe_load_not_flagged(self):
        report = _scan_source("import yaml\ncfg = yaml.safe_load(text)\n")
        assert HotspotCategory.OPAQUE_DESERIALIZATION.value not in _categories(report)

    def test_pickle_is_high_priority(self):
        report = _scan_source("import pickle\nobj = pickle.loads(blob)\n")
        priorities = {
            h.review_priority for h in report.hotspots
            if h.category == HotspotCategory.OPAQUE_DESERIALIZATION.value
        }
        assert ReviewPriority.HIGH.value in priorities


class TestHazmatCrypto:
    def test_hazmat_import_detected(self):
        report = _scan_source(
            "from cryptography.hazmat.primitives.ciphers import Cipher\n"
        )
        assert HotspotCategory.HAZMAT_CRYPTO.value in _categories(report)

    def test_fernet_recipes_not_flagged(self):
        report = _scan_source("from cryptography.fernet import Fernet\n")
        assert report.total_hotspots == 0


class TestRemovedCopOutsStaySilent:
    """If the scanner lacks proof it emits a taint Finding or stays silent."""

    def test_eval_is_not_a_hotspot(self):
        report = _scan_source("eval(user_input)\n")
        assert report.total_hotspots == 0

    def test_variable_url_request_is_not_a_hotspot(self):
        report = _scan_source("import requests\nrequests.get(url)\n")
        assert report.total_hotspots == 0

    def test_os_chmod_is_not_a_hotspot(self):
        report = _scan_source("import os\nos.chmod('/tmp/f', 0o777)\n")
        assert report.total_hotspots == 0

    def test_nested_quantifier_regex_is_not_a_hotspot(self):
        report = _scan_source("import re\np = re.compile(r'(a+)+$')\n")
        assert report.total_hotspots == 0

    def test_xml_import_is_not_a_hotspot(self):
        report = _scan_source("import xml.etree.ElementTree as ET\n")
        assert report.total_hotspots == 0

    def test_cookie_config_is_not_a_hotspot(self):
        report = _scan_source("resp.set_cookie('sid', v, secure=False)\n")
        assert report.total_hotspots == 0


class TestNonPythonRegexFallback:
    def test_js_weak_hash_detected(self):
        report = _scan_source(
            "const h = crypto.createHash('md5').update(x);\n", filename="app.js"
        )
        assert HotspotCategory.WEAK_HASHING.value in _categories(report)

    def test_js_math_random_detected(self):
        report = _scan_source("const t = Math.random();\n", filename="app.js")
        assert HotspotCategory.STANDARD_PRNG.value in _categories(report)

    def test_go_insecure_skip_verify_detected(self):
        report = _scan_source(
            "cfg := &tls.Config{InsecureSkipVerify: true}\n", filename="main.go"
        )
        assert HotspotCategory.DISABLED_TLS.value in _categories(report)

    def test_python_ast_and_regex_deduplicated(self):
        """verify=False on a parsed Python file yields ONE hotspot, not two."""
        report = _scan_source(
            "import requests\nrequests.get('https://x', verify=False)\n"
        )
        tls = [
            h for h in report.hotspots
            if h.category == HotspotCategory.DISABLED_TLS.value
        ]
        assert len(tls) == 1


class TestTestContextRouting:
    """Hotspots in test code are contextually suppressed (plan 08 Part B)."""

    def _scan_in_tests_dir(self, code, filename="test_app.py", config=None):
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir) / "tests"
            tests_dir.mkdir()
            (tests_dir / filename).write_text(code)
            return HotspotDetector(config=config).scan(Path(tmpdir))

    def test_weak_hash_in_test_file_suppressed(self):
        report = self._scan_in_tests_dir("import hashlib\nh = hashlib.md5(b'x')\n")
        assert report.total_hotspots == 0
        assert report.suppressed_by_context_count == 1

    def test_suppressed_retained_with_include_test_context(self):
        config = HotspotConfig(include_test_context=True)
        report = self._scan_in_tests_dir(
            "import hashlib\nh = hashlib.md5(b'x')\n", config=config
        )
        assert report.total_hotspots == 1
        hotspot = report.hotspots[0]
        assert hotspot.suppressed_by_context is True
        assert hotspot.context_tag == "test_unit"

    def test_enforce_pragma_keeps_production_severity(self):
        report = self._scan_in_tests_dir(
            "import hashlib\nh = hashlib.md5(b'x')  # heimdall: enforce\n"
        )
        assert report.total_hotspots == 1
        assert report.hotspots[0].suppressed_by_context is False

    def test_strict_scan_paths_bypass_engine(self):
        config = HotspotConfig(strict_scan_paths=[r"tests/security/"])
        with tempfile.TemporaryDirectory() as tmpdir:
            sec_dir = Path(tmpdir) / "tests" / "security"
            sec_dir.mkdir(parents=True)
            (sec_dir / "test_crypto.py").write_text(
                "import hashlib\nh = hashlib.md5(b'x')\n"
            )
            report = HotspotDetector(config=config).scan(Path(tmpdir))
        assert report.total_hotspots == 1
        assert report.hotspots[0].context_tag == "production"

    def test_context_engine_disabled(self):
        config = HotspotConfig(test_context_enabled=False)
        report = self._scan_in_tests_dir(
            "import hashlib\nh = hashlib.md5(b'x')\n", config=config
        )
        assert report.total_hotspots == 1
        assert report.suppressed_by_context_count == 0

    def test_prod_file_not_suppressed(self):
        report = _scan_source("import hashlib\nh = hashlib.md5(b'x')\n")
        assert report.total_hotspots == 1
        assert report.hotspots[0].context_tag == "production"

    def test_deserialization_in_integration_tests_downgraded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir) / "tests" / "integration"
            d.mkdir(parents=True)
            (d / "test_load.py").write_text("import pickle\no = pickle.loads(b)\n")
            report = HotspotDetector().scan(Path(tmpdir))
        assert report.total_hotspots == 1
        hotspot = report.hotspots[0]
        assert hotspot.context_tag == "test_integration"
        assert hotspot.review_priority == ReviewPriority.LOW.value


class TestPRVolumeGuard:
    """>5 hotspots on one PR collapse to a single summary (DEEPTHINK_10)."""

    def _make(self, n):
        return [
            SecurityHotspot(
                file_path=f"/src/f{i}.py", line_number=i + 1,
                category=HotspotCategory.WEAK_HASHING,
                review_priority=ReviewPriority.MEDIUM,
                title=f"hotspot {i}",
            )
            for i in range(n)
        ]

    def test_cap_is_five(self):
        assert PR_HOTSPOT_CAP == 5

    def test_under_cap_inline_comments(self):
        comments = build_pr_hotspot_comments(self._make(3))
        assert len(comments.inline) == 3
        assert comments.summary == ""
        assert comments.collapsed is False

    def test_eight_hotspots_collapse_to_single_summary(self):
        comments = build_pr_hotspot_comments(self._make(8))
        assert comments.inline == []
        assert comments.collapsed is True
        assert "8" in comments.summary

    def test_suppressed_hotspots_never_decorate(self):
        hotspots = self._make(8)
        for h in hotspots:
            h.suppressed_by_context = True
        comments = build_pr_hotspot_comments(hotspots)
        assert comments.inline == [] and comments.summary == ""


class TestReportAggregation:
    def test_counts_by_priority_and_category(self):
        code = (
            "import hashlib, pickle\n"
            "h = hashlib.md5(d)\n"
            "o = pickle.loads(b)\n"
        )
        report = _scan_source(code)
        assert report.total_hotspots == 2
        assert report.high_priority_count == 1
        assert report.medium_priority_count == 1
        assert report.hotspots_by_category[HotspotCategory.WEAK_HASHING.value] == 1

    def test_min_priority_filter(self):
        config = HotspotConfig(min_priority=ReviewPriority.HIGH)
        code = "import random\nt = random.random()\n"  # LOW priority
        report = _scan_source(code, config=config)
        assert report.total_hotspots == 0

    def test_hotspot_defaults(self):
        report = _scan_source("import pickle\no = pickle.loads(b)\n")
        hotspot = report.hotspots[0]
        assert hotspot.review_status == ReviewStatus.TO_REVIEW.value
        assert hotspot.review_guidance
        assert hotspot.cwe_id == "CWE-502"
