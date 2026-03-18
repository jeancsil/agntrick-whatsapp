"""Test cases for Pydantic configuration models."""

import json

import pytest
from pydantic import ValidationError

from agntrick_whatsapp.config import (
    AgentConfig,
    StorageConfig,
    WebhookConfig,
    WhatsAppConfig,
    WhatsAppRouterConfig,
)


class TestWhatsAppConfig:
    """Test cases for WhatsAppConfig."""

    def test_valid_config(self):
        """Test creating a valid WhatsAppConfig."""
        config = WhatsAppConfig(
            access_token="EAAvalidtoken12345",
            phone_number_id="1234567890",
            verify_token="my_verify_token",
        )
        assert config.access_token == "EAAvalidtoken12345"
        assert config.phone_number_id == "1234567890"
        assert config.verify_token == "my_verify_token"
        assert config.api_version == "18.0"
        assert config.message_timeout == 30
        assert config.retry_attempts == 3
        assert config.retry_delay == 5

    def test_invalid_access_token_missing_prefix(self):
        """Test validation fails for access token without EA prefix."""
        with pytest.raises(ValidationError, match='Access token must start with "EA"'):
            WhatsAppConfig(
                access_token="invalid_token",
                phone_number_id="1234567890",
                verify_token="token",
            )

    def test_invalid_access_token_empty(self):
        """Test validation fails for empty access token."""
        with pytest.raises(ValidationError, match='Access token must start with "EA"'):
            WhatsAppConfig(
                access_token="",
                phone_number_id="1234567890",
                verify_token="token",
            )

    def test_invalid_phone_number_id_non_numeric(self):
        """Test validation fails for non-numeric phone number ID."""
        with pytest.raises(ValidationError, match="Phone number ID must be numeric"):
            WhatsAppConfig(
                access_token="EAAvalidtoken12345",
                phone_number_id="not_a_number",
                verify_token="token",
            )

    def test_invalid_api_version(self):
        """Test validation fails for unsupported API version."""
        with pytest.raises(ValidationError, match="API version must be one of"):
            WhatsAppConfig(
                access_token="EAAvalidtoken12345",
                phone_number_id="1234567890",
                verify_token="token",
                api_version="15.0",
            )

    def test_valid_api_versions(self):
        """Test all allowed API versions."""
        for version in ["18.0", "17.0", "16.0"]:
            config = WhatsAppConfig(
                access_token="EAAvalidtoken12345",
                phone_number_id="1234567890",
                verify_token="token",
                api_version=version,
            )
            assert config.api_version == version

    def test_with_optional_fields(self):
        """Test config with optional fields."""
        config = WhatsAppConfig(
            access_token="EAAvalidtoken12345",
            phone_number_id="1234567890",
            verify_token="token",
            webhook_url="https://example.com/webhook",
            message_timeout=60,
            retry_attempts=5,
            retry_delay=10,
        )
        assert config.webhook_url == "https://example.com/webhook"
        assert config.message_timeout == 60
        assert config.retry_attempts == 5
        assert config.retry_delay == 10


class TestStorageConfig:
    """Test cases for StorageConfig."""

    def test_valid_sqlite_config(self):
        """Test creating a valid SQLite storage config."""
        config = StorageConfig(type="sqlite", path="/tmp/db.sqlite")
        assert config.type == "sqlite"
        assert config.path == "/tmp/db.sqlite"
        assert config.max_connections == 10
        assert config.timeout == 30

    def test_valid_postgres_config(self):
        """Test creating a valid PostgreSQL storage config."""
        config = StorageConfig(type="postgres", connection_string="postgresql://localhost/db")
        assert config.type == "postgres"
        assert config.connection_string == "postgresql://localhost/db"

    def test_valid_memory_config(self):
        """Test creating a valid memory storage config."""
        config = StorageConfig(type="memory")
        assert config.type == "memory"

    def test_invalid_storage_type(self):
        """Test validation fails for unsupported storage type."""
        with pytest.raises(ValidationError, match="Storage type must be one of"):
            StorageConfig(type="mongodb")

    def test_all_valid_storage_types(self):
        """Test all allowed storage types."""
        for storage_type in ["sqlite", "postgres", "mysql", "memory"]:
            config = StorageConfig(type=storage_type)
            assert config.type == storage_type

    def test_with_optional_fields(self):
        """Test config with optional fields."""
        config = StorageConfig(
            type="sqlite",
            path="/tmp/db.sqlite",
            max_connections=20,
            timeout=60,
        )
        assert config.max_connections == 20
        assert config.timeout == 60


