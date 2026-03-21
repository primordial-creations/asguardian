"""
Heimdall Quality - Code Quality Analysis

This module provides code quality analysis tools including:
- File length analysis (line count thresholds)
- Cyclomatic complexity analysis
- Cognitive complexity analysis
- Code duplication detection
- Code smell detection (Martin Fowler's taxonomy)
- Technical debt calculation
- Maintainability index (Microsoft formula)
- Comment density and documentation coverage
- Naming convention enforcement (PEP 8)

Usage:
    python -m Heimdall quality analyze ./src
    python -m Heimdall quality file-length ./src
    python -m Heimdall quality complexity ./src
    python -m Heimdall quality duplication ./src
    python -m Heimdall quality smells ./src
    python -m Heimdall quality debt ./src
    python -m Heimdall quality maintainability ./src
    python -m Heimdall quality documentation ./src
    python -m Heimdall quality naming ./src

Programmatic Usage:
    from Heimdall.Quality import FileAnalyzer, AnalysisConfig
    from Heimdall.Quality import ComplexityAnalyzer, ComplexityConfig
    from Heimdall.Quality import DuplicationDetector, DuplicationConfig
    from Heimdall.Quality import CodeSmellDetector, SmellConfig
    from Heimdall.Quality import TechnicalDebtAnalyzer, DebtConfig
    from Heimdall.Quality import MaintainabilityAnalyzer, MaintainabilityConfig
"""

__version__ = "1.0.0"
__author__ = "Asgard Contributors"

from Asgard.Heimdall.Quality._quality_models_imports import (
    AnalysisConfig,
    AnalysisResult,
    FileAnalysis,
    SeverityLevel,
    ComplexityConfig,
    ComplexityResult,
    ComplexitySeverity,
    FileComplexityAnalysis,
    FunctionComplexity,
    CloneFamily,
    CodeBlock,
    DuplicationConfig,
    DuplicationMatch,
    DuplicationResult,
    DuplicationSeverity,
    DuplicationType,
    CodeSmell,
    SmellCategory,
    SmellConfig,
    SmellReport,
    SmellSeverity,
    SmellThresholds,
    DebtConfig,
    DebtItem,
    DebtReport,
    DebtSeverity,
    DebtType,
    EffortModels,
    InterestRates,
    ROIAnalysis,
    TimeHorizon,
    TimeProjection,
    FileMaintainability,
    FunctionMaintainability,
    HalsteadMetrics,
    LanguageProfile,
    LanguageWeights,
    MaintainabilityConfig,
    MaintainabilityLevel,
    MaintainabilityReport,
    MaintainabilityThresholds,
    LazyImport,
    LazyImportConfig,
    LazyImportReport,
    LazyImportSeverity,
    LazyImportType,
    EnvFallbackConfig,
    EnvFallbackReport,
    EnvFallbackSeverity,
    EnvFallbackType,
    EnvFallbackViolation,
    SyntaxFileAnalysis,
    LinterType,
    SyntaxConfig,
    SyntaxIssue,
    SyntaxResult,
    SyntaxSeverity,
    DocumentationConfig,
    DocumentationReport,
    DocClassDocumentation,
    DocFunctionDocumentation,
    FileDocumentation,
    NamingConfig,
    NamingConvention,
    NamingViolation,
    NamingReport,
    FileTypeCheckStats,
    TypeCheckCategory,
    TypeCheckConfig,
    TypeCheckDiagnostic,
    TypeCheckReport,
    TypeCheckSeverity,
)
from Asgard.Heimdall.Quality._quality_services_imports import (
    FileAnalyzer,
    ComplexityAnalyzer,
    DuplicationDetector,
    CodeSmellDetector,
    TechnicalDebtAnalyzer,
    MaintainabilityAnalyzer,
    LazyImportScanner,
    EnvFallbackScanner,
    SyntaxChecker,
    DocumentationScanner,
    NamingConventionScanner,
    TypeChecker,
    BugCategory,
    BugDetectionConfig,
    BugDetector,
    BugFinding,
    BugReport,
    BugSeverity,
    NullDereferenceDetector,
    UnreachableCodeDetector,
    JSAnalysisConfig,
    JSAnalyzer,
    JSFinding,
    JSReport,
    JSRuleCategory,
    JSSeverity,
    TSAnalyzer,
    ShellAnalysisConfig,
    ShellAnalyzer,
    ShellFinding,
    ShellReport,
    ShellRuleCategory,
    ShellSeverity,
)

