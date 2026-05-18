"""Tests for security log analyzer."""
import pytest
from pathlib import Path
from Asgard.Heimdall.Security.LogAnalysis.services.log_analyzer import LogAnalyzer
from Asgard.Heimdall.Security.LogAnalysis.models.log_models import LogAnalysisReport


class TestLogAnalyzerInstantiation:
    def test_analyzer_can_be_instantiated(self):
        assert LogAnalyzer() is not None


class TestLogAnalyzerCleanLog:
    def test_clean_log_returns_no_critical_events(self, tmp_path):
        log_file = tmp_path / "access.log"
        log_file.write_text(
            "2024-01-01 10:00:00 INFO User logged in successfully\n"
            "2024-01-01 10:01:00 INFO Page rendered\n"
        )
        analyzer = LogAnalyzer()
        report: LogAnalysisReport = analyzer.analyze_file(log_file)
        critical_events = [e for e in report.events if e.severity in ("CRITICAL", "HIGH")]
        assert len(critical_events) == 0


class TestLogAnalyzerBruteForce:
    def test_brute_force_detected_from_failed_password_lines(self, tmp_path):
        log_file = tmp_path / "auth.log"
        lines = "\n".join(
            [f"Jan  1 00:00:{i:02d} server sshd: Failed password for root from 1.2.3.4 port 222{i} ssh2"
             for i in range(15)]
        )
        log_file.write_text(lines + "\n")
        analyzer = LogAnalyzer()
        report: LogAnalysisReport = analyzer.analyze_file(log_file)
        assert report.total_events > 0
