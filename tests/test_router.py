"""Test cases for router agent behavior."""

import pytest

from agntrick_whatsapp.config import WhatsAppConfig, WhatsAppRouterConfig
from agntrick_whatsapp.router import WhatsAppRouterAgent


@pytest.mark.asyncio
class TestWhatsAppRouterAgent:
    """Test cases for WhatsAppRouterAgent class."""

    async def test_init(self):
        """Test router initialization."""
        config = WhatsAppRouterConfig(
            whatsapp=WhatsAppConfig(access_token="EATestToken123", phone_number_id="12345", verify_token="test_verify"),
            storage={"type": "memory"},
        )
        router = WhatsAppRouterAgent(config)
        assert router is not None

    async def test_process_text_message(self):
        """Test processing a text message."""
        config = WhatsAppRouterConfig(
            whatsapp=WhatsAppConfig(access_token="EATestToken123", phone_number_id="12345", verify_token="test_verify"),
            storage={"type": "memory"},
        )
        router = WhatsAppRouterAgent(config)
        message = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "msg1",
                                        "from": "12345",
                                        "timestamp": "1234567890",
                                        "type": "text",
                                        "text": {"body": "Hello"},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        result = await router.process_message(message)
        assert result["status"] in ["handled", "text", "success"]

    async def test_process_command_message(self):
        """Test processing a command message."""
        config = WhatsAppRouterConfig(
            whatsapp=WhatsAppConfig(access_token="EATestToken123", phone_number_id="12345", verify_token="test_verify"),
            storage={"type": "memory"},
        )
        router = WhatsAppRouterAgent(config)
        message = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "msg1",
                                        "from": "12345",
                                        "timestamp": "1234567890",
                                        "type": "text",
                                        "text": {"body": "/help"},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        result = await router.process_message(message)
        assert result["status"] in ["success", "handled"]

    async def test_process_media_message(self):
        """Test processing a media message."""
        config = WhatsAppRouterConfig(
            whatsapp=WhatsAppConfig(access_token="EATestToken123", phone_number_id="12345", verify_token="test_verify"),
            storage={"type": "memory"},
        )
        router = WhatsAppRouterAgent(config)
        message = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "msg1",
                                        "from": "12345",
                                        "timestamp": "1234567890",
                                        "type": "image",
                                        "image": {"url": "http://example.com/image.jpg"},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        result = await router.process_message(message)
        # Media messages should return None from receive_message, so default response
        assert "handled" in result["status"]

    async def test_process_unknown_message_type(self):
        """Test processing an unknown message type."""
        config = WhatsAppRouterConfig(
            whatsapp=WhatsAppConfig(access_token="EATestToken123", phone_number_id="12345", verify_token="test_verify"),
            storage={"type": "memory"},
        )
        router = WhatsAppRouterAgent(config)
        message = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "msg1",
                                        "from": "12345",
                                        "timestamp": "1234567890",
                                        "type": "unknown",
                                        "text": {"body": "test"},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        result = await router.process_message(message)
        assert result["status"] == "handled"

    async def test_register_agent(self):
        """Test registering a new agent."""
        config = WhatsAppRouterConfig(
            whatsapp=WhatsAppConfig(access_token="EATestToken123", phone_number_id="12345", verify_token="test_verify"),
            storage={"type": "memory"},
        )
        router = WhatsAppRouterAgent(config)

        class TestAgent:
            commands = ["test"]

            async def process_message(self, message, context):
                return {"response": "test response"}

        router.register_agent("test", TestAgent)
        assert "test" in router.agent_registry