__all__ = [
    # File length analysis
    "AnalysisConfig",
    "AnalysisResult",
    "FileAnalysis",
    "FileAnalyzer",
    "SeverityLevel",
    # Complexity analysis
    "ComplexityAnalyzer",
    "ComplexityConfig",
    "ComplexityResult",
    "ComplexitySeverity",
    "FileComplexityAnalysis",
    "FunctionComplexity",
    # Duplication detection
    "CloneFamily",
    "CodeBlock",
    "DuplicationConfig",
    "DuplicationDetector",
    "DuplicationMatch",
    "DuplicationResult",
    "DuplicationSeverity",
    "DuplicationType",
    # Code smell detection
    "CodeSmell",
    "CodeSmellDetector",
    "SmellCategory",
    "SmellConfig",
    "SmellReport",
    "SmellSeverity",
    "SmellThresholds",
    # Technical debt analysis
    "DebtConfig",
    "DebtItem",
    "DebtReport",
    "DebtSeverity",
    "DebtType",
    "EffortModels",
    "InterestRates",
    "ROIAnalysis",
    "TechnicalDebtAnalyzer",
    "TimeHorizon",
    "TimeProjection",
    # Maintainability analysis
    "FileMaintainability",
    "FunctionMaintainability",
    "HalsteadMetrics",
    "LanguageProfile",
    "LanguageWeights",
    "MaintainabilityAnalyzer",
    "MaintainabilityConfig",
    "MaintainabilityLevel",
    "MaintainabilityReport",
    "MaintainabilityThresholds",
    # Lazy import analysis
    "LazyImport",
    "LazyImportConfig",
    "LazyImportReport",
    "LazyImportScanner",
    "LazyImportSeverity",
    "LazyImportType",
    # Environment fallback analysis
    "EnvFallbackConfig",
    "EnvFallbackReport",
    "EnvFallbackScanner",
    "EnvFallbackSeverity",
    "EnvFallbackType",
    "EnvFallbackViolation",
    # Syntax analysis
    "LinterType",
    "SyntaxChecker",
    "SyntaxConfig",
    "SyntaxFileAnalysis",
    "SyntaxIssue",
    "SyntaxResult",
    "SyntaxSeverity",
    # Documentation analysis
    "DocumentationConfig",
    "DocumentationReport",
    "DocumentationScanner",
    "DocClassDocumentation",
    "DocFunctionDocumentation",
    "FileDocumentation",
    # Naming convention analysis
    "NamingConfig",
    "NamingConvention",
    "NamingConventionScanner",
    "NamingReport",
    "NamingViolation",
    # Bug detection
    "BugCategory",
    "BugDetectionConfig",
    "BugDetector",
    "BugFinding",
    "BugReport",
    "BugSeverity",
    "NullDereferenceDetector",
    "UnreachableCodeDetector",
    # Static type checking (Pyright/Pylance)
    "FileTypeCheckStats",
    "TypeCheckCategory",
    "TypeCheckConfig",
    "TypeCheckDiagnostic",
    "TypeCheckReport",
    "TypeCheckSeverity",
    "TypeChecker",
    # JavaScript/TypeScript analysis
    "JSAnalysisConfig",
    "JSAnalyzer",
    "JSFinding",
    "JSReport",
    "JSRuleCategory",
    "JSSeverity",
    "TSAnalyzer",
    # Shell analysis
    "ShellAnalysisConfig",
    "ShellAnalyzer",
    "ShellFinding",
    "ShellReport",
    "ShellRuleCategory",
    "ShellSeverity",
]
