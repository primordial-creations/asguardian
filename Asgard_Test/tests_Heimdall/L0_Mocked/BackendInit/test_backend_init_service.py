"""
L0 Unit Tests for BackendInit Service

Tests the backend project scaffolding service, including filesystem operations,
gitignore management, and the top-level init_backend orchestration function.
"""

import pytest
from pathlib import Path

from Asgard.BackendInit.service import _write_if_absent, _ensure_gitignore, init_backend
from Asgard.BackendInit.templates import (
    APIS_INIT,
    CODING_STANDARDS,
    ENV_EXAMPLE,
    GITIGNORE_ENTRIES,
    GITIGNORE_FULL,
    MODELS_ENUMS,
    MODELS_INIT,
    PROMPTS_INIT,
    README,
    SERVICES_INIT,
    TESTS_INIT,
    UTILITIES_INIT,
)


@pytest.mark.L0
@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.backend_init
class TestWriteIfAbsent:
    """Tests for the _write_if_absent helper function."""

    def test_writes_file_when_absent_returns_true(self, tmp_path: Path) -> None:
        # Arrange
        target = tmp_path / "new_file.txt"
        content = "hello world"

        # Act
        result = _write_if_absent(target, content)

        # Assert
        assert result is True

    def test_skips_file_when_already_exists_returns_false(self, tmp_path: Path) -> None:
        # Arrange
        target = tmp_path / "existing_file.txt"
        target.write_text("original", encoding="utf-8")

        # Act
        result = _write_if_absent(target, "new content")

        # Assert
        assert result is False

    def test_written_content_matches_supplied_content(self, tmp_path: Path) -> None:
        # Arrange
        target = tmp_path / "output.txt"
        content = "exact content to write"

        # Act
        _write_if_absent(target, content)

        # Assert
        assert target.read_text(encoding="utf-8") == content

    def test_existing_file_content_is_not_overwritten(self, tmp_path: Path) -> None:
        # Arrange
        target = tmp_path / "existing.txt"
        original = "original content"
        target.write_text(original, encoding="utf-8")

        # Act
        _write_if_absent(target, "replacement content")

        # Assert
        assert target.read_text(encoding="utf-8") == original


