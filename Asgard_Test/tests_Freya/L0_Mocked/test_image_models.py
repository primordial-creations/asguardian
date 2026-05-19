"""
Comprehensive L0 Unit Tests for Freya Image Models

Tests all Pydantic models in the Images module including:
- ImageConfig model validation and defaults
- ImageInfo model field validation
- ImageIssue model construction
- ImageReport model with statistics and scoring
- Enum validation for ImageFormat, ImageIssueType, ImageIssueSeverity
"""

import pytest
import sys
import os
from datetime import datetime
from typing import List

# Add the Freya directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..', 'Asgard', 'Freya'))

try:
    from Images.models.image_models import (
        ImageConfig,
        ImageFormat,
        ImageInfo,
        ImageIssue,
        ImageIssueSeverity,
        ImageIssueType,
        ImageReport,
    )
    IMPORTS_AVAILABLE = True
except ImportError:
    IMPORTS_AVAILABLE = False


@pytest.mark.L0
@pytest.mark.freya
@pytest.mark.unit
class TestImageEnums:
    """Test Image enumeration types"""

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_issue_type_enum_has_all_types(self):
        """Test ImageIssueType enum contains all expected issue types"""
        expected_types = [
            "MISSING_ALT",
            "EMPTY_ALT",
            "MISSING_LAZY_LOADING",
            "NON_OPTIMIZED_FORMAT",
            "MISSING_DIMENSIONS",
            "OVERSIZED_IMAGE",
            "MISSING_SRCSET",
            "DECORATIVE_WITHOUT_EMPTY_ALT",
            "LARGE_FILE_SIZE",
        ]

        for expected_type in expected_types:
            assert hasattr(ImageIssueType, expected_type)

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_issue_severity_enum_has_all_levels(self):
        """Test ImageIssueSeverity enum contains all severity levels"""
        assert hasattr(ImageIssueSeverity, "CRITICAL")
        assert hasattr(ImageIssueSeverity, "WARNING")
        assert hasattr(ImageIssueSeverity, "INFO")

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_format_enum_has_all_formats(self):
        """Test ImageFormat enum contains all supported image formats"""
        expected_formats = [
            "JPEG", "JPG", "PNG", "GIF", "WEBP", "AVIF",
            "SVG", "ICO", "BMP", "TIFF", "UNKNOWN"
        ]

        for expected_format in expected_formats:
            assert hasattr(ImageFormat, expected_format)

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_format_enum_values_are_lowercase(self):
        """Test ImageFormat enum values are lowercase strings"""
        assert ImageFormat.JPEG.value == "jpeg"
        assert ImageFormat.PNG.value == "png"
        assert ImageFormat.WEBP.value == "webp"
        assert ImageFormat.AVIF.value == "avif"


@pytest.mark.L0
@pytest.mark.freya
@pytest.mark.unit
class TestImageConfig:
    """Test ImageConfig model"""

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_config_creates_with_defaults(self):
        """Test ImageConfig initializes with default values"""
        config = ImageConfig()

        assert config.check_alt_text is True
        assert config.check_lazy_loading is True
        assert config.check_formats is True
        assert config.check_dimensions is True
        assert config.check_oversized is True
        assert config.check_srcset is True

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_config_default_thresholds(self):
        """Test ImageConfig has correct default thresholds"""
        config = ImageConfig()

        assert config.oversized_threshold == 1.5
        assert config.large_file_threshold_kb == 200
        assert config.min_srcset_width == 768
        assert config.above_fold_height == 800

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_config_default_recommended_formats(self):
        """Test ImageConfig has correct default recommended formats"""
        config = ImageConfig()

        assert "webp" in config.recommended_formats
        assert "avif" in config.recommended_formats

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_config_accepts_custom_values(self):
        """Test ImageConfig accepts custom configuration values"""
        config = ImageConfig(
            check_alt_text=False,
            check_lazy_loading=False,
            oversized_threshold=2.0,
            large_file_threshold_kb=500,
        )

        assert config.check_alt_text is False
        assert config.check_lazy_loading is False
        assert config.oversized_threshold == 2.0
        assert config.large_file_threshold_kb == 500

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_config_skip_options(self):
        """Test ImageConfig skip options default values"""
        config = ImageConfig()

        assert config.skip_data_urls is True
        assert config.skip_svg is True
        assert config.skip_external_images is False

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_config_output_options(self):
        """Test ImageConfig output options"""
        config = ImageConfig()

        assert config.output_format == "text"
        assert config.include_all_images is False

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_config_accessibility_only_configuration(self):
        """Test ImageConfig can be configured for accessibility checks only"""
        config = ImageConfig(
            check_alt_text=True,
            check_lazy_loading=False,
            check_formats=False,
            check_dimensions=False,
            check_oversized=False,
            check_srcset=False,
        )

        assert config.check_alt_text is True
        assert config.check_lazy_loading is False
        assert config.check_formats is False

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_config_performance_only_configuration(self):
        """Test ImageConfig can be configured for performance checks only"""
        config = ImageConfig(
            check_alt_text=False,
            check_lazy_loading=True,
            check_formats=True,
            check_dimensions=True,
            check_oversized=True,
            check_srcset=True,
        )

        assert config.check_alt_text is False
        assert config.check_lazy_loading is True
        assert config.check_formats is True
        assert config.check_oversized is True


