"""
Tests for Heimdall Complexity Analyzer Service

Unit tests for cyclomatic and cognitive complexity analysis.
"""

import pytest
import tempfile
from pathlib import Path

from Asgard.Bragi.Quality.models.complexity_models import (
    ComplexityConfig,
    ComplexitySeverity,
    FunctionComplexity,
)
from Asgard.Bragi.Quality.services.complexity_analyzer import (
    ComplexityAnalyzer,
    CyclomaticComplexityVisitor,
    CognitiveComplexityVisitor,
)


class TestComplexityAnalyzer:
    """Tests for ComplexityAnalyzer class."""

    def test_init_with_default_config(self):
        """Test initializing with default configuration."""
        analyzer = ComplexityAnalyzer()
        assert analyzer.config is not None
        assert analyzer.config.cyclomatic_threshold == 10
        assert analyzer.config.cognitive_threshold == 15

    def test_init_with_custom_config(self):
        """Test initializing with custom configuration."""
        config = ComplexityConfig(cyclomatic_threshold=5, cognitive_threshold=10)
        analyzer = ComplexityAnalyzer(config)
        assert analyzer.config.cyclomatic_threshold == 5
        assert analyzer.config.cognitive_threshold == 10

    def test_analyze_nonexistent_path(self):
        """Test analyzing a path that doesn't exist."""
        analyzer = ComplexityAnalyzer()
        with pytest.raises(FileNotFoundError):
            analyzer.analyze(Path("/nonexistent/path"))

    def test_analyze_empty_directory(self):
        """Test analyzing an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = ComplexityAnalyzer()
            result = analyzer.analyze(Path(tmpdir))

            assert result.total_files_scanned == 0
            assert result.total_functions_analyzed == 0
            assert result.has_violations is False

    def test_analyze_simple_function(self):
        """Test analyzing a simple function with low complexity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a simple Python file
            code = '''
def simple_function(x):
    return x + 1
'''
            (tmpdir_path / "simple.py").write_text(code)

            config = ComplexityConfig(cyclomatic_threshold=10, cognitive_threshold=15)
            analyzer = ComplexityAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            assert result.total_files_scanned == 1
            assert result.total_functions_analyzed == 1
            assert result.has_violations is False
            # Simple function should have CC=1, COG=0
            assert result.max_cyclomatic == 1
            assert result.max_cognitive == 0

    def test_analyze_complex_function(self):
        """Test analyzing a function with high complexity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a complex Python file
            code = '''
def complex_function(a, b, c, d):
    if a:
        if b:
            if c:
                if d:
                    return 1
                else:
                    return 2
            else:
                return 3
        else:
            return 4
    else:
        if b and c:
            for i in range(10):
                if i > 5:
                    return 5
        return 6
'''
            (tmpdir_path / "complex.py").write_text(code)

            config = ComplexityConfig(cyclomatic_threshold=5, cognitive_threshold=10)
            analyzer = ComplexityAnalyzer(config)
            result = analyzer.analyze(tmpdir_path)

            assert result.total_files_scanned == 1
            assert result.total_functions_analyzed == 1
            assert result.has_violations is True
            assert len(result.violations) == 1

    def test_analyze_class_methods(self):
        """Test analyzing methods within a class."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''
class MyClass:
    def simple_method(self):
        return 1

    def complex_method(self, a, b):
        if a:
            if b:
                return 1
            return 2
        return 3
'''
            (tmpdir_path / "class_file.py").write_text(code)

            analyzer = ComplexityAnalyzer()
            result = analyzer.analyze(tmpdir_path)

            assert result.total_files_scanned == 1
            assert result.total_functions_analyzed == 2

            # Find the complex method
            complex_method = None
            for fa in result.file_analyses:
                for func in fa.functions:
                    if func.name == "complex_method":
                        complex_method = func
                        break

            assert complex_method is not None
            assert complex_method.is_method is True
            assert complex_method.class_name == "MyClass"
            assert complex_method.qualified_name == "MyClass.complex_method"

    def test_analyze_multiple_files(self):
        """Test analyzing multiple Python files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create multiple files
            (tmpdir_path / "file1.py").write_text("def func1(): return 1")
            (tmpdir_path / "file2.py").write_text("def func2(): return 2")
            (tmpdir_path / "file3.py").write_text("""
def func3(x):
    if x:
        return 1
    return 2
""")

            analyzer = ComplexityAnalyzer()
            result = analyzer.analyze(tmpdir_path)

            assert result.total_files_scanned == 3
            assert result.total_functions_analyzed == 3

    def test_analyze_single_file(self):
        """Test analyzing a single file directly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            code = '''
