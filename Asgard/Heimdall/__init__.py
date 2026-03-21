"""
Heimdall - Code Quality Control and Analysis

Named after the Norse watchman god who guards Bifrost and can see and hear
everything across all realms. Like its namesake, Heimdall watches over your
codebase for quality issues, security vulnerabilities, and performance problems.

Subpackages:
- Quality: Code metrics, complexity, duplication, code smells, technical debt
- Security: Vulnerability scanning, secrets detection, injection patterns
- Performance: Memory profiling, CPU analysis, database optimization
- OOP: Object-oriented metrics (CBO, DIT, LCOM, RFC, WMC)
- Dependencies: Dependency graphs, circular detection, modularity analysis
- Architecture: SOLID validation, layer compliance, pattern detection
- Coverage: Test coverage gaps, test suggestions, class coverage
- Ratings: A-E letter ratings for maintainability, reliability, and security
- QualityGate: Condition-based gate evaluation against analysis results

Usage:
    python -m Heimdall --help
    python -m Heimdall quality analyze ./src
    python -m Heimdall security scan ./src
    python -m Heimdall performance scan ./src
    python -m Heimdall oop analyze ./src
    python -m Heimdall dependencies analyze ./src
    python -m Heimdall architecture analyze ./src
    python -m Heimdall coverage analyze ./src
    python -m Heimdall audit ./src

Programmatic Usage:
    from Heimdall.Quality import FileAnalyzer, AnalysisConfig
    from Heimdall.Security import StaticSecurityService, SecurityScanConfig
    from Heimdall.Performance import StaticPerformanceService, PerformanceScanConfig
    from Heimdall.OOP import OOPAnalyzer, OOPConfig
    from Heimdall.Dependencies import DependencyAnalyzer, DependencyConfig
    from Heimdall.Architecture import ArchitectureAnalyzer, ArchitectureConfig
    from Heimdall.Coverage import CoverageAnalyzer, CoverageConfig

    # Quality Analysis
    config = AnalysisConfig(threshold=300)
    analyzer = FileAnalyzer(config)
    result = analyzer.analyze()

    # Security Analysis
    security_service = StaticSecurityService()
    security_report = security_service.scan("./src")
    print(f"Security Score: {security_report.security_score}/100")

    # Performance Analysis
    perf_service = StaticPerformanceService()
    perf_report = perf_service.scan("./src")
    print(f"Performance Score: {perf_report.performance_score}/100")

    # OOP Analysis
    oop_analyzer = OOPAnalyzer()
    oop_report = oop_analyzer.analyze("./src")
    print(f"Classes Analyzed: {oop_report.total_classes}")

    # Dependency Analysis
    dep_analyzer = DependencyAnalyzer()
    dep_report = dep_analyzer.analyze("./src")
    print(f"Circular Dependencies: {dep_report.total_cycles}")

    # Architecture Analysis
    arch_analyzer = ArchitectureAnalyzer()
    arch_report = arch_analyzer.analyze("./src")
    print(f"SOLID Violations: {arch_report.total_violations}")

    # Coverage Analysis
    cov_analyzer = CoverageAnalyzer()
    cov_report = cov_analyzer.analyze("./src")
    print(f"Coverage Gaps: {cov_report.total_gaps}")
"""

__version__ = "1.5.0"
__author__ = "Asgard Contributors"

# Package metadata
PACKAGE_INFO = {
    "name": "Heimdall",
    "version": __version__,
    "description": "Code quality control package",
    "author": __author__,
    "sub_packages": [
        "Quality - Code metrics, complexity, duplication, smells, technical debt",
        "Security - Vulnerability scanning, secrets detection, injection patterns",
        "Performance - Memory profiling, CPU analysis, database optimization",
        "OOP - Object-oriented metrics (CBO, DIT, LCOM, RFC, WMC)",
        "Dependencies - Dependency graphs, circular detection, modularity analysis",
        "Architecture - SOLID validation, layer compliance, pattern detection",
        "Coverage - Test coverage gaps, test suggestions, class coverage",
        "Profiles - Quality profile management (rule sets with inheritance)",
        "Issues - Issue lifecycle tracking (SQLite-backed, status transitions, git blame)",
        "CodeFix - Template-based code fix suggestions for rule violations",
    ]
}

# Import subpackages
from . import Quality
from . import Security
from . import Performance
from . import OOP
from . import Dependencies
from . import Architecture
from . import Coverage
from . import Ratings
from . import Profiles
from . import Issues
from . import CodeFix