@pytest.mark.L0
@pytest.mark.freya
@pytest.mark.unit
class TestImageInfo:
    """Test ImageInfo model"""

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_info_creates_with_minimal_data(self):
        """Test ImageInfo can be created with just src"""
        image_info = ImageInfo(src="https://example.com/image.jpg")

        assert image_info.src == "https://example.com/image.jpg"
        assert image_info.alt is None
        assert image_info.has_alt is False
        assert image_info.has_dimensions is False

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_info_with_complete_data(self):
        """Test ImageInfo with all fields populated"""
        image_info = ImageInfo(
            src="https://example.com/image.jpg",
            alt="Test image",
            has_alt=True,
            width=800,
            height=600,
            has_dimensions=True,
            loading="lazy",
            has_lazy_loading=True,
            srcset="image-800.jpg 800w, image-1200.jpg 1200w",
            has_srcset=True,
            format=ImageFormat.JPEG,
            natural_width=1600,
            natural_height=1200,
            display_width=800,
            display_height=600,
            is_above_fold=True,
        )

        assert image_info.src == "https://example.com/image.jpg"
        assert image_info.alt == "Test image"
        assert image_info.has_alt is True
        assert image_info.width == 800
        assert image_info.height == 600
        assert image_info.has_dimensions is True
        assert image_info.loading == "lazy"
        assert image_info.has_lazy_loading is True
        assert image_info.has_srcset is True
        assert image_info.format == ImageFormat.JPEG

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_info_decorative_detection_fields(self):
        """Test ImageInfo decorative image detection fields"""
        image_info = ImageInfo(
            src="https://example.com/icon.svg",
            is_decorative=True,
            has_alt=True,
            alt="",
        )

        assert image_info.is_decorative is True
        assert image_info.alt == ""
        assert image_info.has_alt is True

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_info_background_image_flag(self):
        """Test ImageInfo can represent CSS background images"""
        image_info = ImageInfo(
            src="https://example.com/bg.jpg",
            is_background_image=True,
        )

        assert image_info.is_background_image is True

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_info_above_fold_detection(self):
        """Test ImageInfo above-fold detection"""
        above_fold = ImageInfo(
            src="https://example.com/hero.jpg",
            is_above_fold=True,
        )
        below_fold = ImageInfo(
            src="https://example.com/footer.jpg",
            is_above_fold=False,
        )

        assert above_fold.is_above_fold is True
        assert below_fold.is_above_fold is False

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_info_file_size_tracking(self):
        """Test ImageInfo tracks file size in bytes"""
        image_info = ImageInfo(
            src="https://example.com/large.jpg",
            file_size_bytes=512000,  # 500KB
        )

        assert image_info.file_size_bytes == 512000

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_info_element_metadata(self):
        """Test ImageInfo stores element HTML and CSS selector"""
        image_info = ImageInfo(
            src="https://example.com/image.jpg",
            element_html='<img src="image.jpg" alt="Test">',
            css_selector='img.hero-image',
        )

        assert image_info.element_html == '<img src="image.jpg" alt="Test">'
        assert image_info.css_selector == 'img.hero-image'

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_info_dimension_validation(self):
        """Test ImageInfo handles various dimension scenarios"""
        # With dimensions
        with_dims = ImageInfo(
            src="https://example.com/img.jpg",
            width=100,
            height=100,
            has_dimensions=True,
        )
        assert with_dims.has_dimensions is True

        # Without dimensions
        without_dims = ImageInfo(
            src="https://example.com/img.jpg",
            has_dimensions=False,
        )
        assert without_dims.has_dimensions is False


