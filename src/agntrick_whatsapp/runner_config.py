"""Configuration loading for the WhatsApp CLI runner.

Loads settings from (in priority order):
1. CLI arguments (highest priority)
2. Environment variables with ``AGNTRICK_WA_`` prefix
3. ``.agntrick.yaml`` ``whatsapp:`` section (CWD then home directory)
4. ``AGNTRICK_WA_CONFIG`` env-var pointing to a dedicated YAML file
5. Built-in defaults (lowest priority)
"""

import logging
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

from agntrick_whatsapp.constants import DATA_DIR

logger = logging.getLogger(__name__)

_ENV_PREFIX = "AGNTRICK_WA_"

_DEFAULT_STORAGE_PATH = DATA_DIR / "session"
_DEFAULT_DB_PATH = DATA_DIR / "whatsapp.db"


class WhatsAppRunnerSettings(BaseModel):
    """Unified settings for the WhatsApp runner.

    All fields have sensible defaults so users only need to configure what
    they want to change.  The most common bridge-mode setup only requires
    ``allowed_contact``.
    """

    # -- mode --
    mode: str = Field(
        default="bridge",
        description="Channel mode: 'bridge' (QR code / neonize) or 'api' (Business API).",
    )

    # -- bridge mode --
    storage_path: Path = Field(
        default=_DEFAULT_STORAGE_PATH,
        description="Directory where neonize stores session data, media cache, and dedup DB.",
    )
    allowed_contact: str = Field(
        default="",
        description="Phone number to accept messages from (e.g. '+34666666666'). Empty = accept all.",
    )
    log_filtered_messages: bool = Field(default=False)
    poll_interval: float = Field(default=1.0)
    typing_indicators: bool = Field(default=True)
    min_typing_duration: float = Field(default=2.0)
    dedup_window: float = Field(default=10.0)

    # -- business API mode --
    access_token: str | None = Field(default=None, description="WhatsApp Business API access token.")
    phone_number_id: str | None = Field(default=None, description="WhatsApp Business phone number ID.")

    # -- agent --
    model_name: str | None = Field(default=None, description="LLM model name (provider auto-detected by agntrick).")
    temperature: float = Field(default=0.7, description="LLM temperature.")
    mcp_servers: list[str] | None = Field(default=None, description="MCP server names to enable.")
    system_prompt: str | None = Field(default=None, description="Override the default system prompt.")

    # -- storage --
    db_path: Path = Field(
        default=_DEFAULT_DB_PATH,
        description="Path to the SQLite database for notes and tasks.",
    )

    # -- logging / debug --
    log_level: str = Field(default="INFO", description="Logging level.")
    debug: bool = Field(default=False, description="Enable debug mode (sets log_level to DEBUG).")

    @model_validator(mode="after")
    def _apply_debug_log_level(self) -> "WhatsAppRunnerSettings":
        if self.debug:
            self.log_level = "DEBUG"
        return self

    @model_validator(mode="after")
    def _validate_api_mode(self) -> "WhatsAppRunnerSettings":
        if self.mode == "api" and (not self.access_token or not self.phone_number_id):
            raise ValueError("Business API mode requires 'access_token' and 'phone_number_id'.")
        return self


# -- YAML loading helpers ------------------------------------------------


def _find_yaml_config() -> tuple[dict[str, Any], str | None]:
    """Search for a ``whatsapp:`` config section and return it.

    Returns:
        A tuple of (config_dict, source_path_or_description).
    """
    # 1. Dedicated config file via env var
    env_cfg = os.getenv("AGNTRICK_WA_CONFIG")
    if env_cfg:
        path = Path(env_cfg).expanduser()
        if path.is_file():
            data = _load_yaml(path)
            if data:
                return data, str(path)

    # 2. .agntrick.yaml in CWD
    local = Path.cwd() / ".agntrick.yaml"
    if local.is_file():
        section = _load_yaml_section(local, "whatsapp")
        if section:
            return section, str(local)

    # 3. .agntrick.yaml in home
    home = Path.home() / ".agntrick.yaml"
    if home.is_file():
        section = _load_yaml_section(home, "whatsapp")
        if section:
            return section, str(home)

    return {}, None


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file and return its top-level dict."""
    try:
        with path.open() as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("Failed to load YAML from %s: %s", path, exc)
        return {}


def _load_yaml_section(path: Path, section: str) -> dict[str, Any] | None:
    data = _load_yaml(path)
    val = data.get(section)
    if isinstance(val, dict):
        return val
    return None


# -- Environment variable helpers ----------------------------------------


def _env_overrides() -> dict[str, Any]:
    """Collect environment variables with the ``AGNTRICK_WA_`` prefix.

    Returns:
        A dict of field_name -> value (strings) for every matching env var.
    """
    overrides: dict[str, Any] = {}
    for key, value in os.environ.items():
        if not key.startswith(_ENV_PREFIX):
            continue
        field_name = key[len(_ENV_PREFIX) :].lower()
        if field_name == "mcp_servers":
            overrides[field_name] = [s.strip() for s in value.split(",") if s.strip()]
        else:
            overrides[field_name] = value
    return overrides


# -- Public API ----------------------------------------------------------


def load_settings(**cli_overrides: Any) -> WhatsAppRunnerSettings:
    """Build ``WhatsAppRunnerSettings`` by merging all config sources.

    Priority (highest wins): CLI args > env vars > YAML file > defaults.

    Args:
        **cli_overrides: Keyword arguments from the CLI (only non-None
            values are merged).

    Returns:
        A fully-resolved ``WhatsAppRunnerSettings`` instance.
    """
    yaml_cfg, source = _find_yaml_config()
    if source:
        logger.info("Loaded WhatsApp config from %s", source)

    env_cfg = _env_overrides()
    if env_cfg:
        logger.debug("Environment overrides: %s", list(env_cfg.keys()))

    # Remove None values from CLI overrides so they don't clobber real values
    cli_cfg = {k: v for k, v in cli_overrides.items() if v is not None}

    merged: dict[str, Any] = {}
    merged.update(yaml_cfg)
    merged.update(env_cfg)
    merged.update(cli_cfg)

    return WhatsAppRunnerSettings(**merged)
