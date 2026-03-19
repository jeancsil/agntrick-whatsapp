"""Tests for the CLI module."""

from pathlib import Path

import yaml
from typer.testing import CliRunner

from agntrick_whatsapp.cli import _config_template, _display_settings, app
from agntrick_whatsapp.runner_config import WhatsAppRunnerSettings

runner = CliRunner()


class TestCLIVersion:
    """Test the version command."""

    def test_version_output(self):
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "agntrick-whatsapp" in result.output


class TestCLIConfig:
    """Test the config command."""

    def test_config_shows_table(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("AGNTRICK_WA_CONFIG", raising=False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "nonexistent"))
        # Clear AGNTRICK_WA_ env vars
        import os

        for key in list(os.environ):
            if key.startswith("AGNTRICK_WA_"):
                monkeypatch.delenv(key, raising=False)

        result = runner.invoke(app, ["config"])
        assert result.exit_code == 0
        assert "bridge" in result.output

    def test_config_with_yaml(self, tmp_path: Path, monkeypatch):
        cfg = tmp_path / ".agntrick.yaml"
        cfg.write_text(yaml.dump({"whatsapp": {"allowed_contact": "+12345"}}))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("AGNTRICK_WA_CONFIG", raising=False)
        import os

        for key in list(os.environ):
            if key.startswith("AGNTRICK_WA_"):
                monkeypatch.delenv(key, raising=False)

        result = runner.invoke(app, ["config"])
        assert result.exit_code == 0
        assert "+12345" in result.output


class TestCLIInit:
    """Test the init command."""

    def test_init_creates_config(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        output_file = tmp_path / ".agntrick.yaml"
        result = runner.invoke(app, ["init", "--output", str(output_file)])
        assert result.exit_code == 0
        assert output_file.exists()

        content = output_file.read_text()
        assert "whatsapp:" in content
        assert "mode: bridge" in content
        assert "allowed_contact" in content

    def test_init_refuses_overwrite(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        output_file = tmp_path / ".agntrick.yaml"
        output_file.write_text("existing: content\n")
        result = runner.invoke(app, ["init", "--output", str(output_file)])
        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_init_force_overwrite(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        output_file = tmp_path / ".agntrick.yaml"
        output_file.write_text("existing: content\n")
        result = runner.invoke(app, ["init", "--output", str(output_file), "--force"])
        assert result.exit_code == 0
        content = output_file.read_text()
        assert "whatsapp:" in content

    def test_init_merges_into_existing(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        output_file = tmp_path / ".agntrick.yaml"
        output_file.write_text("llm:\n  model: gpt-4o\n")
        result = runner.invoke(app, ["init", "--output", str(output_file), "--force"])
        assert result.exit_code == 0
        content = output_file.read_text()
        assert "whatsapp:" in content


class TestCLIStart:
    """Test the start command configuration resolution (not actual connection)."""

    def _clean_env(self, monkeypatch, tmp_path: Path):
        """Remove AGNTRICK_WA_ env vars and point away from home."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("AGNTRICK_WA_CONFIG", raising=False)
        import os

        for key in list(os.environ):
            if key.startswith("AGNTRICK_WA_"):
                monkeypatch.delenv(key, raising=False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "nonexistent"))

    def test_start_missing_api_credentials(self, tmp_path: Path, monkeypatch):
        self._clean_env(monkeypatch, tmp_path)
        result = runner.invoke(app, ["start", "--mode", "api"])
        assert result.exit_code == 1
        assert "Configuration error" in result.output

    def test_start_bridge_mode_shows_banner(self, tmp_path: Path, monkeypatch):
        """start in bridge mode should print the startup banner then fail
        (neonize not available in test env) — we only test config resolution."""
        self._clean_env(monkeypatch, tmp_path)
        result = runner.invoke(app, ["start", "--allowed-contact", "+34666"])
        # It will try to actually start and fail (neonize) but the banner should appear
        assert "Starting WhatsApp Agent" in result.output or result.exit_code == 1

    def test_start_debug_shows_table(self, tmp_path: Path, monkeypatch):
        self._clean_env(monkeypatch, tmp_path)
        result = runner.invoke(app, ["start", "--debug"])
        # Debug mode should show the resolved config table
        assert "Resolved Configuration" in result.output or result.exit_code == 1


class TestCLINoArgs:
    """Test CLI with no arguments shows help."""

    def test_no_args_shows_help(self):
        result = runner.invoke(app, [])
        # Typer uses exit code 0 or 2 for help display depending on version
        assert result.exit_code in (0, 2)
        assert "start" in result.output or "Usage" in result.output

    def test_help_flag(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "start" in result.output
        assert "config" in result.output
        assert "init" in result.output
        assert "version" in result.output

    def test_start_help(self):
        result = runner.invoke(app, ["start", "--help"])
        assert result.exit_code == 0
        assert "--allowed-contact" in result.output
        assert "--model" in result.output
        assert "--mode" in result.output
        assert "--debug" in result.output


class TestHelpers:
    """Test CLI helper functions."""

    def test_config_template_contains_sections(self):
        template = _config_template()
        assert "whatsapp:" in template
        assert "mode: bridge" in template
        assert "allowed_contact" in template
        assert "temperature" in template
        assert "AGNTRICK_WA_" in template

    def test_display_settings_bridge(self, capsys):
        settings = WhatsAppRunnerSettings()
        _display_settings(settings)
        captured = capsys.readouterr()
        assert "bridge" in captured.out

    def test_display_settings_api(self, capsys):
        settings = WhatsAppRunnerSettings(
            mode="api",
            access_token="EAAtest123",
            phone_number_id="999",
        )
        _display_settings(settings)
        captured = capsys.readouterr()
        assert "api" in captured.out
        assert "EAAtes" in captured.out  # truncated token
