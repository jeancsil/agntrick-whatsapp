"""Test cases for router agent behavior."""

import pytest

from agntrick_whatsapp.base import BaseWhatsAppMessage
from agntrick_whatsapp.channel import WhatsAppChannel
from agntrick_whatsapp.router import WhatsAppRouterAgent


class MockWhatsAppChannel(WhatsAppChannel):
    """Mock channel for testing."""

    def __init__(self) -> None:
        self.messages_sent = []
        self.initialize_called = False

    async def initialize(self) -> None:
        """Mock initialize."""
        self.initialize_called = True

    async def listen(self, callback) -> None:
        """Mock listen - doesn't actually listen."""
        pass

    async def shutdown(self) -> None:
        """Mock shutdown."""
        pass

    async def send_message(self, to_number: str, text: str) -> None:
        """Mock send_message."""
        self.messages_sent.append((to_number, text))

    async def receive_message(self) -> BaseWhatsAppMessage | None:
        """Mock receive_message."""
        return None


@pytest.mark.asyncio
class TestWhatsAppRouterAgent:
    """Test cases for WhatsAppRouterAgent class."""

    async def test_init(self):
        """Test router initialization."""
        channel = MockWhatsAppChannel()
        router = WhatsAppRouterAgent(channel)
        assert router is not None
        assert router.channel is channel

    async def test_handle_text_message(self):
        """Test handling a text message via _handle_message."""
        channel = MockWhatsAppChannel()
        router = WhatsAppRouterAgent(channel)

        # Simulate a bridge-format message
        message = {"sender_id": "12345", "text": "Hello"}

        await router._handle_message(message)
        assert len(channel.messages_sent) == 1
        assert channel.messages_sent[0][0] == "12345"

    async def test_handle_command_message(self):
        """Test handling a command message via _handle_message."""
        channel = MockWhatsAppChannel()
        router = WhatsAppRouterAgent(channel)

        # Command message
        message = {"sender_id": "12345", "text": "/help"}

        await router._handle_message(message)
        assert len(channel.messages_sent) == 1
        # Commands are not implemented, so it says "Command not implemented"
        assert "Command not implemented" in channel.messages_sent[0][1]

    async def test_send_response(self):
        """Test the _send_response method."""
        channel = MockWhatsAppChannel()
        router = WhatsAppRouterAgent(channel)

        incoming = {"sender_id": "12345", "text": "test"}
        await router._send_response(incoming, "Response message")

        assert len(channel.messages_sent) == 1
        assert channel.messages_sent[0][0] == "12345"
        assert channel.messages_sent[0][1] == "Response message"

    async def test_router_not_running_initially(self):
        """Test router is not running when created."""
        channel = MockWhatsAppChannel()
        router = WhatsAppRouterAgent(channel)
        assert not router._running

    async def test_shutdown_event(self):
        """Test shutdown event can be set."""
        channel = MockWhatsAppChannel()
        router = WhatsAppRouterAgent(channel)
        assert not router._shutdown_event.is_set()
        router._shutdown_event.set()
        assert router._shutdown_event.is_set()