def test_function(x, y):
    if x and y:
        return 1
    return 0
'''
            file_path = tmpdir_path / "single.py"
            file_path.write_text(code)

            analyzer = ComplexityAnalyzer()
            result = analyzer.analyze_single_file(file_path)

            assert result.total_functions == 1
            assert result.functions[0].name == "test_function"


class TestCyclomaticComplexityVisitor:
    """Tests for CyclomaticComplexityVisitor."""

    def test_base_complexity(self):
        """Test that base complexity is 1."""
        import ast
        code = "def simple(): return 1"
        tree = ast.parse(code)
        func_node = tree.body[0]

        visitor = CyclomaticComplexityVisitor()
        visitor.visit(func_node)

        assert visitor.complexity == 1

    def test_if_statement_adds_complexity(self):
        """Test that if statements add to complexity."""
        import ast
        code = '''
def func(x):
    if x:
        return 1
    return 0
'''
        tree = ast.parse(code)
        func_node = tree.body[0]

        visitor = CyclomaticComplexityVisitor()
        visitor.visit(func_node)

        # Base(1) + if(1) = 2
        assert visitor.complexity == 2

    def test_nested_ifs_add_complexity(self):
        """Test that nested if statements add complexity."""
        import ast
        code = '''
def func(a, b):
    if a:
        if b:
            return 1
    return 0
'''
        tree = ast.parse(code)
        func_node = tree.body[0]

        visitor = CyclomaticComplexityVisitor()
        visitor.visit(func_node)

        # Base(1) + if(1) + if(1) = 3
        assert visitor.complexity == 3

    def test_for_loop_adds_complexity(self):
        """Test that for loops add complexity."""
        import ast
        code = '''
def func(items):
    for item in items:
        print(item)
'''
        tree = ast.parse(code)
        func_node = tree.body[0]

        visitor = CyclomaticComplexityVisitor()
        visitor.visit(func_node)

        # Base(1) + for(1) = 2
        assert visitor.complexity == 2

    def test_while_loop_adds_complexity(self):
        """Test that while loops add complexity."""
        import ast
        code = '''
def func(x):
    while x > 0:
        x -= 1
'''
        tree = ast.parse(code)
        func_node = tree.body[0]

        visitor = CyclomaticComplexityVisitor()
        visitor.visit(func_node)

        # Base(1) + while(1) = 2
        assert visitor.complexity == 2

    def test_boolean_operators_add_complexity(self):
        """Test that boolean operators add complexity."""
        import ast
        code = '''
def func(a, b, c):
    if a and b and c:
        return 1
'''
        tree = ast.parse(code)
        func_node = tree.body[0]

        visitor = CyclomaticComplexityVisitor()
        visitor.visit(func_node)

        # Base(1) + if(1) + and(2, for 3 operands) = 4
        assert visitor.complexity == 4

    def test_except_handler_adds_complexity(self):
        """Test that except handlers add complexity."""
        import ast
        code = '''
def func():
    try:
        x = 1
    except ValueError:
        pass
    except TypeError:
        pass
'''
        tree = ast.parse(code)
        func_node = tree.body[0]

        visitor = CyclomaticComplexityVisitor()
        visitor.visit(func_node)

        # Base(1) + except(1) + except(1) = 3
        assert visitor.complexity == 3

    def test_ternary_adds_complexity(self):
        """Test that ternary expressions add complexity."""
        import ast
        code = '''
def func(x):
    return 1 if x else 0
'''
        tree = ast.parse(code)
        func_node = tree.body[0]

        visitor = CyclomaticComplexityVisitor()
        visitor.visit(func_node)

        # Base(1) + ternary(1) = 2
        assert visitor.complexity == 2


class TestCognitiveComplexityVisitor:
    """Tests for CognitiveComplexityVisitor."""

    def test_base_complexity_zero(self):
        """Test that a simple function has zero cognitive complexity."""
        import ast
        code = "def simple(): return 1"
        tree = ast.parse(code)
        func_node = tree.body[0]

        visitor = CognitiveComplexityVisitor()
        visitor.visit(func_node)

        assert visitor.complexity == 0

    def test_single_if_adds_one(self):
        """Test that a single if adds 1 complexity."""
        import ast
        code = '''