@pytest.mark.L0
@pytest.mark.freya
@pytest.mark.unit
class TestImageIssue:
    """Test ImageIssue model"""

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_issue_creates_with_required_fields(self):
        """Test ImageIssue creates with all required fields"""
        issue = ImageIssue(
            issue_type=ImageIssueType.MISSING_ALT,
            severity=ImageIssueSeverity.CRITICAL,
            image_src="https://example.com/image.jpg",
            description="Image is missing alt attribute",
            suggested_fix="Add an alt attribute",
            impact="Screen readers cannot describe the image",
        )

        assert issue.issue_type == ImageIssueType.MISSING_ALT
        assert issue.severity == ImageIssueSeverity.CRITICAL
        assert issue.image_src == "https://example.com/image.jpg"
        assert issue.description == "Image is missing alt attribute"
        assert issue.suggested_fix == "Add an alt attribute"
        assert issue.impact == "Screen readers cannot describe the image"

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_issue_with_wcag_reference(self):
        """Test ImageIssue can include WCAG criterion reference"""
        issue = ImageIssue(
            issue_type=ImageIssueType.MISSING_ALT,
            severity=ImageIssueSeverity.CRITICAL,
            image_src="https://example.com/image.jpg",
            description="Missing alt text",
            suggested_fix="Add alt attribute",
            impact="Accessibility issue",
            wcag_reference="WCAG 1.1.1 (Non-text Content)",
        )

        assert issue.wcag_reference == "WCAG 1.1.1 (Non-text Content)"

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_issue_performance_type(self):
        """Test ImageIssue for performance issues"""
        issue = ImageIssue(
            issue_type=ImageIssueType.OVERSIZED_IMAGE,
            severity=ImageIssueSeverity.WARNING,
            image_src="https://example.com/large.jpg",
            description="Image is 2.5x larger than displayed size",
            suggested_fix="Resize image or use srcset",
            impact="Wastes bandwidth and slows page load",
        )

        assert issue.issue_type == ImageIssueType.OVERSIZED_IMAGE
        assert issue.severity == ImageIssueSeverity.WARNING

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_issue_format_optimization(self):
        """Test ImageIssue for format optimization"""
        issue = ImageIssue(
            issue_type=ImageIssueType.NON_OPTIMIZED_FORMAT,
            severity=ImageIssueSeverity.WARNING,
            image_src="https://example.com/image.png",
            description="Image uses PNG instead of WebP",
            suggested_fix="Convert to WebP or AVIF format",
            impact="Could reduce file size by 25-50%",
        )

        assert issue.issue_type == ImageIssueType.NON_OPTIMIZED_FORMAT

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_issue_lazy_loading(self):
        """Test ImageIssue for lazy loading concerns"""
        issue = ImageIssue(
            issue_type=ImageIssueType.MISSING_LAZY_LOADING,
            severity=ImageIssueSeverity.WARNING,
            image_src="https://example.com/footer.jpg",
            description="Below-fold image without lazy loading",
            suggested_fix="Add loading='lazy' attribute",
            impact="Increases initial page weight",
        )

        assert issue.issue_type == ImageIssueType.MISSING_LAZY_LOADING

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_issue_with_element_context(self):
        """Test ImageIssue stores element HTML and CSS selector"""
        issue = ImageIssue(
            issue_type=ImageIssueType.MISSING_DIMENSIONS,
            severity=ImageIssueSeverity.WARNING,
            image_src="https://example.com/image.jpg",
            description="Missing width/height",
            suggested_fix="Add dimensions",
            impact="Causes layout shift",
            element_html='<img src="image.jpg">',
            css_selector='img.banner',
        )

        assert issue.element_html == '<img src="image.jpg">'
        assert issue.css_selector == 'img.banner'


