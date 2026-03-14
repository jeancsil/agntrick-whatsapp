"""Test cases for router agent behavior."""

import pytest
from unittest.mock import Mock, patch

from agntrick_whatsapp.router import WhatsAppRouter


class TestWhatsAppRouter:
    """Test cases for WhatsAppRouter class."""

    def test_init(self):
        """Test router initialization."""
        router = WhatsAppRouter()
        assert router is not None

    @patch('agntrick_whatsapp.router.MessageHandler')
    def test_process_text_message(self, mock_handler):
        """Test processing a text message."""
        router = WhatsAppRouter()
        message = {"type": "text", "content": "Hello", "sender": "12345"}

        router.process_message(message)
        mock_handler.handle_text.assert_called_once_with(message)

    @patch('agntrick_whatsapp.router.MessageHandler')
    def test_process_command_message(self, mock_handler):
        """Test processing a command message."""
        router = WhatsAppRouter()
        message = {"type": "text", "content": "/hello", "sender": "12345"}

        router.process_message(message)
        mock_handler.handle_command.assert_called_once_with(message)

    @patch('agntrick_whatsapp.router.MessageHandler')
    def test_process_media_message(self, mock_handler):
        """Test processing a media message."""
        router = WhatsAppRouter()
        message = {"type": "image", "url": "http://example.com/image.jpg", "sender": "12345"}

        router.process_message(message)
        mock_handler.handle_media.assert_called_once_with(message)

    def test_process_unknown_message_type(self):
        """Test processing an unknown message type."""
        router = WhatsAppRouter()
        message = {"type": "unknown", "content": "test", "sender": "12345"}

        result = router.process_message(message)
        assert "Unsupported message type" in result

    def test_route_to_agent(self):
        """Test routing a message to the appropriate agent."""
        router = WhatsAppRouter()
        message = {"type": "text", "content": "I want to schedule something", "sender": "12345"}

        with patch('agntrick_whatsapp.router.SchedulingAgent') as mock_agent:
            router.route_to_agent(message, "scheduling")
            mock_agent.assert_called_once()

    def test_register_agent(self):
        """Test registering a new agent."""
        router = WhatsAppRouter()

        class TestAgent:
            pass

        router.register_agent("test", TestAgent)
        assert "test" in router.available_agents

    def test_register_duplicate_agent(self):
        """Test registering a duplicate agent."""
        router = WhatsAppRouter()

        class TestAgent:
            pass

        router.register_agent("test", TestAgent)
        with pytest.raises(ValueError):
            router.register_agent("test", TestAgent)