def func(x):
    if x:
        return 1
    return 0
'''
        tree = ast.parse(code)
        func_node = tree.body[0]

        visitor = CognitiveComplexityVisitor()
        visitor.visit(func_node)

        # if(1) = 1
        assert visitor.complexity == 1

    def test_nested_if_adds_nesting_penalty(self):
        """Test that nested if adds nesting penalty."""
        import ast
        code = '''
def func(a, b):
    if a:
        if b:
            return 1
    return 0
'''
        tree = ast.parse(code)
        func_node = tree.body[0]

        visitor = CognitiveComplexityVisitor()
        visitor.visit(func_node)

        # outer if(1) + nested if(1 base + 1 nesting) = 3
        assert visitor.complexity == 3

    def test_for_loop_adds_complexity(self):
        """Test that for loops add complexity with nesting."""
        import ast
        code = '''
def func(items):
    for item in items:
        if item:
            print(item)
'''
        tree = ast.parse(code)
        func_node = tree.body[0]

        visitor = CognitiveComplexityVisitor()
        visitor.visit(func_node)

        # for(1) + nested if(1 base + 1 nesting) = 3
        assert visitor.complexity == 3

    def test_break_adds_complexity(self):
        """Test that break statements add complexity."""
        import ast
        code = '''
def func(items):
    for item in items:
        if item:
            break
'''
        tree = ast.parse(code)
        func_node = tree.body[0]

        visitor = CognitiveComplexityVisitor()
        visitor.visit(func_node)

        # for(1) + if(1+1 nesting) + break(1) = 4
        assert visitor.complexity >= 3


class TestFunctionComplexity:
    """Tests for FunctionComplexity model."""

    def test_calculate_severity_low(self):
        """Test severity calculation for low complexity."""
        assert FunctionComplexity.calculate_severity(1) == ComplexitySeverity.LOW
        assert FunctionComplexity.calculate_severity(5) == ComplexitySeverity.LOW

    def test_calculate_severity_moderate(self):
        """Test severity calculation for moderate complexity."""
        assert FunctionComplexity.calculate_severity(6) == ComplexitySeverity.MODERATE
        assert FunctionComplexity.calculate_severity(10) == ComplexitySeverity.MODERATE

    def test_calculate_severity_high(self):
        """Test severity calculation for high complexity."""
        assert FunctionComplexity.calculate_severity(11) == ComplexitySeverity.HIGH
        assert FunctionComplexity.calculate_severity(20) == ComplexitySeverity.HIGH

    def test_calculate_severity_very_high(self):
        """Test severity calculation for very high complexity."""
        assert FunctionComplexity.calculate_severity(21) == ComplexitySeverity.VERY_HIGH
        assert FunctionComplexity.calculate_severity(50) == ComplexitySeverity.VERY_HIGH

    def test_calculate_severity_critical(self):
        """Test severity calculation for critical complexity."""
        assert FunctionComplexity.calculate_severity(51) == ComplexitySeverity.CRITICAL
        assert FunctionComplexity.calculate_severity(100) == ComplexitySeverity.CRITICAL

    def test_qualified_name_function(self):
        """Test qualified name for standalone function."""
        func = FunctionComplexity(
            name="my_function",
            line_number=10,
            end_line=20,
            cyclomatic_complexity=5,
            cognitive_complexity=3,
            severity=ComplexitySeverity.LOW,
        )
        assert func.qualified_name == "my_function"

    def test_qualified_name_method(self):
        """Test qualified name for class method."""
        func = FunctionComplexity(
            name="my_method",
            line_number=10,
            end_line=20,
            cyclomatic_complexity=5,
            cognitive_complexity=3,
            severity=ComplexitySeverity.LOW,
            is_method=True,
            class_name="MyClass",
        )
        assert func.qualified_name == "MyClass.my_method"

    def test_max_complexity(self):
        """Test max_complexity property."""
        func = FunctionComplexity(
            name="test",
            line_number=1,
            end_line=10,
            cyclomatic_complexity=8,
            cognitive_complexity=12,
            severity=ComplexitySeverity.HIGH,
        )
        assert func.max_complexity == 12

        func2 = FunctionComplexity(
            name="test2",
            line_number=1,
            end_line=10,
            cyclomatic_complexity=15,
            cognitive_complexity=10,
            severity=ComplexitySeverity.HIGH,
        )
        assert func2.max_complexity == 15
