"""Pydantic configuration models for WhatsApp integration."""

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationInfo, field_validator


class WhatsAppConfig(BaseModel):
    """Configuration for WhatsApp channel."""

    access_token: str = Field(..., description="WhatsApp Business API access token")
    phone_number_id: str = Field(..., description="WhatsApp Business phone number ID")
    verify_token: str = Field(..., description="Webhook verification token")
    api_version: str = Field(default="18.0", description="WhatsApp API version")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for incoming messages")
    message_timeout: int = Field(default=30, description="Message timeout in seconds")
    retry_attempts: int = Field(default=3, description="Number of retry attempts for failed messages")
    retry_delay: int = Field(default=5, description="Delay between retries in seconds")

    @field_validator("access_token")
    @classmethod
    def validate_access_token(cls, v: str) -> str:
        if not v or not v.startswith("EA"):
            raise ValueError('Access token must start with "EA"')
        return v

    @field_validator("phone_number_id")
    @classmethod
    def validate_phone_number_id(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("Phone number ID must be numeric")
        return v

    @field_validator("api_version")
    @classmethod
    def validate_api_version(cls, v: str) -> str:
        allowed_versions = ["18.0", "17.0", "16.0"]
        if v not in allowed_versions:
            raise ValueError(f"API version must be one of: {', '.join(allowed_versions)}")
        return v


class StorageConfig(BaseModel):
    """Configuration for storage backend."""

    type: str = Field(..., description="Storage type (sqlite, postgres, etc.)")
    path: Optional[str] = Field(None, description="Path for file-based storage")
    connection_string: Optional[str] = Field(None, description="Database connection string")
    max_connections: int = Field(default=10, description="Maximum database connections")
    timeout: int = Field(default=30, description="Database operation timeout in seconds")

    @field_validator("type")
    @classmethod
    def validate_storage_type(cls, v: str) -> str:
        allowed_types = ["sqlite", "postgres", "mysql", "memory"]
        if v not in allowed_types:
            raise ValueError(f"Storage type must be one of: {', '.join(allowed_types)}")
        return v


class AgentConfig(BaseModel):
    """Configuration for WhatsApp agent."""

    name: str = Field(..., description="Agent name")
    description: Optional[str] = Field(None, description="Agent description")
    enabled: bool = Field(default=True, description="Whether the agent is enabled")
    commands: List[str] = Field(default_factory=list, description="List of supported commands")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Additional agent settings")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("Agent name must be alphanumeric or underscore")
        return v


class WhatsAppRouterConfig(BaseModel):
    """Main configuration for WhatsApp router agent."""

    whatsapp: WhatsAppConfig = Field(..., description="WhatsApp configuration")
    storage: StorageConfig = Field(..., description="Storage configuration")
    agents: List[AgentConfig] = Field(default_factory=list, description="List of configured agents")
    default_agent: Optional[str] = Field(None, description="Default agent for unhandled messages")
    message_history_limit: int = Field(default=1000, description="Maximum messages to keep in history")
    max_conversation_length: int = Field(default=100, description="Maximum conversation length")
    debug_mode: bool = Field(default=False, description="Enable debug logging")
    conversation_enabled: bool = Field(default=True, description="Enable conversation history")
    max_conversation_tokens: int = Field(default=4000, description="Max tokens in conversation context")

    @field_validator("default_agent")
    @classmethod
    def validate_default_agent(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        if v and v not in [agent.name for agent in info.data.get("agents", [])]:
            raise ValueError("Default agent must be in the agents list")
        return v

    @field_validator("message_history_limit")
    @classmethod
    def validate_message_history_limit(cls, v: int) -> int:
        if v < 0 or v > 10000:
            raise ValueError("Message history limit must be between 0 and 10000")
        return v

    @field_validator("max_conversation_length")
    @classmethod
    def validate_max_conversation_length(cls, v: int) -> int:
        if v < 10 or v > 1000:
            raise ValueError("Conversation length must be between 10 and 1000")
        return v

    @classmethod
    def load_from_file(cls, file_path: str) -> "WhatsAppRouterConfig":
        """Load configuration from file."""
        import json

        with open(file_path, "r") as f:
            data = json.load(f)
        return cls(**data)

    def save_to_file(self, file_path: str) -> None:
        """Save configuration to file."""
        import json

        with open(file_path, "w") as f:
            json.dump(self.model_dump(), f, indent=2)


class WebhookConfig(BaseModel):
    """Configuration for webhook handling."""

    verify_token: str = Field(..., description="Webhook verification token")
    app_secret: Optional[str] = Field(None, description="Webhook app secret")
    webhook_url: str = Field(..., description="Webhook URL")
    challenge_timeout: int = Field(default=10, description="Challenge timeout in seconds")

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("Webhook URL must start with http:// or https://")
        return v