@pytest.mark.L0
@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.backend_init
class TestEnsureGitignore:
    """Tests for the _ensure_gitignore helper function."""

    def test_creates_full_gitignore_when_file_absent(self, tmp_path: Path) -> None:
        # Arrange
        gitignore = tmp_path / ".gitignore"

        # Act
        _ensure_gitignore(gitignore)

        # Assert
        assert gitignore.exists()

    def test_created_gitignore_content_matches_template(self, tmp_path: Path) -> None:
        # Arrange
        gitignore = tmp_path / ".gitignore"

        # Act
        _ensure_gitignore(gitignore)

        # Assert
        assert gitignore.read_text(encoding="utf-8") == GITIGNORE_FULL

    def test_created_gitignore_contains_claude_entry(self, tmp_path: Path) -> None:
        # Arrange
        gitignore = tmp_path / ".gitignore"

        # Act
        _ensure_gitignore(gitignore)

        # Assert
        content = gitignore.read_text(encoding="utf-8")
        assert ".claude" in content

    def test_created_gitignore_contains_claude_team_entry(self, tmp_path: Path) -> None:
        # Arrange
        gitignore = tmp_path / ".gitignore"

        # Act
        _ensure_gitignore(gitignore)

        # Assert
        content = gitignore.read_text(encoding="utf-8")
        assert "Claude Team" in content

    def test_created_gitignore_contains_env_entry(self, tmp_path: Path) -> None:
        # Arrange
        gitignore = tmp_path / ".gitignore"

        # Act
        _ensure_gitignore(gitignore)

        # Assert
        content = gitignore.read_text(encoding="utf-8")
        assert ".env" in content

    def test_skips_when_all_entries_already_present(self, tmp_path: Path) -> None:
        # Arrange
        gitignore = tmp_path / ".gitignore"
        existing = ".claude\nClaude Team\n.env\n"
        gitignore.write_text(existing, encoding="utf-8")

        # Act
        _ensure_gitignore(gitignore)

        # Assert - content should be unchanged
        assert gitignore.read_text(encoding="utf-8") == existing

    def test_adds_only_missing_entries_when_partially_present(self, tmp_path: Path) -> None:
        # Arrange
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(".claude\n", encoding="utf-8")

        # Act
        _ensure_gitignore(gitignore)

        # Assert
        content = gitignore.read_text(encoding="utf-8")
        assert "Claude Team" in content
        assert ".env" in content
        assert ".claude" in content

    def test_does_not_duplicate_already_present_entry(self, tmp_path: Path) -> None:
        # Arrange
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(".claude\n", encoding="utf-8")

        # Act
        _ensure_gitignore(gitignore)

        # Assert - .claude should appear exactly once
        content = gitignore.read_text(encoding="utf-8")
        assert content.count(".claude") == 1

    def test_entry_with_trailing_slash_counts_as_present_for_dotclaude(self, tmp_path: Path) -> None:
        # Arrange - .claude listed with trailing slash
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(".claude/\nClaude Team\n.env\n", encoding="utf-8")

        # Act
        _ensure_gitignore(gitignore)

        # Assert - should not add .claude again
        content = gitignore.read_text(encoding="utf-8")
        assert content.count(".claude") == 1

    def test_entry_with_trailing_slash_counts_as_present_for_claude_team(self, tmp_path: Path) -> None:
        # Arrange - "Claude Team" listed with trailing slash
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(".claude\nClaude Team/\n.env\n", encoding="utf-8")

        # Act
        _ensure_gitignore(gitignore)

        # Assert - should not add "Claude Team" again
        content = gitignore.read_text(encoding="utf-8")
        assert content.count("Claude Team") == 1

    def test_separator_is_single_newline_when_content_ends_with_newline(self, tmp_path: Path) -> None:
        # Arrange - content already ends with newline, missing entries
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(".claude\n", encoding="utf-8")

        # Act
        _ensure_gitignore(gitignore)

        # Assert - only one newline between existing content and appended block
        content = gitignore.read_text(encoding="utf-8")
        assert "\n\n\n" not in content

    def test_separator_is_double_newline_when_content_does_not_end_with_newline(
        self, tmp_path: Path
    ) -> None:
        # Arrange - content does NOT end with newline, missing entries
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(".claude", encoding="utf-8")

        # Act
        _ensure_gitignore(gitignore)

        # Assert - double newline separator used before appended block
        content = gitignore.read_text(encoding="utf-8")
        assert "\n\n# Added by asgard init-backend\n" in content