@pytest.mark.L0
@pytest.mark.freya
@pytest.mark.unit
class TestImageReport:
    """Test ImageReport model"""

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_report_creates_with_minimal_data(self):
        """Test ImageReport creates with just URL"""
        report = ImageReport(url="https://example.com")

        assert report.url == "https://example.com"
        assert report.total_images == 0
        assert report.total_issues == 0
        assert report.analyzed_at is not None

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_report_with_images_and_issues(self):
        """Test ImageReport with images and issues"""
        images = [
            ImageInfo(src="https://example.com/img1.jpg"),
            ImageInfo(src="https://example.com/img2.jpg"),
        ]
        issues = [
            ImageIssue(
                issue_type=ImageIssueType.MISSING_ALT,
                severity=ImageIssueSeverity.CRITICAL,
                image_src="https://example.com/img1.jpg",
                description="Missing alt",
                suggested_fix="Add alt",
                impact="Accessibility",
            ),
        ]

        report = ImageReport(
            url="https://example.com",
            images=images,
            total_images=2,
            issues=issues,
            total_issues=1,
        )

        assert report.total_images == 2
        assert report.total_issues == 1
        assert len(report.images) == 2
        assert len(report.issues) == 1

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_report_issue_counts_by_type(self):
        """Test ImageReport tracks counts by issue type"""
        report = ImageReport(
            url="https://example.com",
            missing_alt_count=5,
            empty_alt_count=2,
            missing_lazy_loading_count=10,
            non_optimized_format_count=8,
            missing_dimensions_count=3,
            oversized_count=4,
            missing_srcset_count=6,
        )

        assert report.missing_alt_count == 5
        assert report.empty_alt_count == 2
        assert report.missing_lazy_loading_count == 10
        assert report.non_optimized_format_count == 8
        assert report.missing_dimensions_count == 3
        assert report.oversized_count == 4
        assert report.missing_srcset_count == 6

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_report_severity_counts(self):
        """Test ImageReport tracks counts by severity"""
        report = ImageReport(
            url="https://example.com",
            critical_count=3,
            warning_count=7,
            info_count=5,
        )

        assert report.critical_count == 3
        assert report.warning_count == 7
        assert report.info_count == 5

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_report_statistics(self):
        """Test ImageReport statistics fields"""
        report = ImageReport(
            url="https://example.com",
            total_image_bytes=1024000,  # 1MB
            potential_savings_bytes=512000,  # 500KB
            images_above_fold=3,
            images_with_lazy_loading=5,
            images_with_srcset=4,
            optimized_format_count=6,
        )

        assert report.total_image_bytes == 1024000
        assert report.potential_savings_bytes == 512000
        assert report.images_above_fold == 3
        assert report.images_with_lazy_loading == 5
        assert report.images_with_srcset == 4
        assert report.optimized_format_count == 6

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_report_format_breakdown(self):
        """Test ImageReport tracks format breakdown"""
        report = ImageReport(
            url="https://example.com",
            format_breakdown={
                "jpeg": 5,
                "png": 3,
                "webp": 2,
                "svg": 1,
            }
        )

        assert report.format_breakdown["jpeg"] == 5
        assert report.format_breakdown["png"] == 3
        assert report.format_breakdown["webp"] == 2
        assert report.format_breakdown["svg"] == 1

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_report_optimization_score(self):
        """Test ImageReport optimization score"""
        report = ImageReport(
            url="https://example.com",
            optimization_score=85.5,
        )

        assert report.optimization_score == 85.5

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_report_suggestions(self):
        """Test ImageReport suggestions list"""
        suggestions = [
            "Add alt text to 5 images",
            "Convert 8 images to WebP format",
            "Add lazy loading to 10 below-fold images",
        ]

        report = ImageReport(
            url="https://example.com",
            suggestions=suggestions,
        )

        assert len(report.suggestions) == 3
        assert "Add alt text to 5 images" in report.suggestions

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_report_has_issues_property(self):
        """Test ImageReport has_issues property"""
        with_issues = ImageReport(url="https://example.com", total_issues=5)
        without_issues = ImageReport(url="https://example.com", total_issues=0)

        assert with_issues.has_issues is True
        assert without_issues.has_issues is False

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_report_has_critical_issues_property(self):
        """Test ImageReport has_critical_issues property"""
        with_critical = ImageReport(url="https://example.com", critical_count=2)
        without_critical = ImageReport(url="https://example.com", critical_count=0)

        assert with_critical.has_critical_issues is True
        assert without_critical.has_critical_issues is False

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_report_has_accessibility_issues_property(self):
        """Test ImageReport has_accessibility_issues property"""
        with_alt_issues = ImageReport(url="https://example.com", missing_alt_count=3)
        without_alt_issues = ImageReport(url="https://example.com", missing_alt_count=0)

        assert with_alt_issues.has_accessibility_issues is True
        assert without_alt_issues.has_accessibility_issues is False

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_report_analysis_duration(self):
        """Test ImageReport tracks analysis duration"""
        report = ImageReport(
            url="https://example.com",
            analysis_duration_ms=1234.56,
        )

        assert report.analysis_duration_ms == 1234.56

    @pytest.mark.skipif(not IMPORTS_AVAILABLE, reason="Freya imports not available")
    def test_image_report_complete_scenario(self):
        """Test ImageReport with complete real-world scenario"""
        images = [
            ImageInfo(
                src="https://example.com/hero.jpg",
                has_alt=True,
                alt="Hero image",
                is_above_fold=True,
                format=ImageFormat.JPEG,
            ),
            ImageInfo(
                src="https://example.com/product.webp",
                has_alt=False,
                is_above_fold=False,
                format=ImageFormat.WEBP,
            ),
        ]

        issues = [
            ImageIssue(
                issue_type=ImageIssueType.MISSING_ALT,
                severity=ImageIssueSeverity.CRITICAL,
                image_src="https://example.com/product.webp",
                description="Missing alt attribute",
                suggested_fix="Add alt text",
                impact="Accessibility issue",
            ),
        ]

        report = ImageReport(
            url="https://example.com",
            images=images,
            total_images=2,
            issues=issues,
            total_issues=1,
            missing_alt_count=1,
            critical_count=1,
            images_above_fold=1,
            optimized_format_count=1,
            optimization_score=75.0,
            suggestions=["Add alt text to 1 image"],
        )

        assert report.total_images == 2
        assert report.has_issues is True
        assert report.has_critical_issues is True
        assert report.has_accessibility_issues is True
        assert report.optimization_score == 75.0
