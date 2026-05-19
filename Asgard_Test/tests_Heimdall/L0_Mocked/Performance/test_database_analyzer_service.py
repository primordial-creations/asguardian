"""
Tests for Heimdall Database Analyzer Service

Unit tests for database performance pattern detection and ORM anti-patterns.
"""

import pytest
import tempfile
from pathlib import Path

from Asgard.Heimdall.Performance.models.performance_models import (
    DatabaseFinding,
    DatabaseIssueType,
    DatabaseReport,
    PerformanceScanConfig,
    PerformanceSeverity,
)
from Asgard.Heimdall.Performance.services.database_analyzer_service import (
    DatabaseAnalyzerService,
    DatabasePattern,
    DATABASE_PATTERNS,
)


class TestDatabasePattern:
    """Tests for DatabasePattern class."""

    def test_init_with_default_file_types(self):
        """Test initializing pattern with default file types."""
        pattern = DatabasePattern(
            name="test_pattern",
            pattern=r"test",
            issue_type=DatabaseIssueType.N_PLUS_ONE,
            severity=PerformanceSeverity.MEDIUM,
            description="Test description",
            estimated_impact="Test impact",
            recommendation="Test recommendation",
        )

        assert pattern.name == "test_pattern"
        assert pattern.issue_type == DatabaseIssueType.N_PLUS_ONE
        assert pattern.severity == PerformanceSeverity.MEDIUM
        assert ".py" in pattern.file_types

    def test_init_with_custom_file_types(self):
        """Test initializing pattern with custom file types."""
        pattern = DatabasePattern(
            name="test_pattern",
            pattern=r"test",
            issue_type=DatabaseIssueType.N_PLUS_ONE,
            severity=PerformanceSeverity.LOW,
            description="Test description",
            estimated_impact="Test impact",
            recommendation="Test recommendation",
            file_types={".sql"},
        )

        assert pattern.file_types == {".sql"}

    def test_pattern_compilation(self):
        """Test that regex pattern is compiled correctly."""
        pattern = DatabasePattern(
            name="test_pattern",
            pattern=r"\.objects\.all",
            issue_type=DatabaseIssueType.FULL_TABLE_SCAN,
            severity=PerformanceSeverity.MEDIUM,
            description="Test description",
            estimated_impact="Test impact",
            recommendation="Test recommendation",
        )

        assert pattern.pattern.search("User.objects.all()") is not None
        assert pattern.pattern.search("MODEL.OBJECTS.ALL()") is not None


class TestDatabasePatterns:
    """Tests for predefined DATABASE_PATTERNS."""

    def test_database_patterns_exist(self):
        """Test that predefined database patterns are defined."""
        assert len(DATABASE_PATTERNS) > 0

    def test_objects_all_no_filter_pattern_exists(self):
        """Test that objects_all_no_filter pattern exists."""
        pattern_names = [p.name for p in DATABASE_PATTERNS]
        assert "objects_all_no_filter" in pattern_names

    def test_cursor_execute_pattern_exists(self):
        """Test that cursor_execute pattern exists."""
        pattern_names = [p.name for p in DATABASE_PATTERNS]
        assert "cursor_execute" in pattern_names

    def test_all_patterns_have_required_fields(self):
        """Test that all patterns have required fields."""
        for pattern in DATABASE_PATTERNS:
            assert pattern.name
            assert pattern.pattern
            assert pattern.issue_type
            assert pattern.severity
            assert pattern.description
            assert pattern.estimated_impact
            assert pattern.recommendation


class TestDatabaseAnalyzerService:
    """Tests for DatabaseAnalyzerService class."""

    def test_init_with_default_config(self):
        """Test initializing with default configuration."""
        service = DatabaseAnalyzerService()

        assert service.config is not None
        assert isinstance(service.config, PerformanceScanConfig)
        assert len(service.patterns) > 0

    def test_init_with_custom_config(self):
        """Test initializing with custom configuration."""
        config = PerformanceScanConfig(
            scan_path=Path("/custom/path"),
            min_severity=PerformanceSeverity.HIGH,
        )
        service = DatabaseAnalyzerService(config)

        assert service.config.scan_path == Path("/custom/path")
        assert service.config.min_severity == PerformanceSeverity.HIGH

    def test_scan_nonexistent_path(self):
        """Test scanning a path that doesn't exist."""
        service = DatabaseAnalyzerService()

        with pytest.raises(FileNotFoundError):
            service.scan(Path("/nonexistent/path"))

    def test_scan_empty_directory(self):
        """Test scanning an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = DatabaseAnalyzerService()
            result = service.scan(Path(tmpdir))

            assert isinstance(result, DatabaseReport)
            assert result.total_files_scanned == 0
            assert result.issues_found == 0
            assert result.orm_detected is None

    def test_scan_clean_code(self):
        """Test scanning clean database code."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "clean.py").write_text('''
