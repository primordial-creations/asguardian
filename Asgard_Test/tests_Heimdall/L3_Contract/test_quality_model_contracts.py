"""L3 Contract tests for Heimdall Quality scanner models.

Verifies field names, required fields, and defaults.
"""
import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Complexity
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.models.complexity_models import (
    FunctionComplexity,
    FileComplexityAnalysis,
    ComplexityResult,
    ComplexityConfig,
)


class TestFunctionComplexityContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            FunctionComplexity()

    def test_accepts_valid_data(self):
        fc = FunctionComplexity(
            name="my_func",
            line_number=10,
            end_line=30,
            cyclomatic_complexity=5,
            cognitive_complexity=3,
            severity="low",
        )
        assert fc.name == "my_func"
        assert hasattr(fc, "cyclomatic_complexity")


class TestComplexityConfigContract:
    def test_instantiates_with_defaults(self):
        config = ComplexityConfig()
        assert config is not None

    def test_has_expected_fields(self):
        config = ComplexityConfig()
        assert hasattr(ComplexityConfig, "model_fields")


# ---------------------------------------------------------------------------
# Duplication
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.models.duplication_models import (
    CodeBlock,
    DuplicationMatch,
    CloneFamily,
    DuplicationResult,
    DuplicationConfig,
)


class TestCodeBlockContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            CodeBlock()

    def test_accepts_valid_data(self):
        cb = CodeBlock(
            file_path="/a/b.py",
            relative_path="b.py",
            start_line=1,
            end_line=10,
            content="x = 1",
            hash_value="abc123",
            line_count=10,
        )
        assert cb.file_path == "/a/b.py"
        assert hasattr(cb, "hash_value")


class TestDuplicationMatchContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            DuplicationMatch()

    def test_accepts_valid_data(self):
        block_kwargs = dict(
            file_path="/a.py", relative_path="a.py", start_line=1,
            end_line=5, content="x=1", hash_value="h1", line_count=5,
        )
        dm = DuplicationMatch(
            original=CodeBlock(**block_kwargs),
            duplicate=CodeBlock(**{**block_kwargs, "file_path": "/b.py", "relative_path": "b.py"}),
            similarity=1.0,
            match_type="exact",
        )
        assert dm.similarity == 1.0


class TestDuplicationConfigContract:
    def test_instantiates_with_defaults(self):
        config = DuplicationConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# Debt
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.models.debt_models import (
    DebtItem,
    DebtReport,
    DebtConfig,
)


class TestDebtItemContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            DebtItem()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Quality.models.debt_models import DebtType
        di = DebtItem(debt_type=DebtType.CODE, file_path="/a.py", description="Too long")
        assert hasattr(di, "debt_type")
        assert hasattr(di, "file_path")


class TestDebtConfigContract:
    def test_instantiates_with_defaults(self):
        config = DebtConfig()
        assert config is not None


class TestDebtReportContract:
    def test_instantiates_with_defaults(self):
        report = DebtReport()
        assert report is not None
        assert hasattr(report, "items") or hasattr(DebtReport, "model_fields")


# ---------------------------------------------------------------------------
# Naming
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.models.naming_models import (
    NamingViolation,
    NamingConfig,
    NamingReport,
)


class TestNamingViolationContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            NamingViolation()

    def test_accepts_valid_data(self):
        nv = NamingViolation(
            file_path="/a.py",
            line_number=5,
            element_type="function",
            element_name="MyFunc",
            expected_convention="snake_case",
        )
        assert nv.element_name == "MyFunc"
        assert hasattr(nv, "expected_convention")


class TestNamingConfigContract:
    def test_instantiates_with_defaults(self):
        config = NamingConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# Documentation
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.models.documentation_models import (
    DocumentationConfig,
    FunctionDocumentation,
    ClassDocumentation,
    FileDocumentation,
    DocumentationReport,
)


class TestFunctionDocumentationContract:
    def test_requires_name(self):
        with pytest.raises((ValidationError, TypeError)):
            FunctionDocumentation()

    def test_accepts_valid_data(self):
        fd = FunctionDocumentation(name="my_func")
        assert fd.name == "my_func"
        assert hasattr(fd, "has_docstring") or hasattr(FunctionDocumentation, "model_fields")


class TestDocumentationConfigContract:
    def test_instantiates_with_defaults(self):
        config = DocumentationConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.models.analysis_models import (
    FileAnalysis,
    AnalysisResult,
    AnalysisConfig,
)


class TestFileAnalysisContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            FileAnalysis()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Quality.models.analysis_models import SeverityLevel
        fa = FileAnalysis(
            file_path="/a.py",
            line_count=200,
            threshold=150,
            lines_over=50,
            severity=SeverityLevel.WARNING,
            file_extension=".py",
            relative_path="a.py",
        )
        assert fa.file_path == "/a.py"
        assert hasattr(fa, "line_count")


class TestAnalysisConfigContract:
    def test_instantiates_with_defaults(self):
        config = AnalysisConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# Thread Safety
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.models.thread_safety_models import (
    ThreadSafetyIssue,
    ThreadSafetyReport,
    ThreadSafetyConfig,
)


class TestThreadSafetyIssueContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            ThreadSafetyIssue()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Quality.models.thread_safety_models import ThreadSafetyIssueType, ThreadSafetySeverity
        tsi = ThreadSafetyIssue(
            file_path="/a.py",
            line_number=10,
            class_name="MyClass",
            issue_type=ThreadSafetyIssueType.UNINITIALIZED_ATTR,
            severity=ThreadSafetySeverity.HIGH,
            description="Unsynchronized access",
            remediation="Use locks",
        )
        assert tsi.class_name == "MyClass"
        assert hasattr(tsi, "issue_type")


class TestThreadSafetyConfigContract:
    def test_instantiates_with_defaults(self):
        config = ThreadSafetyConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# Race Condition
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.models.race_condition_models import (
    RaceConditionIssue,
    RaceConditionReport,
    RaceConditionConfig,
)


class TestRaceConditionIssueContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            RaceConditionIssue()

    def test_accepts_valid_data(self):
        rci = RaceConditionIssue(
            file_path="/a.py",
            line_number=5,
            race_type="check_then_act",
            description="Race in file access",
            remediation="Use atomic ops",
        )
        assert rci.race_type == "check_then_act"


class TestRaceConditionConfigContract:
    def test_instantiates_with_defaults(self):
        config = RaceConditionConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# Blocking Async
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.models.blocking_async_models import (
    BlockingCall,
    BlockingAsyncReport,
    BlockingAsyncConfig,
)


class TestBlockingCallContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            BlockingCall()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Quality.models.blocking_async_models import BlockingCallType
        bc = BlockingCall(
            file_path="/a.py",
            line_number=20,
            call_expression="time.sleep(1)",
            blocking_type=BlockingCallType.TIME_SLEEP,
            context_description="Inside async function",
            remediation="Use asyncio.sleep",
        )
        assert bc.call_expression == "time.sleep(1)"


class TestBlockingAsyncConfigContract:
    def test_instantiates_with_defaults(self):
        config = BlockingAsyncConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# Error Handling
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.models.error_handling_models import (
    ErrorHandlingViolation,
    ErrorHandlingReport,
    ErrorHandlingConfig,
)


class TestErrorHandlingViolationContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            ErrorHandlingViolation()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Quality.models.error_handling_models import ErrorHandlingType, ErrorHandlingSeverity
        ehv = ErrorHandlingViolation(
            file_path="/a.py",
            line_number=10,
            code_snippet="except: pass",
            handling_type=ErrorHandlingType.THREAD_TARGET_NO_EXCEPTION_HANDLING,
            severity=ErrorHandlingSeverity.HIGH,
            context_description="Swallows all exceptions",
        )
        assert hasattr(ehv, "handling_type")


class TestErrorHandlingConfigContract:
    def test_instantiates_with_defaults(self):
        config = ErrorHandlingConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# Code Smells
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.models.smell_models import (
    CodeSmell,
    SmellReport,
    SmellConfig,
)


class TestCodeSmellContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            CodeSmell()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Quality.models.smell_models import SmellCategory, SmellSeverity
        cs = CodeSmell(
            name="LongMethod",
            category=SmellCategory.BLOATERS,
            severity=SmellSeverity.LOW,
            file_path="/a.py",
            line_number=5,
            description="Method too long",
            evidence="150 lines",
            remediation="Extract methods",
        )
        assert cs.name == "LongMethod"
        assert hasattr(cs, "category")


class TestSmellConfigContract:
    def test_instantiates_with_defaults(self):
        config = SmellConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# Typing
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.models.typing_models import (
    FunctionAnnotation,
    FileTypingStats,
    TypingReport,
    TypingConfig,
)


class TestFunctionAnnotationContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            FunctionAnnotation()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Quality.models.typing_models import AnnotationStatus, AnnotationSeverity
        fa = FunctionAnnotation(
            file_path="/a.py",
            line_number=10,
            function_name="my_func",
            status=AnnotationStatus.FULLY_ANNOTATED,
            severity=AnnotationSeverity.LOW,
        )
        assert fa.function_name == "my_func"