@pytest.mark.L0
@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.backend_init
class TestInitBackend:
    """Tests for the init_backend orchestration function."""

    def test_returns_zero_on_success(self, tmp_path: Path) -> None:
        # Arrange / Act
        result = init_backend("myproject", base_dir=tmp_path)

        # Assert
        assert result == 0

    def test_creates_root_folder_when_absent(self, tmp_path: Path) -> None:
        # Arrange
        expected = tmp_path / "newproject"
        assert not expected.exists()

        # Act
        init_backend("newproject", base_dir=tmp_path)

        # Assert
        assert expected.is_dir()

    def test_creates_apis_subdirectory(self, tmp_path: Path) -> None:
        # Act
        init_backend("proj", base_dir=tmp_path)

        # Assert
        assert (tmp_path / "proj" / "apis").is_dir()

    def test_creates_models_subdirectory(self, tmp_path: Path) -> None:
        # Act
        init_backend("proj", base_dir=tmp_path)

        # Assert
        assert (tmp_path / "proj" / "models").is_dir()

    def test_creates_services_subdirectory(self, tmp_path: Path) -> None:
        # Act
        init_backend("proj", base_dir=tmp_path)

        # Assert
        assert (tmp_path / "proj" / "services").is_dir()

    def test_creates_prompts_subdirectory(self, tmp_path: Path) -> None:
        # Act
        init_backend("proj", base_dir=tmp_path)

        # Assert
        assert (tmp_path / "proj" / "prompts").is_dir()

    def test_creates_tests_subdirectory(self, tmp_path: Path) -> None:
        # Act
        init_backend("proj", base_dir=tmp_path)

        # Assert
        assert (tmp_path / "proj" / "tests").is_dir()

    def test_creates_utilities_subdirectory(self, tmp_path: Path) -> None:
        # Act
        init_backend("proj", base_dir=tmp_path)

        # Assert
        assert (tmp_path / "proj" / "utilities").is_dir()

    def test_creates_apis_init_with_correct_content(self, tmp_path: Path) -> None:
        # Act
        init_backend("proj", base_dir=tmp_path)

        # Assert
        content = (tmp_path / "proj" / "apis" / "__init__.py").read_text(encoding="utf-8")
        assert content == APIS_INIT

    def test_creates_models_init_with_correct_content(self, tmp_path: Path) -> None:
        # Act
        init_backend("proj", base_dir=tmp_path)

        # Assert
        content = (tmp_path / "proj" / "models" / "__init__.py").read_text(encoding="utf-8")
        assert content == MODELS_INIT

    def test_creates_services_init_with_correct_content(self, tmp_path: Path) -> None:
        # Act
        init_backend("proj", base_dir=tmp_path)

        # Assert
        content = (tmp_path / "proj" / "services" / "__init__.py").read_text(encoding="utf-8")
        assert content == SERVICES_INIT

    def test_creates_prompts_init_with_correct_content(self, tmp_path: Path) -> None:
        # Act
        init_backend("proj", base_dir=tmp_path)

        # Assert
        content = (tmp_path / "proj" / "prompts" / "__init__.py").read_text(encoding="utf-8")
        assert content == PROMPTS_INIT

    def test_creates_tests_init_with_correct_content(self, tmp_path: Path) -> None:
        # Act
        init_backend("proj", base_dir=tmp_path)

        # Assert
        content = (tmp_path / "proj" / "tests" / "__init__.py").read_text(encoding="utf-8")
        assert content == TESTS_INIT

    def test_creates_utilities_init_with_correct_content(self, tmp_path: Path) -> None:
        # Act
        init_backend("proj", base_dir=tmp_path)

        # Assert
        content = (tmp_path / "proj" / "utilities" / "__init__.py").read_text(encoding="utf-8")
        assert content == UTILITIES_INIT

    def test_creates_models_enums_with_correct_content(self, tmp_path: Path) -> None:
        # Act
        init_backend("proj", base_dir=tmp_path)

        # Assert
        content = (tmp_path / "proj" / "models" / "enums.py").read_text(encoding="utf-8")
        assert content == MODELS_ENUMS

    def test_creates_coding_standards_md(self, tmp_path: Path) -> None:
        # Act
        init_backend("proj", base_dir=tmp_path)

        # Assert
        file = tmp_path / "proj" / "coding_standards.md"
        assert file.exists()
        assert file.read_text(encoding="utf-8") == CODING_STANDARDS

    def test_creates_readme_md(self, tmp_path: Path) -> None:
        # Act
        init_backend("proj", base_dir=tmp_path)

        # Assert
        file = tmp_path / "proj" / "readme.md"
        assert file.exists()
        assert file.read_text(encoding="utf-8") == README

    def test_creates_env_example(self, tmp_path: Path) -> None:
        # Act
        init_backend("proj", base_dir=tmp_path)

        # Assert
        file = tmp_path / "proj" / ".env.example"
        assert file.exists()
        assert file.read_text(encoding="utf-8") == ENV_EXAMPLE

    def test_creates_env_file(self, tmp_path: Path) -> None:
        # Act
        init_backend("proj", base_dir=tmp_path)

        # Assert
        assert (tmp_path / "proj" / ".env").exists()

    def test_creates_gitignore_when_absent(self, tmp_path: Path) -> None:
        # Act
        init_backend("proj", base_dir=tmp_path)

        # Assert
        assert (tmp_path / "proj" / ".gitignore").exists()

    def test_does_not_overwrite_existing_init_py(self, tmp_path: Path) -> None:
        # Arrange - pre-create the apis __init__.py with custom content
        root = tmp_path / "proj"
        apis_dir = root / "apis"
        apis_dir.mkdir(parents=True)
        custom_content = "# custom content"
        (apis_dir / "__init__.py").write_text(custom_content, encoding="utf-8")

        # Act
        init_backend("proj", base_dir=tmp_path)

        # Assert - custom content must be preserved
        content = (apis_dir / "__init__.py").read_text(encoding="utf-8")
        assert content == custom_content

    def test_does_not_overwrite_existing_coding_standards(self, tmp_path: Path) -> None:
        # Arrange
        root = tmp_path / "proj"
        root.mkdir(parents=True)
        custom = "# my own standards"
        (root / "coding_standards.md").write_text(custom, encoding="utf-8")

        # Act
        init_backend("proj", base_dir=tmp_path)

        # Assert
        assert (root / "coding_standards.md").read_text(encoding="utf-8") == custom

    def test_does_not_overwrite_existing_readme(self, tmp_path: Path) -> None:
        # Arrange
        root = tmp_path / "proj"
        root.mkdir(parents=True)
        custom = "# My Custom README"
        (root / "readme.md").write_text(custom, encoding="utf-8")

        # Act
        init_backend("proj", base_dir=tmp_path)

        # Assert
        assert (root / "readme.md").read_text(encoding="utf-8") == custom

    def test_does_not_overwrite_existing_env_example(self, tmp_path: Path) -> None:
        # Arrange
        root = tmp_path / "proj"
        root.mkdir(parents=True)
        custom = "# custom env example"
        (root / ".env.example").write_text(custom, encoding="utf-8")

        # Act
        init_backend("proj", base_dir=tmp_path)

        # Assert
        assert (root / ".env.example").read_text(encoding="utf-8") == custom

    def test_does_not_overwrite_existing_env_file(self, tmp_path: Path) -> None:
        # Arrange
        root = tmp_path / "proj"
        root.mkdir(parents=True)
        custom = "SECRET_KEY=abc123"
        (root / ".env").write_text(custom, encoding="utf-8")

        # Act
        init_backend("proj", base_dir=tmp_path)

        # Assert
        assert (root / ".env").read_text(encoding="utf-8") == custom

    def test_uses_provided_base_dir(self, tmp_path: Path) -> None:
        # Arrange
        base = tmp_path / "custom_base"
        base.mkdir()

        # Act
        init_backend("proj", base_dir=base)

        # Assert
        assert (base / "proj").is_dir()

    def test_idempotent_when_target_folder_already_exists(self, tmp_path: Path) -> None:
        # Arrange - run once to scaffold
        init_backend("proj", base_dir=tmp_path)

        # Act - run again on the same folder
        result = init_backend("proj", base_dir=tmp_path)

        # Assert - succeeds without error, returns 0
        assert result == 0

    def test_idempotent_preserves_existing_init_files(self, tmp_path: Path) -> None:
        # Arrange - run once to scaffold
        init_backend("proj", base_dir=tmp_path)
        apis_init = tmp_path / "proj" / "apis" / "__init__.py"
        original_content = apis_init.read_text(encoding="utf-8")

        # Act - run again
        init_backend("proj", base_dir=tmp_path)

        # Assert - content unchanged
        assert apis_init.read_text(encoding="utf-8") == original_content

    def test_updates_existing_gitignore_missing_entries(self, tmp_path: Path) -> None:
        # Arrange - create a partial .gitignore before init
        root = tmp_path / "proj"
        root.mkdir(parents=True)
        (root / ".gitignore").write_text("*.pyc\n", encoding="utf-8")

        # Act
        init_backend("proj", base_dir=tmp_path)

        # Assert - all required entries are present
        content = (root / ".gitignore").read_text(encoding="utf-8")
        for entry in GITIGNORE_ENTRIES:
            assert entry in content
