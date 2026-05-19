"""
Tests for Asgard GitHub and GitLab PR Decorator Services

Unit tests for posting analysis results to pull requests and merge requests.
HTTP calls are mocked using unittest.mock.patch on urllib.request.urlopen.
"""

import io
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from Asgard.Reporting.PRDecoration.models.decoration_models import (
    IssueComment,
    PRDecorationConfig,
    PRDecorationResult,
    PRPlatform,
)
from Asgard.Reporting.PRDecoration.services.github_decorator import GitHubDecorator
from Asgard.Reporting.PRDecoration.services.gitlab_decorator import GitLabDecorator


def _make_github_config(
    post_summary: bool = True,
    post_inline: bool = False,
) -> PRDecorationConfig:
    """Helper to build a minimal GitHub PRDecorationConfig."""
    return PRDecorationConfig(
        platform=PRPlatform.GITHUB,
        api_token="test-github-token",
        repository="test-owner/test-repo",
        pr_number=42,
        post_summary=post_summary,
        post_inline_comments=post_inline,
    )


def _make_gitlab_config(
    post_summary: bool = True,
    post_inline: bool = False,
) -> PRDecorationConfig:
    """Helper to build a minimal GitLab PRDecorationConfig."""
    return PRDecorationConfig(
        platform=PRPlatform.GITLAB,
        api_token="test-gitlab-token",
        repository="test-group/test-project",
        pr_number=17,
        post_summary=post_summary,
        post_inline_comments=post_inline,
        gitlab_api_url="https://gitlab.com/api/v4",
    )


def _make_urlopen_mock(response_body: dict):
    """Return a context-manager mock that yields a response with the given JSON body."""
    encoded = json.dumps(response_body).encode("utf-8")
    mock_response = MagicMock()
    mock_response.read.return_value = encoded
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


class TestGitHubDecoratorSummaryComment:
    """Tests for GitHubDecorator posting summary comments."""

    def test_post_summary_calls_github_issues_endpoint(self):
        """decorate() posts summary to /repos/{owner}/{repo}/issues/{pr}/comments."""
        config = _make_github_config(post_summary=True, post_inline=False)
        decorator = GitHubDecorator()

        mock_response = _make_urlopen_mock(
            {"id": 1, "html_url": "https://github.com/test-owner/test-repo/issues/42#comment-1"}
        )
        with patch(
            "Asgard.Reporting.PRDecoration.services.github_decorator.urllib_request.urlopen",
            return_value=mock_response,
        ) as mock_urlopen:
            result = decorator.decorate(config, issues=[], gate_result=None, ratings=None)

        assert mock_urlopen.called
        called_request = mock_urlopen.call_args[0][0]
        assert "/repos/test-owner/test-repo/issues/42/comments" in called_request.full_url

    def test_post_summary_success_sets_summary_posted(self):
        """A successful summary post sets summary_posted=True on the result."""
        config = _make_github_config(post_summary=True, post_inline=False)
        decorator = GitHubDecorator()

        mock_response = _make_urlopen_mock(
            {"id": 1, "html_url": "https://github.com/test-owner/test-repo/issues/42#comment-1"}
        )
        with patch(
            "Asgard.Reporting.PRDecoration.services.github_decorator.urllib_request.urlopen",
            return_value=mock_response,
        ):
            result = decorator.decorate(config, issues=[], gate_result=None, ratings=None)

        assert result.summary_posted is True

    def test_post_summary_captures_decoration_url(self):
        """The html_url from the API response is stored as decoration_url."""
        config = _make_github_config(post_summary=True, post_inline=False)
        decorator = GitHubDecorator()
        expected_url = "https://github.com/test-owner/test-repo/issues/42#comment-99"

        mock_response = _make_urlopen_mock({"id": 99, "html_url": expected_url})
        with patch(
            "Asgard.Reporting.PRDecoration.services.github_decorator.urllib_request.urlopen",
            return_value=mock_response,
        ):
            result = decorator.decorate(config, issues=[], gate_result=None, ratings=None)

        assert result.decoration_url == expected_url

    def test_post_summary_includes_quality_gate_status(self):
        """The summary comment body includes the quality gate status."""
        config = _make_github_config(post_summary=True, post_inline=False)
        decorator = GitHubDecorator()

        gate_result = SimpleNamespace(status="passed")
        mock_response = _make_urlopen_mock({"id": 1, "html_url": "https://example.com"})

        posted_bodies = []

        def capture_urlopen(req, timeout=None):
            body_data = json.loads(req.data.decode("utf-8"))
            posted_bodies.append(body_data.get("body", ""))
            return mock_response

        with patch(
            "Asgard.Reporting.PRDecoration.services.github_decorator.urllib_request.urlopen",
            side_effect=capture_urlopen,
        ):
            decorator.decorate(config, issues=[], gate_result=gate_result, ratings=None)

        assert len(posted_bodies) == 1
        assert "PASSED" in posted_bodies[0]

    def test_http_error_results_in_failed_result(self):
        """An HTTP error when posting causes summary_posted=False with error details."""
        from urllib.error import HTTPError

        config = _make_github_config(post_summary=True, post_inline=False)
        decorator = GitHubDecorator()

        http_error = HTTPError(
            url="https://api.github.com/...",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=None,
        )
        with patch(
            "Asgard.Reporting.PRDecoration.services.github_decorator.urllib_request.urlopen",
            side_effect=http_error,
        ):
            result = decorator.decorate(config, issues=[], gate_result=None, ratings=None)

        assert result.summary_posted is False
        assert len(result.errors) > 0
        assert "401" in result.errors[0]

    def test_url_error_results_in_failed_result(self):
        """A URLError when posting causes summary_posted=False with error details."""
        from urllib.error import URLError

        config = _make_github_config(post_summary=True, post_inline=False)
        decorator = GitHubDecorator()

        url_error = URLError(reason="Connection refused")
        with patch(
            "Asgard.Reporting.PRDecoration.services.github_decorator.urllib_request.urlopen",
            side_effect=url_error,
        ):
            result = decorator.decorate(config, issues=[], gate_result=None, ratings=None)

        assert result.summary_posted is False
        assert len(result.errors) > 0