# Re-export commonly used items from Quality for convenience
from Asgard.Heimdall.Quality import (
    AnalysisConfig,
    AnalysisResult,
    FileAnalysis,
    FileAnalyzer,
    SeverityLevel,
)

# Re-export commonly used items from Security for convenience
from Asgard.Heimdall.Security import (
    SecurityReport,
    SecurityScanConfig,
    SecuritySeverity,
    StaticSecurityService,
)

# Re-export commonly used items from Performance for convenience
from Asgard.Heimdall.Performance import (
    PerformanceReport,
    PerformanceScanConfig,
    PerformanceSeverity,
    StaticPerformanceService,
)

# Re-export commonly used items from OOP for convenience
from Asgard.Heimdall.OOP import (
    OOPConfig,
    OOPReport,
    ClassOOPMetrics,
    OOPAnalyzer,
)

# Re-export commonly used items from Dependencies for convenience
from Asgard.Heimdall.Dependencies import (
    DependencyConfig,
    DependencyReport,
    CircularDependency,
    DependencyAnalyzer,
)

# Re-export commonly used items from Architecture for convenience
from Asgard.Heimdall.Architecture import (
    ArchitectureConfig,
    ArchitectureReport,
    HexagonalAnalyzer,
    HexagonalReport,
    SOLIDReport,
    ArchitectureAnalyzer,
)

# Re-export commonly used items from Coverage for convenience
from Asgard.Heimdall.Coverage import (
    CoverageConfig,
    CoverageReport,
    CoverageGap,
    CoverageAnalyzer,
)

# Re-export commonly used items from Ratings for convenience
from Asgard.Heimdall.Ratings import (
    LetterRating,
    ProjectRatings,
    RatingsCalculator,
    RatingsConfig,
)

# Re-export commonly used items from QualityGate for convenience
from Asgard.Heimdall.QualityGate import (
    MetricType,
    QualityGate,
    QualityGateEvaluator,
    QualityGateResult,
)

# Re-export commonly used items from Profiles for convenience
from Asgard.Heimdall.Profiles import (
    ProfileManager,
    QualityProfile,
    RuleConfig,
)

# Re-export commonly used items from Issues for convenience
from Asgard.Heimdall.Issues import (
    IssueStatus,
    IssueTracker,
    TrackedIssue,
)

# Re-export commonly used items from CodeFix for convenience
from Asgard.Heimdall.CodeFix import (
    CodeFixService,
    CodeFixReport,
    FixSuggestion,
)

__all__ = [
    # Subpackages
    "Issues",
    "Quality",
    "Security",
    "Performance",
    "OOP",
    "Dependencies",
    "Architecture",
    "Coverage",
    "Ratings",
    "QualityGate",
    # Quality exports
    "AnalysisConfig",
    "AnalysisResult",
    "FileAnalysis",
    "FileAnalyzer",
    "SeverityLevel",
    # Security exports
    "SecurityReport",
    "SecurityScanConfig",
    "SecuritySeverity",
    "StaticSecurityService",
    # Performance exports
    "PerformanceReport",
    "PerformanceScanConfig",
    "PerformanceSeverity",
    "StaticPerformanceService",
    # OOP exports
    "OOPConfig",
    "OOPReport",
    "ClassOOPMetrics",
    "OOPAnalyzer",
    # Dependencies exports
    "DependencyConfig",
    "DependencyReport",
    "CircularDependency",
    "DependencyAnalyzer",
    # Architecture exports
    "ArchitectureConfig",
    "ArchitectureReport",
    "HexagonalAnalyzer",
    "HexagonalReport",
    "SOLIDReport",
    "ArchitectureAnalyzer",
    # Coverage exports
    "CoverageConfig",
    "CoverageReport",
    "CoverageGap",
    "CoverageAnalyzer",
    # Ratings exports
    "LetterRating",
    "ProjectRatings",
    "RatingsCalculator",
    "RatingsConfig",
    # QualityGate exports
    "MetricType",
    "QualityGate",
    "QualityGateEvaluator",
    "QualityGateResult",
    # Profiles exports
    "Profiles",
    "ProfileManager",
    "QualityProfile",
    "RuleConfig",
    # Issues exports
    "IssueStatus",
    "IssueTracker",
    "TrackedIssue",
    # CodeFix exports
    "CodeFix",
    "CodeFixReport",
    "CodeFixService",
    "FixSuggestion",
]