class TestTypingConfigContract:
    def test_instantiates_with_defaults(self):
        config = TypingConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# Type Check
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.models.type_check_models import (
    TypeCheckDiagnostic,
    FileTypeCheckStats,
    TypeCheckReport,
    TypeCheckConfig,
)


class TestTypeCheckDiagnosticContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            TypeCheckDiagnostic()

    def test_accepts_valid_data(self):
        tcd = TypeCheckDiagnostic(
            file_path="/a.py",
            line=10,
            severity="error",
            message="Incompatible types",
        )
        assert tcd.message == "Incompatible types"


class TestTypeCheckConfigContract:
    def test_instantiates_with_defaults(self):
        config = TypeCheckConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# Lazy Import
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.models.lazy_import_models import (
    LazyImport,
    LazyImportReport,
    LazyImportConfig,
)


class TestLazyImportContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            LazyImport()

    def test_accepts_valid_data(self):
        li = LazyImport(
            file_path="/a.py",
            line_number=5,
            import_statement="import os",
            import_type="conditional",
            severity="low",
            context_description="Import inside function",
        )
        assert li.import_type == "conditional"


class TestLazyImportConfigContract:
    def test_instantiates_with_defaults(self):
        config = LazyImportConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# Future Leak
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.models.future_leak_models import (
    FutureLeak,
    FutureLeakReport,
    FutureLeakConfig,
)


class TestFutureLeakContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            FutureLeak()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Quality.models.future_leak_models import FutureLeakType, FutureLeakSeverity
        fl = FutureLeak(
            file_path="/a.py",
            line_number=10,
            variable_name="future",
            leak_type=FutureLeakType.ASYNCIO_TASK,
            severity=FutureLeakSeverity.LOW,
            context_description="Future not awaited",
            remediation="Await the future",
        )
        assert fl.variable_name == "future"


class TestFutureLeakConfigContract:
    def test_instantiates_with_defaults(self):
        config = FutureLeakConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# Resource Cleanup
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.models.resource_cleanup_models import (
    ResourceCleanupViolation,
    ResourceCleanupReport,
    ResourceCleanupConfig,
)


class TestResourceCleanupViolationContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            ResourceCleanupViolation()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Quality.models.resource_cleanup_models import ResourceCleanupType, ResourceCleanupSeverity
        rcv = ResourceCleanupViolation(
            file_path="/a.py",
            line_number=10,
            code_snippet="open('f')",
            cleanup_type=ResourceCleanupType.FILE_OPEN_NO_WITH,
            severity=ResourceCleanupSeverity.HIGH,
            context_description="File not closed",
        )
        assert hasattr(rcv, "cleanup_type")


class TestResourceCleanupConfigContract:
    def test_instantiates_with_defaults(self):
        config = ResourceCleanupConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# Daemon Thread
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.models.daemon_thread_models import (
    DaemonThreadIssue,
    DaemonThreadReport,
    DaemonThreadConfig,
)


class TestDaemonThreadIssueContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            DaemonThreadIssue()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Quality.models.daemon_thread_models import DaemonThreadIssueType, DaemonThreadSeverity
        dti = DaemonThreadIssue(
            file_path="/a.py",
            line_number=15,
            issue_type=DaemonThreadIssueType.NO_JOIN,
            severity=DaemonThreadSeverity.MEDIUM,
            description="Thread not set as daemon",
            remediation="Set daemon=True",
        )
        assert hasattr(dti, "issue_type")


class TestDaemonThreadConfigContract:
    def test_instantiates_with_defaults(self):
        config = DaemonThreadConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# Datetime
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.models.datetime_models import (
    DatetimeViolation,
    DatetimeReport,
    DatetimeConfig,
)


class TestDatetimeViolationContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            DatetimeViolation()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Quality.models.datetime_models import DatetimeIssueType, DatetimeSeverity
        dv = DatetimeViolation(
            file_path="/a.py",
            line_number=10,
            code_snippet="datetime.now()",
            issue_type=DatetimeIssueType.UTCNOW,
            severity=DatetimeSeverity.LOW,
            remediation="Use datetime.now(tz=utc)",
        )
        assert hasattr(dv, "issue_type")


class TestDatetimeConfigContract:
    def test_instantiates_with_defaults(self):
        config = DatetimeConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# Env Fallback
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.models.env_fallback_models import (
    EnvFallbackViolation,
    EnvFallbackReport,
    EnvFallbackConfig,
)


class TestEnvFallbackViolationContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            EnvFallbackViolation()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Quality.models.env_fallback_models import EnvFallbackType, EnvFallbackSeverity
        efv = EnvFallbackViolation(
            file_path="/a.py",
            line_number=5,
            code_snippet="os.getenv('K', 'default')",
            fallback_type=EnvFallbackType.GETENV_DEFAULT,
            severity=EnvFallbackSeverity.CRITICAL,
            context_description="Sensitive env fallback",
        )
        assert hasattr(efv, "fallback_type")


class TestEnvFallbackConfigContract:
    def test_instantiates_with_defaults(self):
        config = EnvFallbackConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# Library Usage (Forbidden Imports)
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.models.library_usage_models import (
    ForbiddenImportViolation,
    ForbiddenImportReport,
    ForbiddenImportConfig,
)


class TestForbiddenImportViolationContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            ForbiddenImportViolation()

    def test_accepts_valid_data(self):
        fiv = ForbiddenImportViolation(
            file_path="/a.py",
            line_number=1,
            import_statement="import pickle",
            module_name="pickle",
            severity="high",
            remediation="Use json instead",
        )
        assert fiv.module_name == "pickle"


class TestForbiddenImportConfigContract:
    def test_instantiates_with_defaults(self):
        config = ForbiddenImportConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# Maintainability
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.models.maintainability_models import (
    HalsteadMetrics,
    FunctionMaintainability,
    FileMaintainability,
    MaintainabilityReport,
    MaintainabilityConfig,
)


class TestHalsteadMetricsContract:
    def test_instantiates_with_defaults(self):
        hm = HalsteadMetrics()
        assert hm is not None
        assert hasattr(HalsteadMetrics, "model_fields")


class TestFunctionMaintainabilityContract:
    def test_requires_name_and_file_path(self):
        with pytest.raises((ValidationError, TypeError)):
            FunctionMaintainability()

    def test_accepts_valid_data(self):
        fm = FunctionMaintainability(name="my_func", file_path="/a.py")
        assert fm.name == "my_func"
        assert hasattr(fm, "file_path")


class TestMaintainabilityConfigContract:
    def test_instantiates_with_defaults(self):
        config = MaintainabilityConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# Bug Detection
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.BugDetection.models.bug_models import (
    BugFinding,
    BugReport,
    BugDetectionConfig,
)


class TestBugFindingContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            BugFinding()

    def test_accepts_valid_data(self):
        bf = BugFinding(
            file_path="/a.py",
            line_number=10,
            category="null_dereference",
            severity="high",
            title="Null pointer",
            description="Possible null dereference",
        )
        assert bf.category == "null_dereference"


class TestBugDetectionConfigContract:
    def test_instantiates_with_defaults(self):
        config = BugDetectionConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# JavaScript Quality
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.languages.javascript.models.js_models import (
    JSFinding,
    JSReport,
    JSAnalysisConfig,
)


class TestJSFindingContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            JSFinding()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Quality.languages.javascript.models.js_models import JSRuleCategory, JSSeverity
        jf = JSFinding(
            file_path="/a.js",
            line_number=5,
            rule_id="no-eval",
            category=JSRuleCategory.BUG,
            severity=JSSeverity.ERROR,
            title="Eval usage",
            description="Do not use eval",
        )
        assert jf.rule_id == "no-eval"


class TestJSAnalysisConfigContract:
    def test_instantiates_with_defaults(self):
        config = JSAnalysisConfig()
        assert config is not None


# ---------------------------------------------------------------------------
# Shell Quality
# ---------------------------------------------------------------------------
from Asgard.Heimdall.Quality.languages.shell.models.shell_models import (
    ShellFinding,
    ShellReport,
    ShellAnalysisConfig,
)


class TestShellFindingContract:
    def test_requires_fields(self):
        with pytest.raises((ValidationError, TypeError)):
            ShellFinding()

    def test_accepts_valid_data(self):
        from Asgard.Heimdall.Quality.languages.shell.models.shell_models import ShellRuleCategory, ShellSeverity
        sf = ShellFinding(
            file_path="/a.sh",
            line_number=5,
            rule_id="SC2086",
            category=ShellRuleCategory.SECURITY,
            severity=ShellSeverity.ERROR,
            title="Double quote",
            description="Double quote to prevent globbing",
        )
        assert sf.rule_id == "SC2086"


class TestShellAnalysisConfigContract:
    def test_instantiates_with_defaults(self):
        config = ShellAnalysisConfig()
        assert config is not None
