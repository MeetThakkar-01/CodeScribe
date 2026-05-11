"""Tests for the JiraClient retry-on-transient-error path."""

from unittest.mock import MagicMock, patch

import httpx
import pytest


def _set_jira_env(monkeypatch):
    """Provide minimum env so JiraClient construction succeeds."""
    monkeypatch.setenv("JIRA_BASE_URL", "https://example.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "demo@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token")
    import src.config

    src.config.settings = None  # force reload


def _mock_response(status_code: int, body=None, headers=None):
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.headers = headers or {}
    response.json.return_value = body or {}
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"{status_code}", request=MagicMock(), response=response
        )
    else:
        response.raise_for_status = MagicMock()
    return response


class TestRetryOnTransientErrors:
    def test_succeeds_on_first_attempt_no_retries(self, monkeypatch):
        _set_jira_env(monkeypatch)
        from src.agents.ticketing.client import JiraClient

        success = _mock_response(200, body={"key": "PROJ-1"})
        with patch("src.agents.ticketing.client.httpx.post") as post, patch(
            "src.agents.ticketing.client.time.sleep"
        ) as sleep:
            post.return_value = success
            result = JiraClient().create_issue({"fields": {}})

        assert result == "PROJ-1"
        assert post.call_count == 1
        sleep.assert_not_called()

    def test_retries_on_429_then_succeeds(self, monkeypatch):
        _set_jira_env(monkeypatch)
        from src.agents.ticketing.client import JiraClient

        responses = [
            _mock_response(429),
            _mock_response(200, body={"key": "PROJ-2"}),
        ]
        with patch("src.agents.ticketing.client.httpx.post") as post, patch(
            "src.agents.ticketing.client.time.sleep"
        ) as sleep:
            post.side_effect = responses
            result = JiraClient().create_issue({"fields": {}})

        assert result == "PROJ-2"
        assert post.call_count == 2
        assert sleep.call_count == 1  # one delay between the two attempts

    def test_retries_on_5xx_then_succeeds(self, monkeypatch):
        _set_jira_env(monkeypatch)
        from src.agents.ticketing.client import JiraClient

        responses = [
            _mock_response(503),
            _mock_response(502),
            _mock_response(200, body={"key": "PROJ-3"}),
        ]
        with patch("src.agents.ticketing.client.httpx.post") as post, patch(
            "src.agents.ticketing.client.time.sleep"
        ) as sleep:
            post.side_effect = responses
            result = JiraClient().create_issue({"fields": {}})

        assert result == "PROJ-3"
        assert post.call_count == 3
        assert sleep.call_count == 2

    def test_honors_retry_after_header_on_429(self, monkeypatch):
        _set_jira_env(monkeypatch)
        from src.agents.ticketing.client import JiraClient

        responses = [
            _mock_response(429, headers={"Retry-After": "5"}),
            _mock_response(200, body={"key": "PROJ-4"}),
        ]
        with patch("src.agents.ticketing.client.httpx.post") as post, patch(
            "src.agents.ticketing.client.time.sleep"
        ) as sleep:
            post.side_effect = responses
            JiraClient().create_issue({"fields": {}})

        # Retry-After=5 should drive the sleep duration, not the default backoff
        sleep.assert_called_once_with(5.0)

    def test_exhausts_retries_and_raises(self, monkeypatch):
        _set_jira_env(monkeypatch)
        from src.agents.ticketing.client import JiraClient

        responses = [
            _mock_response(503),
            _mock_response(503),
            _mock_response(503),
        ]
        with patch("src.agents.ticketing.client.httpx.post") as post, patch(
            "src.agents.ticketing.client.time.sleep"
        ):
            post.side_effect = responses
            with pytest.raises(httpx.HTTPStatusError):
                JiraClient().create_issue({"fields": {}})
            assert post.call_count == 3

    def test_network_error_retried(self, monkeypatch):
        _set_jira_env(monkeypatch)
        from src.agents.ticketing.client import JiraClient

        with patch("src.agents.ticketing.client.httpx.post") as post, patch(
            "src.agents.ticketing.client.time.sleep"
        ):
            post.side_effect = [
                httpx.ConnectError("dns failure"),
                _mock_response(200, body={"key": "PROJ-5"}),
            ]
            result = JiraClient().create_issue({"fields": {}})

        assert result == "PROJ-5"
        assert post.call_count == 2

    def test_unconfigured_raises(self, monkeypatch):
        # Empty base_url means JiraClient should refuse to attempt
        monkeypatch.setenv("JIRA_BASE_URL", "")
        monkeypatch.setenv("JIRA_EMAIL", "")
        monkeypatch.setenv("JIRA_API_TOKEN", "")
        import src.config

        src.config.settings = None
        from src.agents.ticketing.client import JiraClient

        with pytest.raises(RuntimeError):
            JiraClient().create_issue({"fields": {}})