class TestAgentConfig:
    """Test cases for AgentConfig."""

    def test_valid_agent_config(self):
        """Test creating a valid agent config."""
        config = AgentConfig(
            name="my_agent",
            description="A test agent",
        )
        assert config.name == "my_agent"
        assert config.description == "A test agent"
        assert config.enabled is True
        assert config.commands == []
        assert config.settings == {}

    def test_invalid_agent_name_with_special_chars(self):
        """Test validation fails for agent name with invalid characters."""
        with pytest.raises(ValidationError, match="Agent name must be alphanumeric or underscore"):
            AgentConfig(name="agent-name", description="test")

    def test_valid_agent_name_with_underscore(self):
        """Test agent name with underscore is valid."""
        config = AgentConfig(name="my_agent_v2", description="test")
        assert config.name == "my_agent_v2"

    def test_agent_with_commands(self):
        """Test agent config with commands."""
        config = AgentConfig(name="agent", description="test", commands=["/hello", "/help", "/status"])
        assert config.commands == ["/hello", "/help", "/status"]

    def test_agent_with_settings(self):
        """Test agent config with settings."""
        config = AgentConfig(name="agent", description="test", settings={"param1": "value1", "param2": 123})
        assert config.settings == {"param1": "value1", "param2": 123}

    def test_agent_disabled(self):
        """Test agent can be disabled."""
        config = AgentConfig(name="agent", description="test", enabled=False)
        assert config.enabled is False


class TestWhatsAppRouterConfig:
    """Test cases for WhatsAppRouterConfig."""

    def test_valid_router_config(self):
        """Test creating a valid router config."""
        whatsapp_config = WhatsAppConfig(
            access_token="EAAxxx",
            phone_number_id="123",
            verify_token="token",
        )
        storage_config = StorageConfig(type="memory")

        config = WhatsAppRouterConfig(whatsapp=whatsapp_config, storage=storage_config)

        assert config.whatsapp == whatsapp_config
        assert config.storage == storage_config
        assert config.message_history_limit == 1000
        assert config.max_conversation_length == 100
        assert config.debug_mode is False
        assert config.agents == []
        assert config.default_agent is None

    def test_invalid_default_agent_not_in_list(self):
        """Test validation fails when default_agent not in agents list."""
        whatsapp_config = WhatsAppConfig(
            access_token="EAAxxx",
            phone_number_id="123",
            verify_token="token",
        )
        storage_config = StorageConfig(type="memory")

        agent1 = AgentConfig(name="agent1", description="test")

        with pytest.raises(ValidationError, match="Default agent must be in the agents list"):
            WhatsAppRouterConfig(
                whatsapp=whatsapp_config,
                storage=storage_config,
                agents=[agent1],
                default_agent="agent2",
            )

    def test_valid_default_agent_in_list(self):
        """Test default_agent is valid when in agents list."""
        whatsapp_config = WhatsAppConfig(
            access_token="EAAxxx",
            phone_number_id="123",
            verify_token="token",
        )
        storage_config = StorageConfig(type="memory")

        agent1 = AgentConfig(name="agent1", description="test")
        agent2 = AgentConfig(name="agent2", description="test")

        config = WhatsAppRouterConfig(
            whatsapp=whatsapp_config,
            storage=storage_config,
            agents=[agent1, agent2],
            default_agent="agent1",
        )

        assert config.default_agent == "agent1"

    def test_invalid_message_history_limit_negative(self):
        """Test validation fails for negative message history limit."""
        whatsapp_config = WhatsAppConfig(
            access_token="EAAxxx",
            phone_number_id="123",
            verify_token="token",
        )
        storage_config = StorageConfig(type="memory")

        with pytest.raises(ValidationError, match="Message history limit must be between 0 and 10000"):
            WhatsAppRouterConfig(
                whatsapp=whatsapp_config,
                storage=storage_config,
                message_history_limit=-1,
            )

    def test_invalid_message_history_limit_too_large(self):
        """Test validation fails for message history limit over 10000."""
        whatsapp_config = WhatsAppConfig(
            access_token="EAAxxx",
            phone_number_id="123",
            verify_token="token",
        )
        storage_config = StorageConfig(type="memory")

        with pytest.raises(ValidationError, match="Message history limit must be between 0 and 10000"):
            WhatsAppRouterConfig(
                whatsapp=whatsapp_config,
                storage=storage_config,
                message_history_limit=10001,
            )

    def test_invalid_max_conversation_length_too_small(self):
        """Test validation fails for conversation length under 10."""
        whatsapp_config = WhatsAppConfig(
            access_token="EAAxxx",
            phone_number_id="123",
            verify_token="token",
        )
        storage_config = StorageConfig(type="memory")

        with pytest.raises(ValidationError, match="Conversation length must be between 10 and 1000"):
            WhatsAppRouterConfig(
                whatsapp=whatsapp_config,
                storage=storage_config,
                max_conversation_length=5,
            )

    def test_invalid_max_conversation_length_too_large(self):
        """Test validation fails for conversation length over 1000."""
        whatsapp_config = WhatsAppConfig(
            access_token="EAAxxx",
            phone_number_id="123",
            verify_token="token",
        )
        storage_config = StorageConfig(type="memory")

        with pytest.raises(ValidationError, match="Conversation length must be between 10 and 1000"):
            WhatsAppRouterConfig(
                whatsapp=whatsapp_config,
                storage=storage_config,
                max_conversation_length=1001,
            )

    def test_valid_boundary_values(self):
        """Test valid boundary values for numeric fields."""
        whatsapp_config = WhatsAppConfig(
            access_token="EAAxxx",
            phone_number_id="123",
            verify_token="token",
        )
        storage_config = StorageConfig(type="memory")

        config = WhatsAppRouterConfig(
            whatsapp=whatsapp_config,
            storage=storage_config,
            message_history_limit=0,
            max_conversation_length=10,
        )

        assert config.message_history_limit == 0
        assert config.max_conversation_length == 10

        config2 = WhatsAppRouterConfig(
            whatsapp=whatsapp_config,
            storage=storage_config,
            message_history_limit=10000,
            max_conversation_length=1000,
        )

        assert config2.message_history_limit == 10000
        assert config2.max_conversation_length == 1000

    def test_with_multiple_agents(self):
        """Test router config with multiple agents."""
        whatsapp_config = WhatsAppConfig(
            access_token="EAAxxx",
            phone_number_id="123",
            verify_token="token",
        )
        storage_config = StorageConfig(type="memory")

        agents = [
            AgentConfig(name="agent1", description="First agent"),
            AgentConfig(name="agent2", description="Second agent"),
            AgentConfig(name="agent3", description="Third agent"),
        ]

        config = WhatsAppRouterConfig(
            whatsapp=whatsapp_config,
            storage=storage_config,
            agents=agents,
        )

        assert len(config.agents) == 3
        assert config.agents[0].name == "agent1"
        assert config.agents[1].name == "agent2"
        assert config.agents[2].name == "agent3"

    def test_save_to_file(self, tmp_path):
        """Test saving config to file."""
        whatsapp_config = WhatsAppConfig(
            access_token="EAAxxx",
            phone_number_id="123",
            verify_token="token",
        )
        storage_config = StorageConfig(type="memory")

        config = WhatsAppRouterConfig(
            whatsapp=whatsapp_config,
            storage=storage_config,
            debug_mode=True,
        )

        file_path = tmp_path / "config.json"
        config.save_to_file(str(file_path))

        with open(file_path, "r") as f:
            data = json.load(f)

        assert data["whatsapp"]["access_token"] == "EAAxxx"
        assert data["storage"]["type"] == "memory"
        assert data["debug_mode"] is True

    def test_load_from_file(self, tmp_path):
        """Test loading config from file."""
        config_data = {
            "whatsapp": {
                "access_token": "EAAxxx",
                "phone_number_id": "123",
                "verify_token": "token",
            },
            "storage": {"type": "memory"},
        }

        file_path = tmp_path / "config.json"
        with open(file_path, "w") as f:
            json.dump(config_data, f)

        config = WhatsAppRouterConfig.load_from_file(str(file_path))

        assert config.whatsapp.access_token == "EAAxxx"
        assert config.storage.type == "memory"

    def test_model_dump(self):
        """Test model_dump method works correctly."""
        whatsapp_config = WhatsAppConfig(
            access_token="EAAxxx",
            phone_number_id="123",
            verify_token="token",
        )
        storage_config = StorageConfig(type="memory")

        config = WhatsAppRouterConfig(whatsapp=whatsapp_config, storage=storage_config)

        dumped = config.model_dump()
        assert "whatsapp" in dumped
        assert "storage" in dumped
        assert dumped["whatsapp"]["access_token"] == "EAAxxx"


