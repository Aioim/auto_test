"""
Unit tests for get_role_credentials() in src/core/cache_utils.py

Tests cover:
- Plaintext env vars returned as-is
- ENC[...] encrypted values trigger decryption via decrypt_env_key()
- Fallback to single-account variables
- Missing env vars raise ValueError
- Edge cases
"""
import os
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True, scope="module")
def _ensure_module_loaded():
    """Pre-load core.cache_utils so @patch('core.cache_utils.xxx') resolves."""
    import core.cache_utils  # noqa: F401
    yield


@pytest.fixture(autouse=True)
def _clear_env_vars():
    """Remove test env vars between tests."""
    for prefix in ("BETA_", "PROD_", "TEST_"):
        for k in list(os.environ):
            if k.startswith(prefix):
                os.environ.pop(k, None)
    yield
    for prefix in ("BETA_", "PROD_", "TEST_"):
        for k in list(os.environ):
            if k.startswith(prefix):
                os.environ.pop(k, None)


class TestGetRoleCredentials:

    @patch("core.cache_utils.decrypt_env_key")
    @patch("core.cache_utils.SecureEnvLoader")
    def test_plaintext_password_returned_as_is(self, mock_loader, mock_decrypt, monkeypatch):
        from core.cache_utils import get_role_credentials

        mock_loader.is_encrypted_value.return_value = False
        monkeypatch.setenv("BETA_EMPLOYEE_USER", "alice")
        monkeypatch.setenv("BETA_EMPLOYEE_PASS", "plain-password")

        result = get_role_credentials("employee", env="beta")

        assert result == {"username": "alice", "password": "plain-password"}
        mock_decrypt.assert_not_called()

    @patch("core.cache_utils.decrypt_env_key")
    @patch("core.cache_utils.SecureEnvLoader")
    def test_encrypted_password_triggers_decryption(self, mock_loader, mock_decrypt, monkeypatch):
        from core.cache_utils import get_role_credentials

        mock_loader.is_encrypted_value.return_value = True
        mock_decrypt.return_value = "decrypted-secret"
        monkeypatch.setenv("BETA_ADMIN_USER", "admin1")
        monkeypatch.setenv("BETA_ADMIN_PASS", "ENC[gAAAAAB...]")

        result = get_role_credentials("admin", env="beta")

        assert result == {"username": "admin1", "password": "decrypted-secret"}
        mock_decrypt.assert_called_once_with("BETA_ADMIN_PASS")

    @patch("core.cache_utils.decrypt_env_key")
    @patch("core.cache_utils.SecureEnvLoader")
    def test_encrypted_password_with_plaintext_username(self, mock_loader, mock_decrypt, monkeypatch):
        from core.cache_utils import get_role_credentials

        mock_loader.is_encrypted_value.return_value = True
        mock_decrypt.return_value = "decrypted-secret"
        monkeypatch.setenv("BETA_MANAGER_USER", "bob")
        monkeypatch.setenv("BETA_MANAGER_PASS", "ENC[xyz...]")

        result = get_role_credentials("manager", env="beta")
        assert result["username"] == "bob"
        assert result["password"] == "decrypted-secret"

    @patch("core.cache_utils.decrypt_env_key")
    @patch("core.cache_utils.SecureEnvLoader")
    def test_fallback_to_single_account_plain(self, mock_loader, mock_decrypt, monkeypatch):
        from core.cache_utils import get_role_credentials

        mock_loader.is_encrypted_value.return_value = False
        monkeypatch.setenv("BETA_USERNAME", "fallback_user")
        monkeypatch.setenv("BETA_PASSWORD", "fallback_pass")

        result = get_role_credentials("nonexistent_role", env="beta")

        assert result == {"username": "fallback_user", "password": "fallback_pass"}
        mock_decrypt.assert_not_called()

    @patch("core.cache_utils.decrypt_env_key")
    @patch("core.cache_utils.SecureEnvLoader")
    def test_fallback_to_single_account_encrypted(self, mock_loader, mock_decrypt, monkeypatch):
        from core.cache_utils import get_role_credentials

        mock_loader.is_encrypted_value.return_value = True
        mock_decrypt.return_value = "decrypted-fallback"
        monkeypatch.setenv("BETA_USERNAME", "fallback_user")
        monkeypatch.setenv("BETA_PASSWORD", "ENC[fallback_enc...]")

        result = get_role_credentials("unknown_role", env="beta")

        assert result == {"username": "fallback_user", "password": "decrypted-fallback"}
        mock_decrypt.assert_called_once_with("BETA_PASSWORD")

    @patch("core.cache_utils.decrypt_env_key")
    @patch("core.cache_utils.SecureEnvLoader")
    def test_missing_role_vars_raise_value_error(self, mock_loader, mock_decrypt, monkeypatch):
        from core.cache_utils import get_role_credentials

        with pytest.raises(ValueError, match="未找到角色 'ghost' 的环境变量配置"):
            get_role_credentials("ghost", env="beta")

    @patch("core.cache_utils.decrypt_env_key")
    @patch("core.cache_utils.SecureEnvLoader")
    def test_partial_role_vars_raise_value_error(self, mock_loader, mock_decrypt, monkeypatch):
        from core.cache_utils import get_role_credentials

        mock_loader.is_encrypted_value.return_value = False
        monkeypatch.setenv("BETA_PARTIAL_USER", "someuser")

        with pytest.raises(ValueError, match="未找到角色 'partial' 的环境变量配置"):
            get_role_credentials("partial", env="beta")

    @patch("core.cache_utils.decrypt_env_key")
    @patch("core.cache_utils.SecureEnvLoader")
    @patch("core.cache_utils.settings")
    def test_default_env_from_settings(self, mock_settings, mock_loader, mock_decrypt, monkeypatch):
        from core.cache_utils import get_role_credentials

        mock_settings.env = "prod"
        mock_loader.is_encrypted_value.return_value = False
        monkeypatch.setenv("PROD_DEFAULT_USER", "default_user")
        monkeypatch.setenv("PROD_DEFAULT_PASS", "default_pass")

        result = get_role_credentials("default")
        assert result == {"username": "default_user", "password": "default_pass"}

    @patch("core.cache_utils.decrypt_env_key")
    @patch("core.cache_utils.SecureEnvLoader")
    def test_is_encrypted_not_called_for_missing_vars(self, mock_loader, mock_decrypt, monkeypatch):
        from core.cache_utils import get_role_credentials

        with pytest.raises(ValueError):
            get_role_credentials("ghost", env="beta")

        mock_loader.is_encrypted_value.assert_not_called()
