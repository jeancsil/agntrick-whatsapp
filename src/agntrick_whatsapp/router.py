"""WhatsAppRouterAgent for routing messages to appropriate agents.

This version supports both:
- Business API mode (WhatsApp Business API with access_token)
- Bridge mode (whatsmeow/QR Code with storage_path, allowed_contact)
"""

import asyncio
import logging
from datetime import datetime, UTC
from typing import Any, Dict, List

from .base import BaseWhatsAppMessage
from .channel import WhatsAppChannel
from .commands import CommandHandler, CommandParser

logger = logging.getLogger(__name__)

# Constants
SCHEDULER_INTERVAL_SECONDS = 10


# System prompts
DEFAULT_SYSTEM_PROMPT = """You are a helpful AI assistant communicating through WhatsApp.
Be concise and friendly in your responses.
Avoid overly long explanations.
Use emojis occasionally to be more conversational.
If you need to show code or data, use formatted text blocks.
Focus on being helpful and direct.
"""

# Router initialization now accepts a Channel object directly
# The channel can be either Business API or Bridge implementation
# and will provide the appropriate methods (send, listen, shutdown, initialize)


class WhatsAppRouterAgent:
    """Agent that routes WhatsApp messages to appropriate handlers.

    Args:
        channel: The WhatsAppChannel instance to use (can be Business API or Bridge).
        model_name: Optional name of LLM model to use.
        temperature: The temperature for LLM responses (default: 0.7).
        mcp_servers_override: Optional override for MCP servers.
        audio_transcriber_config: Optional audio transcription config.
    """

    def __init__(
        self,
        channel: WhatsAppChannel,
        model_name: str | None = None,
        temperature: float = 0.7,
        mcp_servers_override: list[str] | None = None,
        audio_transcriber_config: Any = None,
    ) -> None:
        self.channel = channel
        self._model_name = model_name
        self._temperature = temperature
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._mcp_servers_override = mcp_servers_override
        self._audio_transcriber_config = audio_transcriber_config

        # Message history
        self.message_history: List[Dict[str, Any]] = []
        self.conversations: Dict[str, Dict[str, Any]] = {}

        # Command parser
        self._command_parser = CommandParser()

        logger.info(f"WhatsAppRouterAgent initialized with channel type: {type(channel).__name__}")

    async def start(self) -> None:
        """Start WhatsApp router agent."""
        if self._running:
            logger.warning("Agent is already running")
            return

        logger.info("Starting WhatsApp router agent...")
        try:
            # Initialize channel (works for both implementations)
            if hasattr(self.channel, "initialize"):
                await self.channel.initialize()

            # Set up MCP servers
            self._mcp_servers = self._mcp_servers_override or ["fetch"]

            # Start listening for messages
            await self.channel.listen(self._handle_message)

        except Exception as e:
            logger.error(f"Failed to start WhatsApp router agent: {e}")
            self._running = False
            raise

    async def stop(self) -> None:
        """Stop WhatsApp router agent."""
        if not self._running:
            return

        logger.info("Stopping WhatsApp router agent...")
        self._running = False

        # Signal shutdown to all components
        self._shutdown_event.set()

        # Shut down channel
        try:
            if hasattr(self.channel, "shutdown"):
                await self.channel.shutdown()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

        logger.info("WhatsApp router agent stopped")

    async def _handle_message(self, incoming: Any) -> None:
        """Handle an incoming message from the channel.

        The incoming message format depends on channel implementation:
        - Business API: Dict with 'entry', 'changes', etc.
        - Bridge: BaseWhatsAppMessage with text, sender_id, etc.
        """
        self.logger.info(f"Processing message: {incoming}")

        try:
            # Check if we have text content
            if isinstance(incoming, dict) and "text" in incoming:
                message_text = incoming.get("text", "")

                # Check for commands using the bridge's command parser
                # (works with both implementations)
                parser = CommandParser()
                command = parser.parse(message_text)
                self.logger.info(f"Parsed command: {command}")

                # Handle commands
                if command.get("command"):
                    # Simple echo for commands like /help
                    response = f"Command not implemented: {command.get('command')}"
                    await self._send_response(incoming, response)
                    return

                # For regular messages, just echo back
                response = f"Received: {message_text}"
                await self._send_response(incoming, response)

        except Exception as e:
            self.logger.error(f"Error handling message: {e}")

            try:
                # Send error response if possible
                if isinstance(incoming, dict) and "sender_id" in incoming:
                    await self._send_response(incoming, "Sorry, I encountered an error processing your message.")
            except Exception as send_error:
                self.logger.error(f"Failed to send error response: {send_error}")

    async def _send_response(self, incoming: Any, response: str) -> None:
        """Send a response message through the channel.

        The incoming object format varies by channel type:
        - Bridge: Has sender_id, can be dict with text
        - Business API: Has from_number, to_number

        We normalize to get the recipient number and text.
        """
        # Get recipient based on incoming format
        if isinstance(incoming, dict):
            recipient_id = incoming.get("sender_id", "")
            text = incoming.get("text", response)
        elif isinstance(incoming, BaseWhatsAppMessage):
            recipient_id = incoming.to_number
            text = response
        else:
            self.logger.warning(f"Unknown incoming format: {type(incoming)}")
            return

        # Send through the channel
        await self.channel.send_message(recipient_id, text)
        self.logger.info(f"Response sent to {recipient_id}")