class TestWebhookConfig:
    """Test cases for WebhookConfig."""

    def test_valid_webhook_config(self):
        """Test creating a valid webhook config."""
        config = WebhookConfig(
            verify_token="my_secret",
            webhook_url="https://example.com/webhook",
        )
        assert config.verify_token == "my_secret"
        assert config.webhook_url == "https://example.com/webhook"
        assert config.challenge_timeout == 10
        assert config.app_secret is None

    def test_invalid_webhook_url_missing_scheme(self):
        """Test validation fails for webhook URL without http/https."""
        with pytest.raises(ValidationError, match="Webhook URL must start with http:// or https://"):
            WebhookConfig(verify_token="token", webhook_url="ftp://example.com/webhook")

    def test_invalid_webhook_url_no_scheme(self):
        """Test validation fails for webhook URL without scheme."""
        with pytest.raises(ValidationError, match="Webhook URL must start with http:// or https://"):
            WebhookConfig(verify_token="token", webhook_url="example.com/webhook")

    def test_valid_http_webhook_url(self):
        """Test webhook URL with http is valid."""
        config = WebhookConfig(verify_token="token", webhook_url="http://example.com/webhook")
        assert config.webhook_url == "http://example.com/webhook"

    def test_valid_https_webhook_url(self):
        """Test webhook URL with https is valid."""
        config = WebhookConfig(verify_token="token", webhook_url="https://example.com/webhook")
        assert config.webhook_url == "https://example.com/webhook"

    def test_webhook_with_app_secret(self):
        """Test webhook config with app secret."""
        config = WebhookConfig(
            verify_token="token",
            webhook_url="https://example.com/webhook",
            app_secret="my_app_secret",
        )
        assert config.app_secret == "my_app_secret"

    def test_webhook_with_custom_timeout(self):
        """Test webhook config with custom timeout."""
        config = WebhookConfig(
            verify_token="token",
            webhook_url="https://example.com/webhook",
            challenge_timeout=30,
        )
        assert config.challenge_timeout == 30