class TestGitHubDecoratorInlineComments:
    """Tests for GitHubDecorator posting inline review comments."""

    def test_inline_comments_call_pulls_endpoint(self):
        """Inline comments are posted to /repos/{owner}/{repo}/pulls/{pr}/comments."""
        config = _make_github_config(post_summary=False, post_inline=True)
        decorator = GitHubDecorator()

        issues = [
            IssueComment(
                file_path="src/main.py",
                line_number=10,
                message="Cyclomatic complexity too high",
                severity="warning",
                rule_id="quality.cyclomatic_complexity",
            )
        ]

        sha_response = _make_urlopen_mock({"head": {"sha": "abc123def456"}})
        comment_response = _make_urlopen_mock({"id": 5, "html_url": "https://example.com"})
        call_count = [0]

        def side_effect(req, timeout=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return sha_response
            return comment_response

        with patch(
            "Asgard.Reporting.PRDecoration.services.github_decorator.urllib_request.urlopen",
            side_effect=side_effect,
        ) as mock_urlopen:
            result = decorator.decorate(config, issues=issues, gate_result=None, ratings=None)

        assert result.inline_comments_posted == 1
        assert result.errors == []

    def test_inline_comment_http_error_recorded_in_errors(self):
        """HTTP errors on individual inline comments are recorded without crashing."""
        from urllib.error import HTTPError

        config = _make_github_config(post_summary=False, post_inline=True)
        decorator = GitHubDecorator()

        issues = [
            IssueComment(
                file_path="src/main.py",
                line_number=5,
                message="Issue here",
                severity="error",
                rule_id="security.hardcoded_secrets",
            )
        ]

        sha_response = _make_urlopen_mock({"head": {"sha": "abc123def456"}})
        call_count = [0]

        def side_effect(req, timeout=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return sha_response
            raise HTTPError(url="", code=422, msg="Unprocessable Entity", hdrs=None, fp=None)

        with patch(
            "Asgard.Reporting.PRDecoration.services.github_decorator.urllib_request.urlopen",
            side_effect=side_effect,
        ):
            result = decorator.decorate(config, issues=issues, gate_result=None, ratings=None)

        assert result.inline_comments_posted == 0
        assert len(result.errors) > 0


class TestGitHubDecoratorResult:
    """Tests for PRDecorationResult structure from GitHubDecorator."""

    def test_result_has_correct_platform(self):
        """Result platform matches github."""
        config = _make_github_config(post_summary=False, post_inline=False)
        decorator = GitHubDecorator()

        with patch(
            "Asgard.Reporting.PRDecoration.services.github_decorator.urllib_request.urlopen"
        ):
            result = decorator.decorate(config, issues=[], gate_result=None, ratings=None)

        assert result.platform == PRPlatform.GITHUB

    def test_result_has_correct_pr_number(self):
        """Result pr_number matches the config pr_number."""
        config = _make_github_config(post_summary=False, post_inline=False)
        decorator = GitHubDecorator()

        with patch(
            "Asgard.Reporting.PRDecoration.services.github_decorator.urllib_request.urlopen"
        ):
            result = decorator.decorate(config, issues=[], gate_result=None, ratings=None)

        assert result.pr_number == 42


class TestGitLabDecoratorSummaryNote:
    """Tests for GitLabDecorator posting summary notes."""

    def test_post_summary_calls_gitlab_notes_endpoint(self):
        """decorate() posts summary to /projects/{repo}/merge_requests/{mr}/notes."""
        config = _make_gitlab_config(post_summary=True, post_inline=False)
        decorator = GitLabDecorator()

        mock_response = _make_urlopen_mock(
            {"id": 1, "web_url": "https://gitlab.com/test-group/test-project/-/merge_requests/17#note_1"}
        )
        with patch(
            "Asgard.Reporting.PRDecoration.services.gitlab_decorator.urllib_request.urlopen",
            return_value=mock_response,
        ) as mock_urlopen:
            result = decorator.decorate(config, issues=[], gate_result=None, ratings=None)

        assert mock_urlopen.called
        called_request = mock_urlopen.call_args[0][0]
        assert "merge_requests/17/notes" in called_request.full_url

    def test_post_summary_success_sets_summary_posted(self):
        """A successful summary note sets summary_posted=True."""
        config = _make_gitlab_config(post_summary=True, post_inline=False)
        decorator = GitLabDecorator()

        mock_response = _make_urlopen_mock({"id": 1, "web_url": "https://gitlab.com/example"})
        with patch(
            "Asgard.Reporting.PRDecoration.services.gitlab_decorator.urllib_request.urlopen",
            return_value=mock_response,
        ):
            result = decorator.decorate(config, issues=[], gate_result=None, ratings=None)

        assert result.summary_posted is True

    def test_post_summary_captures_web_url(self):
        """The web_url from the GitLab API response is stored as decoration_url."""
        config = _make_gitlab_config(post_summary=True, post_inline=False)
        decorator = GitLabDecorator()
        expected_url = "https://gitlab.com/test-group/test-project/-/merge_requests/17#note_42"

        mock_response = _make_urlopen_mock({"id": 42, "web_url": expected_url})
        with patch(
            "Asgard.Reporting.PRDecoration.services.gitlab_decorator.urllib_request.urlopen",
            return_value=mock_response,
        ):
            result = decorator.decorate(config, issues=[], gate_result=None, ratings=None)

        assert result.decoration_url == expected_url

    def test_post_summary_includes_quality_gate_status(self):
        """The summary note body includes the quality gate status."""
        config = _make_gitlab_config(post_summary=True, post_inline=False)
        decorator = GitLabDecorator()

        gate_result = SimpleNamespace(status="failed")
        mock_response = _make_urlopen_mock({"id": 1, "web_url": "https://example.com"})

        posted_bodies = []

        def capture_urlopen(req, timeout=None):
            body_data = json.loads(req.data.decode("utf-8"))
            posted_bodies.append(body_data.get("body", ""))
            return mock_response

        with patch(
            "Asgard.Reporting.PRDecoration.services.gitlab_decorator.urllib_request.urlopen",
            side_effect=capture_urlopen,
        ):
            decorator.decorate(config, issues=[], gate_result=gate_result, ratings=None)

        assert len(posted_bodies) == 1
        assert "FAILED" in posted_bodies[0]

    def test_http_error_results_in_failed_result(self):
        """An HTTP error when posting a note causes summary_posted=False with errors."""
        from urllib.error import HTTPError

        config = _make_gitlab_config(post_summary=True, post_inline=False)
        decorator = GitLabDecorator()

        http_error = HTTPError(url="", code=403, msg="Forbidden", hdrs=None, fp=None)
        with patch(
            "Asgard.Reporting.PRDecoration.services.gitlab_decorator.urllib_request.urlopen",
            side_effect=http_error,
        ):
            result = decorator.decorate(config, issues=[], gate_result=None, ratings=None)

        assert result.summary_posted is False
        assert len(result.errors) > 0
        assert "403" in result.errors[0]

    def test_url_error_results_in_failed_result(self):
        """A URLError when posting causes summary_posted=False with error details."""
        from urllib.error import URLError

        config = _make_gitlab_config(post_summary=True, post_inline=False)
        decorator = GitLabDecorator()

        url_error = URLError(reason="Network unreachable")
        with patch(
            "Asgard.Reporting.PRDecoration.services.gitlab_decorator.urllib_request.urlopen",
            side_effect=url_error,
        ):
            result = decorator.decorate(config, issues=[], gate_result=None, ratings=None)

        assert result.summary_posted is False
        assert len(result.errors) > 0

    def test_raises_valueerror_when_no_gitlab_api_url(self):
        """decorate() raises ValueError when gitlab_api_url is missing."""
        config = PRDecorationConfig(
            platform=PRPlatform.GITLAB,
            api_token="token",
            repository="group/project",
            pr_number=1,
            gitlab_api_url=None,
        )
        decorator = GitLabDecorator()

        with pytest.raises(ValueError, match="gitlab_api_url"):
            decorator.decorate(config, issues=[], gate_result=None, ratings=None)


class TestGitLabDecoratorInlineDiscussions:
    """Tests for GitLabDecorator posting inline discussion comments."""

    def test_inline_comments_call_discussions_endpoint(self):
        """Inline comments are posted to .../merge_requests/{mr}/discussions."""
        config = _make_gitlab_config(post_summary=False, post_inline=True)
        decorator = GitLabDecorator()

        issues = [
            IssueComment(
                file_path="src/app.py",
                line_number=20,
                message="Security issue",
                severity="error",
                rule_id="security.sql_injection",
            )
        ]

        mock_response = _make_urlopen_mock({"id": "disc1"})
        with patch(
            "Asgard.Reporting.PRDecoration.services.gitlab_decorator.urllib_request.urlopen",
            return_value=mock_response,
        ) as mock_urlopen:
            result = decorator.decorate(config, issues=issues, gate_result=None, ratings=None)

        assert mock_urlopen.called
        called_request = mock_urlopen.call_args[0][0]
        assert "merge_requests/17/discussions" in called_request.full_url
        assert result.inline_comments_posted == 1

    def test_inline_comment_http_error_recorded_in_errors(self):
        """HTTP errors on inline discussion posts are recorded without crashing."""
        from urllib.error import HTTPError

        config = _make_gitlab_config(post_summary=False, post_inline=True)
        decorator = GitLabDecorator()

        issues = [
            IssueComment(
                file_path="src/app.py",
                line_number=15,
                message="Issue",
                severity="warning",
                rule_id="quality.complexity",
            )
        ]

        http_error = HTTPError(url="", code=400, msg="Bad Request", hdrs=None, fp=None)
        with patch(
            "Asgard.Reporting.PRDecoration.services.gitlab_decorator.urllib_request.urlopen",
            side_effect=http_error,
        ):
            result = decorator.decorate(config, issues=issues, gate_result=None, ratings=None)

        assert result.inline_comments_posted == 0
        assert len(result.errors) > 0


class TestGitLabDecoratorResult:
    """Tests for PRDecorationResult structure from GitLabDecorator."""

    def test_result_has_correct_platform(self):
        """Result platform matches gitlab."""
        config = _make_gitlab_config(post_summary=False, post_inline=False)
        decorator = GitLabDecorator()

        with patch(
            "Asgard.Reporting.PRDecoration.services.gitlab_decorator.urllib_request.urlopen"
        ):
            result = decorator.decorate(config, issues=[], gate_result=None, ratings=None)

        assert result.platform == PRPlatform.GITLAB

    def test_result_has_correct_pr_number(self):
        """Result pr_number matches the config pr_number."""
        config = _make_gitlab_config(post_summary=False, post_inline=False)
        decorator = GitLabDecorator()

        with patch(
            "Asgard.Reporting.PRDecoration.services.gitlab_decorator.urllib_request.urlopen"
        ):
            result = decorator.decorate(config, issues=[], gate_result=None, ratings=None)

        assert result.pr_number == 17


class TestSummaryCommentContent:
    """Tests for summary comment content generated by decorators."""

    def test_github_summary_lists_issue_counts(self):
        """GitHub summary includes total issue count, errors, warnings, and info."""
        config = _make_github_config(post_summary=True, post_inline=False)
        decorator = GitHubDecorator()

        issues = [
            IssueComment(
                file_path="a.py",
                line_number=1,
                message="Error issue",
                severity="error",
                rule_id="rule.A",
            ),
            IssueComment(
                file_path="b.py",
                line_number=2,
                message="Warning issue",
                severity="warning",
                rule_id="rule.B",
            ),
            IssueComment(
                file_path="c.py",
                line_number=3,
                message="Info issue",
                severity="info",
                rule_id="rule.C",
            ),
        ]

        posted_bodies = []
        mock_response = _make_urlopen_mock({"id": 1, "html_url": "https://example.com"})

        def capture(req, timeout=None):
            body_data = json.loads(req.data.decode("utf-8"))
            posted_bodies.append(body_data.get("body", ""))
            return mock_response

        with patch(
            "Asgard.Reporting.PRDecoration.services.github_decorator.urllib_request.urlopen",
            side_effect=capture,
        ):
            decorator.decorate(config, issues=issues, gate_result=None, ratings=None)

        assert len(posted_bodies) == 1
        summary = posted_bodies[0]
        assert "3 total" in summary
        assert "Errors: 1" in summary
        assert "Warnings: 1" in summary
        assert "Info: 1" in summary

    def test_gitlab_summary_lists_issue_counts(self):
        """GitLab summary includes total issue count, errors, warnings, and info."""
        config = _make_gitlab_config(post_summary=True, post_inline=False)
        decorator = GitLabDecorator()

        issues = [
            IssueComment(
                file_path="a.py",
                line_number=1,
                message="Error issue",
                severity="error",
                rule_id="rule.A",
            ),
            IssueComment(
                file_path="b.py",
                line_number=2,
                message="Warning issue",
                severity="warning",
                rule_id="rule.B",
            ),
        ]

        posted_bodies = []
        mock_response = _make_urlopen_mock({"id": 1, "web_url": "https://example.com"})

        def capture(req, timeout=None):
            body_data = json.loads(req.data.decode("utf-8"))
            posted_bodies.append(body_data.get("body", ""))
            return mock_response

        with patch(
            "Asgard.Reporting.PRDecoration.services.gitlab_decorator.urllib_request.urlopen",
            side_effect=capture,
        ):
            decorator.decorate(config, issues=issues, gate_result=None, ratings=None)

        assert len(posted_bodies) == 1
        summary = posted_bodies[0]
        assert "2 total" in summary
        assert "Errors: 1" in summary
        assert "Warnings: 1" in summary