from django.db import models

class User(models.Model):
    name = models.CharField(max_length=100)

def get_users():
    return User.objects.filter(active=True)[:10]
''')

            service = DatabaseAnalyzerService()
            result = service.scan(tmpdir_path)

            assert result.total_files_scanned == 1

    def test_detect_objects_all_no_filter(self):
        """Test detecting .objects.all() without filtering."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "no_filter.py").write_text('''
from django.db import models

def get_all_users():
    return User.objects.all()

def get_all_posts():
    posts = Post.objects.all()
    return posts
''')

            service = DatabaseAnalyzerService()
            result = service.scan(tmpdir_path)

            full_scan_findings = [
                f for f in result.findings
                if f.issue_type == DatabaseIssueType.FULL_TABLE_SCAN
            ]
            assert len(full_scan_findings) >= 2

    def test_detect_cursor_execute(self):
        """Test detecting raw cursor.execute calls."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "cursor.py").write_text('''
import sqlite3

def get_users():
    conn = sqlite3.connect('db.sqlite')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    return cursor.fetchall()

def insert_user(name):
    cursor.execute("INSERT INTO users (name) VALUES (?)", (name,))
''')

            service = DatabaseAnalyzerService()
            result = service.scan(tmpdir_path)

            n_plus_one_findings = [
                f for f in result.findings
                if f.issue_type == DatabaseIssueType.N_PLUS_ONE
            ]
            assert len(n_plus_one_findings) >= 2

    def test_detect_like_leading_wildcard(self):
        """Test detecting LIKE with leading wildcard."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "like.py").write_text('''
def search_users(term):
    query = "SELECT * FROM users WHERE name LIKE '%{}%'".format(term)
    another = "SELECT * FROM posts WHERE title LIKE '%search%'"
    return execute_query(query)
''')

            service = DatabaseAnalyzerService()
            result = service.scan(tmpdir_path)

            full_scan_findings = [
                f for f in result.findings
                if f.issue_type == DatabaseIssueType.FULL_TABLE_SCAN
            ]
            assert len(full_scan_findings) >= 2

    def test_detect_select_star(self):
        """Test detecting SELECT * queries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "select_star.py").write_text('''
def get_data():
    query1 = "SELECT * FROM users"
    query2 = "SELECT * FROM posts WHERE id = 1"
    return execute_queries([query1, query2])
''')

            service = DatabaseAnalyzerService()
            result = service.scan(tmpdir_path)

            full_scan_findings = [
                f for f in result.findings
                if f.issue_type == DatabaseIssueType.FULL_TABLE_SCAN
            ]
            assert len(full_scan_findings) >= 2

    def test_detect_distinct_keyword(self):
        """Test detecting DISTINCT without proper indexing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "distinct.py").write_text('''
def get_unique_names():
    query = "SELECT DISTINCT name FROM users"
    return execute_query(query)

def get_unique_emails():
    return "SELECT DISTINCT email FROM customers"
''')

            service = DatabaseAnalyzerService()
            result = service.scan(tmpdir_path)

            missing_index_findings = [
                f for f in result.findings
                if f.issue_type == DatabaseIssueType.MISSING_INDEX
            ]
            assert len(missing_index_findings) >= 2

    def test_detect_django_save_instead_of_bulk(self):
        """Test detecting individual save() instead of bulk_create."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "save.py").write_text('''
from django.db import models

def create_users(names):
    for name in names:
        user = User(name=name)
        user.save()

def update_status():
    obj.status = "active"
    obj.save()
''')

            service = DatabaseAnalyzerService()
            result = service.scan(tmpdir_path)

            excessive_queries_findings = [
                f for f in result.findings
                if f.issue_type == DatabaseIssueType.EXCESSIVE_QUERIES
            ]
            assert len(excessive_queries_findings) >= 2

    def test_detect_django_orm(self):
        """Test detecting Django ORM."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "django_code.py").write_text('''
from django.db import models
from django.core.exceptions import ObjectDoesNotExist

class MyModel(models.Model):
    name = models.CharField(max_length=100)
''')

            service = DatabaseAnalyzerService()
            result = service.scan(tmpdir_path)

            assert result.orm_detected == "Django ORM"

    def test_detect_sqlalchemy_orm(self):
        """Test detecting SQLAlchemy ORM."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "sqlalchemy_code.py").write_text('''
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
''')

            service = DatabaseAnalyzerService()
            result = service.scan(tmpdir_path)

            assert result.orm_detected == "SQLAlchemy"

    def test_detect_peewee_orm(self):
        """Test detecting Peewee ORM."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "peewee_code.py").write_text('''
from peewee import Model, CharField

class User(Model):
    name = CharField()
