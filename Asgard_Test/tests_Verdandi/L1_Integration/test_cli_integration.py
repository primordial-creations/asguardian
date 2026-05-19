"""
L1 Integration Tests for Verdandi CLI.

Tests the complete workflow of running Verdandi CLI commands with sample data,
validating output format (JSON, text), and ensuring all subcommands work correctly.
"""

import json
import subprocess
import sys
from io import StringIO

import pytest

from Asgard.Verdandi.cli._parser import create_parser
from Asgard.Verdandi.cli.handlers_analysis import (
    parse_data_list,
    run_web_vitals,
    run_percentiles,
    run_apdex,
    run_sla_check,
    run_cache_metrics,
)


class TestCLIParserIntegration:
    """Integration tests for CLI argument parser."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = create_parser()

    def test_cli_parser_creation(self):
        """Test that parser is created successfully."""
        assert self.parser is not None
        assert self.parser.prog == "verdandi"

    def test_cli_parser_web_vitals_command(self):
        """Test parsing web vitals command."""
        args = self.parser.parse_args([
            "web", "vitals",
            "--lcp", "2000",
            "--fid", "50",
            "--cls", "0.05",
        ])

        assert args.command == "web"
        assert args.web_command == "vitals"
        assert args.lcp == 2000.0
        assert args.fid == 50.0
        assert args.cls == 0.05

    def test_cli_parser_analyze_percentiles_command(self):
        """Test parsing analyze percentiles command."""
        args = self.parser.parse_args([
            "analyze", "percentiles",
            "--data", "100,150,200,250,300",
        ])

        assert args.command == "analyze"
        assert args.analyze_command == "percentiles"
        assert args.data == "100,150,200,250,300"

    def test_cli_parser_analyze_apdex_command(self):
        """Test parsing analyze apdex command."""
        args = self.parser.parse_args([
            "analyze", "apdex",
            "--data", "100,200,300,400,500",
            "--threshold", "500",
        ])

        assert args.command == "analyze"
        assert args.analyze_command == "apdex"
        assert args.data == "100,200,300,400,500"
        assert args.threshold == 500.0

    def test_cli_parser_analyze_sla_command(self):
        """Test parsing analyze sla command."""
        args = self.parser.parse_args([
            "analyze", "sla",
            "--data", "100,150,200",
            "--threshold", "200",
            "--percentile", "95",
        ])

        assert args.command == "analyze"
        assert args.analyze_command == "sla"
        assert args.threshold == 200.0
        assert args.percentile == 95.0

    def test_cli_parser_cache_metrics_command(self):
        """Test parsing cache metrics command."""
        args = self.parser.parse_args([
            "cache", "metrics",
            "--hits", "900",
            "--misses", "100",
        ])

        assert args.command == "cache"
        assert args.cache_command == "metrics"
        assert args.hits == 900
        assert args.misses == 100

    def test_cli_parser_format_option(self):
        """Test format option parsing."""
        args = self.parser.parse_args([
            "--format", "json",
            "web", "vitals",
            "--lcp", "2000",
        ])

        assert args.format == "json"

    def test_cli_parser_verbose_option(self):
        """Test verbose option parsing."""
        args = self.parser.parse_args([
            "--verbose",
            "web", "vitals",
            "--lcp", "2000",
        ])

        assert args.verbose is True


class TestCLIDataParsingIntegration:
    """Integration tests for CLI data parsing utilities."""

    def test_cli_parse_data_list_simple(self):
        """Test parsing simple comma-separated data."""
        data = parse_data_list("100,150,200,250,300")

        assert data == [100.0, 150.0, 200.0, 250.0, 300.0]

    def test_cli_parse_data_list_with_spaces(self):
        """Test parsing data with spaces."""
        data = parse_data_list("100, 150, 200, 250, 300")

        assert data == [100.0, 150.0, 200.0, 250.0, 300.0]

    def test_cli_parse_data_list_floats(self):
        """Test parsing floating point data."""
        data = parse_data_list("100.5,150.75,200.25")

        assert data == [100.5, 150.75, 200.25]

    def test_cli_parse_data_list_single_value(self):
        """Test parsing single value."""
        data = parse_data_list("100")

        assert data == [100.0]


class TestCLIWebVitalsIntegration:
    """Integration tests for web vitals CLI command."""

    def test_cli_web_vitals_text_output_good(self, capsys):
        """Test web vitals command with text output format for good performance."""
        class Args:
            lcp = 2000.0
            fid = 50.0
            cls = 0.05
            inp = 150.0
            ttfb = 600.0
            fcp = 1500.0

        exit_code = run_web_vitals(Args(), "text")

        captured = capsys.readouterr()
        assert "VERDANDI - CORE WEB VITALS" in captured.out
        assert "good" in captured.out.lower()
        assert exit_code == 0

    def test_cli_web_vitals_text_output_poor(self, capsys):
        """Test web vitals command with text output format for poor performance."""
        class Args:
            lcp = 5000.0
            fid = 400.0
            cls = 0.5
            inp = 600.0
            ttfb = 2000.0
            fcp = 3500.0

        exit_code = run_web_vitals(Args(), "text")

        captured = capsys.readouterr()
        assert "VERDANDI - CORE WEB VITALS" in captured.out
        assert "poor" in captured.out.lower()
        assert "RECOMMENDATIONS" in captured.out
        assert exit_code == 1

    def test_cli_web_vitals_json_output(self, capsys):
        """Test web vitals command with JSON output format."""
        class Args:
            lcp = 2000.0
            fid = 50.0
            cls = 0.05
            inp = 150.0
            ttfb = 600.0
            fcp = 1500.0

        exit_code = run_web_vitals(Args(), "json")

        captured = capsys.readouterr()
        result = json.loads(captured.out)

        assert result["lcp_ms"] == 2000.0
        assert result["lcp_rating"] == "good"
        assert result["overall_rating"] == "good"
        assert exit_code == 0

    def test_cli_web_vitals_partial_metrics(self, capsys):
        """Test web vitals command with partial metrics."""
        class Args:
            lcp = 2100.0
            fid = None
            cls = 0.08
            inp = None
            ttfb = 650.0
            fcp = None

        exit_code = run_web_vitals(Args(), "text")

        captured = capsys.readouterr()
        assert "LCP" in captured.out
        assert "CLS" in captured.out
        assert "TTFB" in captured.out


class TestCLIPercentilesIntegration:
    """Integration tests for percentiles CLI command."""

    def test_cli_percentiles_text_output(self, capsys):
        """Test percentiles command with text output format."""
        class Args:
            data = "100,150,200,250,300"

        exit_code = run_percentiles(Args(), "text")

        captured = capsys.readouterr()
        assert "VERDANDI - PERCENTILE ANALYSIS" in captured.out
        assert "Samples:" in captured.out
        assert "P50:" in captured.out
        assert "P95:" in captured.out
        assert exit_code == 0

    def test_cli_percentiles_json_output(self, capsys):
        """Test percentiles command with JSON output format."""
        class Args:
            data = "100,150,200,250,300"

        exit_code = run_percentiles(Args(), "json")

        captured = capsys.readouterr()
        result = json.loads(captured.out)

        assert result["sample_count"] == 5
        assert "p50" in result
        assert "p95" in result
        assert "p99" in result
        assert exit_code == 0

    def test_cli_percentiles_large_dataset(self, capsys):
        """Test percentiles command with large dataset."""
        data_str = ",".join(str(i) for i in range(1, 101))

        class Args:
            data = data_str

        exit_code = run_percentiles(Args(), "json")

        captured = capsys.readouterr()
        result = json.loads(captured.out)

        assert result["sample_count"] == 100
        assert result["min_value"] == 1.0
        assert result["max_value"] == 100.0


class TestCLIApdexIntegration:
    """Integration tests for Apdex CLI command."""

    def test_cli_apdex_text_output_excellent(self, capsys):
        """Test Apdex command with excellent performance."""
        class Args:
            data = "100,150,200,250,300"
            threshold = 500.0

        exit_code = run_apdex(Args(), "text")

        captured = capsys.readouterr()
        assert "VERDANDI - APDEX SCORE" in captured.out
        assert "Score:" in captured.out
        assert "Excellent" in captured.out
        assert exit_code == 0

    def test_cli_apdex_text_output_poor(self, capsys):
        """Test Apdex command with poor performance."""
        class Args:
            data = "2500,3000,3500,4000,4500"
            threshold = 500.0

        exit_code = run_apdex(Args(), "text")

        captured = capsys.readouterr()
        assert "VERDANDI - APDEX SCORE" in captured.out
        assert exit_code == 1

    def test_cli_apdex_json_output(self, capsys):
        """Test Apdex command with JSON output format."""
        class Args:
            data = "100,200,300,400,500"
            threshold = 500.0

        exit_code = run_apdex(Args(), "json")

        captured = capsys.readouterr()
        result = json.loads(captured.out)

        assert "score" in result
        assert "rating" in result
        assert "satisfied_count" in result
        assert "tolerating_count" in result
        assert "frustrated_count" in result

    def test_cli_apdex_custom_threshold(self, capsys):
        """Test Apdex command with custom threshold."""
        class Args:
            data = "100,200,300,400,500"
            threshold = 100.0

        exit_code = run_apdex(Args(), "text")

        captured = capsys.readouterr()
        assert "Threshold T: 100" in captured.out


class TestCLISLAIntegration:
    """Integration tests for SLA CLI command."""

    def test_cli_sla_text_output_compliant(self, capsys):
        """Test SLA command with compliant data."""
        class Args:
            data = "100,150,200,180,190"
            threshold = 1000.0
            percentile = 95.0

        exit_code = run_sla_check(Args(), "text")

        captured = capsys.readouterr()
        assert "VERDANDI - SLA COMPLIANCE CHECK" in captured.out
        assert "COMPLIANT" in captured.out
        assert exit_code == 0

    def test_cli_sla_text_output_breached(self, capsys):
        """Test SLA command with breached data."""
        class Args:
            data = "100,200,300,400,500,600,700,800,900,1000"
            threshold = 200.0
            percentile = 95.0

        exit_code = run_sla_check(Args(), "text")

        captured = capsys.readouterr()
        assert "VERDANDI - SLA COMPLIANCE CHECK" in captured.out
        assert "VIOLATIONS" in captured.out
        assert exit_code == 1

    def test_cli_sla_json_output(self, capsys):
        """Test SLA command with JSON output format."""
        class Args:
            data = "100,150,200,180,190"
            threshold = 1000.0
            percentile = 95.0

        exit_code = run_sla_check(Args(), "json")

        captured = capsys.readouterr()
        result = json.loads(captured.out)

        assert "status" in result
        assert "percentile_value" in result
        assert "percentile_target" in result
        assert "threshold_ms" in result
        assert "margin_percent" in result

    def test_cli_sla_custom_percentile(self, capsys):
        """Test SLA command with custom percentile."""
        class Args:
            data = "100,150,200,250,300"
            threshold = 500.0
            percentile = 99.0

        exit_code = run_sla_check(Args(), "text")

        captured = capsys.readouterr()
        assert "P99" in captured.out


class TestCLICacheMetricsIntegration:
    """Integration tests for cache metrics CLI command."""

    def test_cli_cache_text_output_good(self, capsys):
        """Test cache metrics command with good hit rate."""
        class Args:
            hits = 900
            misses = 100
            hit_latency = None
            miss_latency = None

        exit_code = run_cache_metrics(Args(), "text")

        captured = capsys.readouterr()
        assert "VERDANDI - CACHE METRICS" in captured.out
        assert "Hit Rate:" in captured.out
        assert exit_code == 0

    def test_cli_cache_text_output_poor(self, capsys):
        """Test cache metrics command with poor hit rate."""
        class Args:
            hits = 100
            misses = 900

        exit_code = run_cache_metrics(Args(), "text")

        captured = capsys.readouterr()
        assert "VERDANDI - CACHE METRICS" in captured.out
        assert "RECOMMENDATIONS" in captured.out
        assert exit_code == 0

    def test_cli_cache_json_output(self, capsys):
        """Test cache metrics command with JSON output format."""
        class Args:
            hits = 900
            misses = 100

        exit_code = run_cache_metrics(Args(), "json")

        captured = capsys.readouterr()
        result = json.loads(captured.out)

        assert "hits" in result
        assert "misses" in result
        assert "hit_rate_percent" in result
        assert "total_requests" in result
        assert exit_code == 0

    def test_cli_cache_with_latency(self, capsys):
        """Test cache metrics command with latency data."""
        class Args:
            hits = 900
            misses = 100
            hit_latency = 10.0
            miss_latency = 100.0

        exit_code = run_cache_metrics(Args(), "text")

        captured = capsys.readouterr()
        assert "VERDANDI - CACHE METRICS" in captured.out


class TestCLIEndToEndIntegration:
    """End-to-end integration tests for CLI commands."""

    def test_cli_web_vitals_full_workflow(self, capsys):
        """Test complete web vitals workflow from CLI."""
        class Args:
            lcp = 2000.0
            fid = 50.0
            cls = 0.05
            inp = 150.0
            ttfb = 600.0
            fcp = 1500.0

        exit_code_text = run_web_vitals(Args(), "text")
        text_output = capsys.readouterr()

        exit_code_json = run_web_vitals(Args(), "json")
        json_output = capsys.readouterr()

        assert exit_code_text == 0
        assert exit_code_json == 0
        assert "VERDANDI" in text_output.out
        assert json.loads(json_output.out)["overall_rating"] == "good"

    def test_cli_analyze_percentiles_full_workflow(self, capsys):
        """Test complete percentiles analysis workflow from CLI."""
        class Args:
            data = "100,150,200,250,300,350,400,450,500,550"

        exit_code_text = run_percentiles(Args(), "text")
        text_output = capsys.readouterr()

        exit_code_json = run_percentiles(Args(), "json")
        json_output = capsys.readouterr()

        assert exit_code_text == 0
        assert exit_code_json == 0
        assert "PERCENTILE ANALYSIS" in text_output.out

        json_result = json.loads(json_output.out)
        assert json_result["sample_count"] == 10
        assert json_result["p50"] > json_result["min_value"]
        assert json_result["p95"] < json_result["max_value"]

    def test_cli_multiple_commands_consistency(self, capsys):
        """Test that multiple CLI commands produce consistent results."""
        class PercentileArgs:
            data = "100,200,300,400,500"

        percentile_exit = run_percentiles(PercentileArgs(), "json")
        percentile_output = capsys.readouterr()
        percentile_result = json.loads(percentile_output.out)

        class ApdexArgs:
            data = "100,200,300,400,500"
            threshold = 500.0

        apdex_exit = run_apdex(ApdexArgs(), "json")
        apdex_output = capsys.readouterr()
        apdex_result = json.loads(apdex_output.out)

        assert percentile_result["sample_count"] == apdex_result["total_count"]
        assert percentile_exit == 0
        assert apdex_exit == 0

    def test_cli_error_handling_invalid_data(self):
        """Test CLI error handling with invalid data."""
        with pytest.raises(ValueError):
            parse_data_list("abc,def,ghi")

    def test_cli_json_output_is_valid(self, capsys):
        """Test that all JSON outputs are valid JSON."""
        class WebVitalsArgs:
            lcp = 2000.0
            fid = 50.0
            cls = 0.05
            inp = None
            ttfb = None
            fcp = None

        run_web_vitals(WebVitalsArgs(), "json")
        output = capsys.readouterr()

        try:
            json.loads(output.out)
            json_valid = True
        except json.JSONDecodeError:
            json_valid = False

        assert json_valid is True
