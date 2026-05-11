"""Tests for the GitHubClient installation-token refresh logic."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock


def _fake_auth(token: str, ttl_seconds: int):
    """Construct a fake InstallationAuthorization-like object."""
    auth = MagicMock()
    auth.token = token
    auth.expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    return auth


def _build_client_with_fake_integration(integration):
    """Build a GitHubClient and inject a fake _get_integration."""
    from src.github.client import GitHubClient

    client = GitHubClient()
    client._get_integration = lambda: integration
    return client


class TestTokenRefresh:
    def test_first_call_fetches_token(self):
        integration = MagicMock()
        integration.get_access_token.return_value = _fake_auth("ghs_first", 3600)

        client = _build_client_with_fake_integration(integration)
        token = client.get_installation_token(installation_id=42)

        assert token == "ghs_first"
        assert integration.get_access_token.call_count == 1

    def test_cached_token_reused_within_ttl(self):
        integration = MagicMock()
        integration.get_access_token.return_value = _fake_auth("ghs_cached", 3600)

        client = _build_client_with_fake_integration(integration)
        client.get_installation_token(42)
        client.get_installation_token(42)
        client.get_installation_token(42)

        # Three reads, one network call.
        assert integration.get_access_token.call_count == 1

    def test_token_refreshed_when_ttl_under_threshold(self):
        integration = MagicMock()
        # First token expires in 30 seconds — below the 60 second refresh threshold.
        integration.get_access_token.side_effect = [
            _fake_auth("ghs_old", 30),
            _fake_auth("ghs_fresh", 3600),
        ]

        client = _build_client_with_fake_integration(integration)
        first = client.get_installation_token(42)
        # Second call should detect the low TTL and refresh.
        second = client.get_installation_token(42)

        assert first == "ghs_old"
        assert second == "ghs_fresh"
        assert integration.get_access_token.call_count == 2

    def test_separate_installations_have_separate_caches(self):
        integration = MagicMock()
        integration.get_access_token.side_effect = [
            _fake_auth("ghs_inst1", 3600),
            _fake_auth("ghs_inst2", 3600),
        ]

        client = _build_client_with_fake_integration(integration)
        token1 = client.get_installation_token(1)
        token2 = client.get_installation_token(2)
        token1_again = client.get_installation_token(1)
        token2_again = client.get_installation_token(2)

        assert token1 == token1_again == "ghs_inst1"
        assert token2 == token2_again == "ghs_inst2"
        # Two refreshes total — one per installation.
        assert integration.get_access_token.call_count == 2

    def test_naive_expires_at_treated_as_utc(self):
        """PyGithub sometimes returns a tz-naive datetime; client should accept it."""
        integration = MagicMock()
        naive_auth = MagicMock()
        naive_auth.token = "ghs_naive"
        naive_auth.expires_at = datetime.utcnow() + timedelta(hours=1)  # naive
        integration.get_access_token.return_value = naive_auth

        client = _build_client_with_fake_integration(integration)
        token = client.get_installation_token(99)

        assert token == "ghs_naive"