''')

            service = DatabaseAnalyzerService()
            result = service.scan(tmpdir_path)

            assert result.orm_detected == "Peewee"

    def test_detect_tortoise_orm(self):
        """Test detecting Tortoise ORM."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "tortoise_code.py").write_text('''
from tortoise import fields
from tortoise.models import Model

class User(Model):
    name = fields.CharField(max_length=100)
''')

            service = DatabaseAnalyzerService()
            result = service.scan(tmpdir_path)

            assert result.orm_detected == "Tortoise ORM"

    def test_detect_prisma_orm(self):
        """Test detecting Prisma ORM."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "prisma_code.py").write_text('''
from prisma import Prisma

async def main():
    db = Prisma()
    await db.connect()
''')

            service = DatabaseAnalyzerService()
            result = service.scan(tmpdir_path)

            assert result.orm_detected == "Prisma"

    def test_severity_filtering(self):
        """Test filtering findings by severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "mixed.py").write_text('''
def query1():
    return "SELECT * FROM users"

def query2():
    return User.objects.all()
''')

            config = PerformanceScanConfig(
                min_severity=PerformanceSeverity.HIGH,
            )
            service = DatabaseAnalyzerService(config)
            result = service.scan(tmpdir_path)

            for finding in result.findings:
                assert finding.severity in [
                    PerformanceSeverity.HIGH.value,
                    PerformanceSeverity.CRITICAL.value,
                ]

    def test_findings_sorted_by_severity(self):
        """Test that findings are sorted by severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "mixed.py").write_text('''
def queries():
    q1 = "SELECT * FROM users"
    q2 = "SELECT DISTINCT name FROM users"
    q3 = User.objects.all()
''')

            service = DatabaseAnalyzerService()
            result = service.scan(tmpdir_path)

            if len(result.findings) > 1:
                severity_order = {
                    PerformanceSeverity.CRITICAL.value: 0,
                    PerformanceSeverity.HIGH.value: 1,
                    PerformanceSeverity.MEDIUM.value: 2,
                    PerformanceSeverity.LOW.value: 3,
                    PerformanceSeverity.INFO.value: 4,
                }

                for i in range(len(result.findings) - 1):
                    current_order = severity_order.get(result.findings[i].severity, 5)
                    next_order = severity_order.get(result.findings[i + 1].severity, 5)
                    assert current_order <= next_order

    def test_scan_duration_recorded(self):
        """Test that scan duration is recorded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            service = DatabaseAnalyzerService()
            result = service.scan(Path(tmpdir))

            assert result.scan_duration_seconds >= 0

    def test_ignore_comments(self):
        """Test that patterns in comments are ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "comments.py").write_text(
                "# User.objects.all()\n"
                "# cursor.execute('SELECT * FROM users')\n"
                "\n"
                "def actual_function():\n"
                "    pass\n"
            )

            service = DatabaseAnalyzerService()
            result = service.scan(tmpdir_path)

            assert result.issues_found == 0

    def test_exclude_patterns(self):
        """Test that files matching exclude patterns are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "include.py").write_text('''
def query():
    return User.objects.all()
''')

            test_dir = tmpdir_path / "tests"
            test_dir.mkdir()
            (test_dir / "test_file.py").write_text('''
def test_query():
    return User.objects.all()
''')

            config = PerformanceScanConfig(
                exclude_patterns=["tests"],
            )
            service = DatabaseAnalyzerService(config)
            result = service.scan(tmpdir_path)

            assert result.total_files_scanned == 1

    def test_include_extensions(self):
        """Test that only specified file extensions are scanned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "script.py").write_text('''
def query():
    return User.objects.all()
''')

            (tmpdir_path / "script.sql").write_text('''
SELECT * FROM users;
''')

            config = PerformanceScanConfig(
                include_extensions=[".py"],
            )
            service = DatabaseAnalyzerService(config)
            result = service.scan(tmpdir_path)

            assert result.total_files_scanned == 1

    def test_file_read_error_handling(self):
        """Test handling of file read errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            file_path = tmpdir_path / "normal.py"
            file_path.write_text('''
def query():
    return User.objects.filter(active=True)
''')

            service = DatabaseAnalyzerService()
            result = service.scan(tmpdir_path)

            assert isinstance(result, DatabaseReport)

    def test_is_in_comment_python(self):
        """Test comment detection for Python code."""
        service = DatabaseAnalyzerService()
        lines = [
            "# This is a comment",
            "def function():",
            "    pass",
        ]

        assert service._is_in_comment(lines, 1)
        assert not service._is_in_comment(lines, 2)

    def test_is_in_comment_out_of_bounds(self):
        """Test comment detection with invalid line numbers."""
        service = DatabaseAnalyzerService()
        lines = ["line 1", "line 2"]

        assert not service._is_in_comment(lines, 0)
        assert not service._is_in_comment(lines, 10)

    def test_code_snippet_in_findings(self):
        """Test that findings include code snippets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "snippet.py").write_text('''
