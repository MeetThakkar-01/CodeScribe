"""Shared test fixtures and environment setup."""

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _stub_env(monkeypatch, tmp_path_factory):
    """Provide dummy env vars + a fake private key so Settings() can construct."""
    tmpdir = tmp_path_factory.mktemp("codescribe_test")
    fake_key = tmpdir / "fake.pem"
    fake_key.write_text("-----BEGIN PRIVATE KEY-----\nFAKE\n-----END PRIVATE KEY-----\n")

    monkeypatch.setenv("GITHUB_APP_ID", "12345")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY_PATH", str(fake_key))
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("DOC_CACHE_DIR", str(tmpdir / "cache"))

    # Reset the cached singleton so tests pick up the patched env.
    import src.config as config

    config.settings = None
    yield
    config.settings = None
