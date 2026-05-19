"""Tests for Asgard config models."""
import pytest
from Asgard.config.models import (
    AsgardConfig,
    BrowserType,
    CICDPlatform,
    GlobalConfig,
    HeimdallConfig,
    OutputFormat,
    ScreenshotFormat,
    TerraformBackend,
)


class TestConfigModelsInstantiation:
    def test_asgard_config_can_be_instantiated(self):
        assert AsgardConfig() is not None

    def test_global_config_can_be_instantiated(self):
        assert GlobalConfig() is not None

    def test_heimdall_config_can_be_instantiated(self):
        assert HeimdallConfig() is not None


class TestConfigModelsCleanPath:
    def test_output_format_values(self):
        assert OutputFormat.TEXT == "text"
        assert OutputFormat.JSON == "json"
        assert OutputFormat.MARKDOWN == "markdown"

    def test_browser_type_values(self):
        assert BrowserType.CHROMIUM == "chromium"
        assert BrowserType.FIREFOX == "firefox"
        assert BrowserType.WEBKIT == "webkit"

    def test_screenshot_format_values(self):
        assert ScreenshotFormat.PNG == "png"
        assert ScreenshotFormat.JPEG == "jpeg"

    def test_cicd_platform_values(self):
        assert CICDPlatform.GITHUB_ACTIONS == "github_actions"

    def test_terraform_backend_values(self):
        assert TerraformBackend.LOCAL == "local"
        assert TerraformBackend.S3 == "s3"

    def test_asgard_config_has_global_config(self):
        config = AsgardConfig()
        assert hasattr(config, "global_config")
        assert isinstance(config.global_config, GlobalConfig)

    def test_asgard_config_has_heimdall(self):
        config = AsgardConfig()
        assert hasattr(config, "heimdall")
        assert isinstance(config.heimdall, HeimdallConfig)


class TestConfigModelsEdgeCases:
    def test_global_config_verbose_default_is_bool(self):
        config = GlobalConfig()
        assert isinstance(config.verbose, bool)

    def test_asgard_config_model_dump_roundtrip(self):
        config = AsgardConfig()
        data = config.model_dump()
        assert isinstance(data, dict)

    def test_output_format_all_members(self):
        members = {f.value for f in OutputFormat}
        assert "text" in members
        assert "json" in members
        assert "markdown" in members
        assert "html" in members
        assert "github" in members
