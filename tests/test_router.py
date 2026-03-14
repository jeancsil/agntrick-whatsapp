"""Test cases for router agent behavior."""

from agntrick_whatsapp.config import WhatsAppConfig, WhatsAppRouterConfig
from agntrick_whatsapp.router import WhatsAppRouterAgent


class TestWhatsAppRouterAgent:
    """Test cases for WhatsAppRouterAgent class."""

    def test_init(self):
        """Test router initialization."""
        config = WhatsAppRouterConfig(
            whatsapp=WhatsAppConfig(access_token="test_token", phone_number_id="12345", verify_token="test_verify"),
            storage={"type": "memory"},
        )
        router = WhatsAppRouterAgent(config)
        assert router is not None

    def test_process_text_message(self):
        """Test processing a text message."""
        config = WhatsAppRouterConfig(
            whatsapp=WhatsAppConfig(access_token="test_token", phone_number_id="12345", verify_token="test_verify"),
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

        result = router.process_message(message)
        assert result["status"] == "text"

    def test_process_command_message(self):
        """Test processing a command message."""
        config = WhatsAppRouterConfig(
            whatsapp=WhatsAppConfig(access_token="test_token", phone_number_id="12345", verify_token="test_verify"),
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

        result = router.process_message(message)
        assert result["status"] == "success"

    def test_process_media_message(self):
        """Test processing a media message."""
        config = WhatsAppRouterConfig(
            whatsapp=WhatsAppConfig(access_token="test_token", phone_number_id="12345", verify_token="test_verify"),
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

        result = router.process_message(message)
        # Media messages should return None from receive_message, so default response
        assert "handled" in result["status"]

    def test_process_unknown_message_type(self):
        """Test processing an unknown message type."""
        config = WhatsAppRouterConfig(
            whatsapp=WhatsAppConfig(access_token="test_token", phone_number_id="12345", verify_token="test_verify"),
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

        result = router.process_message(message)
        assert result["status"] == "handled"

    def test_route_to_agent(self):
        """Test routing a message to the appropriate agent."""
        config = WhatsAppRouterConfig(
            whatsapp=WhatsAppConfig(access_token="test_token", phone_number_id="12345", verify_token="test_verify"),
            storage={"type": "memory"},
        )
        router = WhatsAppRouterAgent(config)

        # Mock an agent
        class TestAgent:
            commands = ["schedule"]

            async def process_message(self, message, context):
                return {"response": "scheduled"}

        router.register_agent("scheduling", TestAgent)

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
                                        "text": {"body": "/schedule something"},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        result = router.process_message(message)
        assert result["status"] == "success"
        assert result["agent"] == "scheduling"

    def test_register_agent(self):
        """Test registering a new agent."""
        config = WhatsAppRouterConfig(
            whatsapp=WhatsAppConfig(access_token="test_token", phone_number_id="12345", verify_token="test_verify"),
            storage={"type": "memory"},
        )
        router = WhatsAppRouterAgent(config)

        class TestAgent:
            commands = ["test"]

            async def process_message(self, message, context):
                return {"response": "test response"}

        router.register_agent("test", TestAgent)
        assert "test" in router.agent_registry

    def test_register_duplicate_agent(self):
        """Test registering a duplicate agent."""
        config = WhatsAppRouterConfig(
            whatsapp=WhatsAppConfig(access_token="test_token", phone_number_id="12345", verify_token="test_verify"),
            storage={"type": "memory"},
        )
        router = WhatsAppRouterAgent(config)

        class TestAgent:
            commands = ["test"]

            async def process_message(self, message, context):
                return {"response": "test response"}

        router.register_agent("test", TestAgent)
        # Registering the same agent again should not raise an error
        router.register_agent("test", TestAgent)
        assert "test" in router.agent_registry