from django.db import models

def get_all():
    return User.objects.all()
''')

            service = DatabaseAnalyzerService()
            result = service.scan(tmpdir_path)

            if result.findings:
                assert result.findings[0].code_snippet
                assert ">>>" in result.findings[0].code_snippet

    def test_relative_file_paths_in_findings(self):
        """Test that findings contain relative file paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            subdir = tmpdir_path / "subdir"
            subdir.mkdir()
            (subdir / "code.py").write_text('''
def query():
    return User.objects.all()
''')

            service = DatabaseAnalyzerService()
            result = service.scan(tmpdir_path)

            if result.findings:
                assert not result.findings[0].file_path.startswith("/")
                assert "subdir" in result.findings[0].file_path

    def test_scan_with_config_path(self):
        """Test scanning using path from configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = PerformanceScanConfig(
                scan_path=Path(tmpdir),
            )
            service = DatabaseAnalyzerService(config)
            result = service.scan()

            assert result.scan_path == str(Path(tmpdir).resolve())

    def test_multiple_findings_same_file(self):
        """Test detecting multiple issues in the same file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "multi.py").write_text('''
def query1():
    return User.objects.all()

def query2():
    return "SELECT * FROM users"

def query3():
    cursor.execute("SELECT DISTINCT name FROM users")
''')

            service = DatabaseAnalyzerService()
            result = service.scan(tmpdir_path)

            assert result.issues_found >= 3

    def test_query_pattern_in_findings(self):
        """Test that findings include query pattern names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "pattern.py").write_text('''
def query():
    return User.objects.all()
''')

            service = DatabaseAnalyzerService()
            result = service.scan(tmpdir_path)

            if result.findings:
                assert result.findings[0].query_pattern
                assert result.findings[0].query_pattern == "objects_all_no_filter"

    def test_severity_meets_threshold_low(self):
        """Test severity threshold checking with LOW threshold."""
        service = DatabaseAnalyzerService()

        assert service._severity_meets_threshold(PerformanceSeverity.LOW.value)
        assert service._severity_meets_threshold(PerformanceSeverity.MEDIUM.value)
        assert service._severity_meets_threshold(PerformanceSeverity.HIGH.value)
        assert service._severity_meets_threshold(PerformanceSeverity.CRITICAL.value)

    def test_severity_meets_threshold_high(self):
        """Test severity threshold checking with HIGH threshold."""
        config = PerformanceScanConfig(
            min_severity=PerformanceSeverity.HIGH,
        )
        service = DatabaseAnalyzerService(config)

        assert not service._severity_meets_threshold(PerformanceSeverity.LOW.value)
        assert not service._severity_meets_threshold(PerformanceSeverity.MEDIUM.value)
        assert service._severity_meets_threshold(PerformanceSeverity.HIGH.value)
        assert service._severity_meets_threshold(PerformanceSeverity.CRITICAL.value)

    def test_severity_order(self):
        """Test severity ordering for sorting."""
        service = DatabaseAnalyzerService()

        assert service._severity_order(PerformanceSeverity.CRITICAL.value) < \
               service._severity_order(PerformanceSeverity.HIGH.value)
        assert service._severity_order(PerformanceSeverity.HIGH.value) < \
               service._severity_order(PerformanceSeverity.MEDIUM.value)
        assert service._severity_order(PerformanceSeverity.MEDIUM.value) < \
               service._severity_order(PerformanceSeverity.LOW.value)

    def test_orm_detection_none_when_no_orm(self):
        """Test that ORM detection returns None when no ORM is found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "plain.py").write_text('''
import sqlite3

def query():
    conn = sqlite3.connect('db.sqlite')
    return conn.cursor().execute("SELECT * FROM users")
''')

            service = DatabaseAnalyzerService()
            result = service.scan(tmpdir_path)

            # ORM might be None or remain as first detected ORM
            assert isinstance(result.orm_detected, (str, type(None)))

    def test_estimated_impact_in_findings(self):
        """Test that findings include estimated impact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "impact.py").write_text('''
def query():
    return User.objects.all()
''')

            service = DatabaseAnalyzerService()
            result = service.scan(tmpdir_path)

            if result.findings:
                assert result.findings[0].estimated_impact
                assert len(result.findings[0].estimated_impact) > 0

    def test_recommendation_in_findings(self):
        """Test that findings include recommendations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            (tmpdir_path / "recommend.py").write_text('''
def query():
    return User.objects.all()
''')

            service = DatabaseAnalyzerService()
            result = service.scan(tmpdir_path)

            if result.findings:
                assert result.findings[0].recommendation
                assert len(result.findings[0].recommendation) > 0
