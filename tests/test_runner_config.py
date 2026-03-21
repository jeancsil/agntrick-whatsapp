"""Tests for runner_config module."""

import os
from pathlib import Path

import pytest
import yaml

from agntrick_whatsapp.runner_config import (
    WhatsAppRunnerSettings,
    _env_overrides,
    _find_yaml_config,
    load_settings,
)


class TestWhatsAppRunnerSettings:
    """Test the Pydantic settings model."""

    def test_defaults(self):
        """All fields have defaults so an empty instantiation works (bridge mode)."""
        s = WhatsAppRunnerSettings()
        assert s.mode == "bridge"
        assert s.temperature == 0.7
        assert s.log_level == "INFO"
        assert s.debug is False
        assert s.allowed_contact == ""
        assert s.typing_indicators is True
        assert s.model_name is None
        assert s.access_token is None

    def test_debug_sets_log_level(self):
        """When debug=True, log_level should be forced to DEBUG."""
        s = WhatsAppRunnerSettings(debug=True)
        assert s.log_level == "DEBUG"

    def test_api_mode_requires_credentials(self):
        """API mode without credentials should raise ValueError."""
        with pytest.raises(ValueError, match="access_token"):
            WhatsAppRunnerSettings(mode="api")

    def test_api_mode_with_credentials(self):
        """API mode with credentials should succeed."""
        s = WhatsAppRunnerSettings(
            mode="api",
            access_token="EAAtest123",
            phone_number_id="9876543210",
        )
        assert s.mode == "api"
        assert s.access_token == "EAAtest123"

    def test_custom_storage_path(self, tmp_path: Path):
        s = WhatsAppRunnerSettings(storage_path=tmp_path / "mysession")
        assert s.storage_path == tmp_path / "mysession"

    def test_custom_db_path(self, tmp_path: Path):
        s = WhatsAppRunnerSettings(db_path=tmp_path / "custom.db")
        assert s.db_path == tmp_path / "custom.db"

    def test_mcp_servers_list(self):
        s = WhatsAppRunnerSettings(mcp_servers=["fetch", "notion"])
        assert s.mcp_servers == ["fetch", "notion"]


class TestEnvOverrides:
    """Test environment variable collection."""

    def test_collects_prefixed_vars(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("AGNTRICK_WA_MODE", "api")
        monkeypatch.setenv("AGNTRICK_WA_ALLOWED_CONTACT", "+34666666666")
        monkeypatch.setenv("UNRELATED_VAR", "ignored")

        overrides = _env_overrides()
        assert overrides["mode"] == "api"
        assert overrides["allowed_contact"] == "+34666666666"
        assert "unrelated_var" not in overrides

    def test_mcp_servers_split(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("AGNTRICK_WA_MCP_SERVERS", "fetch, notion , slack")
        overrides = _env_overrides()
        assert overrides["mcp_servers"] == ["fetch", "notion", "slack"]

    def test_empty_env(self, monkeypatch: pytest.MonkeyPatch):
        # Remove any existing AGNTRICK_WA_ vars
        for key in list(os.environ):
            if key.startswith("AGNTRICK_WA_"):
                monkeypatch.delenv(key, raising=False)
        assert _env_overrides() == {}


class TestFindYamlConfig:
    """Test YAML configuration discovery."""

    def test_dedicated_config_via_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        cfg_file = tmp_path / "wa.yaml"
        cfg_file.write_text(yaml.dump({"mode": "bridge", "allowed_contact": "+1111"}))
        monkeypatch.setenv("AGNTRICK_WA_CONFIG", str(cfg_file))
        monkeypatch.chdir(tmp_path)

        data, source = _find_yaml_config()
        assert data["mode"] == "bridge"
        assert source == str(cfg_file)

    def test_cwd_agntrick_yaml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        cfg_file = tmp_path / ".agntrick.yaml"
        cfg_file.write_text(yaml.dump({"whatsapp": {"allowed_contact": "+2222"}}))
        monkeypatch.chdir(tmp_path)
        # Clear env var if set
        monkeypatch.delenv("AGNTRICK_WA_CONFIG", raising=False)

        data, source = _find_yaml_config()
        assert data["allowed_contact"] == "+2222"
        assert source == str(cfg_file)

    def test_home_agntrick_yaml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("AGNTRICK_WA_CONFIG", raising=False)
        # CWD without config
        monkeypatch.chdir(tmp_path)

        home_dir = tmp_path / "fakehome"
        home_dir.mkdir()
        cfg_file = home_dir / ".agntrick.yaml"
        cfg_file.write_text(yaml.dump({"whatsapp": {"allowed_contact": "+3333"}}))
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home_dir))

        data, source = _find_yaml_config()
        assert data["allowed_contact"] == "+3333"

    def test_no_config_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("AGNTRICK_WA_CONFIG", raising=False)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "nonexistent"))

        data, source = _find_yaml_config()
        assert data == {}
        assert source is None


class TestLoadSettings:
    """Test the merged settings loader."""

    def test_defaults_only(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("AGNTRICK_WA_CONFIG", raising=False)
        monkeypatch.chdir(tmp_path)
        # Clear any existing AGNTRICK_WA_ env vars
        for key in list(os.environ):
            if key.startswith("AGNTRICK_WA_"):
                monkeypatch.delenv(key, raising=False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "nonexistent"))

        s = load_settings()
        assert s.mode == "bridge"

    def test_yaml_overrides_defaults(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        cfg = tmp_path / ".agntrick.yaml"
        cfg.write_text(yaml.dump({"whatsapp": {"temperature": 0.3, "allowed_contact": "+9999"}}))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("AGNTRICK_WA_CONFIG", raising=False)
        for key in list(os.environ):
            if key.startswith("AGNTRICK_WA_"):
                monkeypatch.delenv(key, raising=False)

        s = load_settings()
        assert s.temperature == 0.3
        assert s.allowed_contact == "+9999"

    def test_env_overrides_yaml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        cfg = tmp_path / ".agntrick.yaml"
        cfg.write_text(yaml.dump({"whatsapp": {"temperature": 0.3}}))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("AGNTRICK_WA_CONFIG", raising=False)
        monkeypatch.setenv("AGNTRICK_WA_TEMPERATURE", "0.9")
        # Clear other AGNTRICK_WA_ vars
        for key in list(os.environ):
            if key.startswith("AGNTRICK_WA_") and key != "AGNTRICK_WA_TEMPERATURE":
                monkeypatch.delenv(key, raising=False)

        s = load_settings()
        assert s.temperature == 0.9

    def test_cli_overrides_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("AGNTRICK_WA_CONFIG", raising=False)
        monkeypatch.setenv("AGNTRICK_WA_TEMPERATURE", "0.9")
        for key in list(os.environ):
            if key.startswith("AGNTRICK_WA_") and key != "AGNTRICK_WA_TEMPERATURE":
                monkeypatch.delenv(key, raising=False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "nonexistent"))

        s = load_settings(temperature=0.1)
        assert s.temperature == 0.1

    def test_none_cli_values_ignored(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        cfg = tmp_path / ".agntrick.yaml"
        cfg.write_text(yaml.dump({"whatsapp": {"allowed_contact": "+5555"}}))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("AGNTRICK_WA_CONFIG", raising=False)
        for key in list(os.environ):
            if key.startswith("AGNTRICK_WA_"):
                monkeypatch.delenv(key, raising=False)

        s = load_settings(allowed_contact=None, model_name=None)
        assert s.allowed_contact == "+5555"
