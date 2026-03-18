"""WhatsApp Business API channel implementation.

This module provides the implementation for Meta's WhatsApp Business API.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Optional, Union

from .base import BaseWhatsAppMessage, TextMessage, WhatsAppChannelBase, WhatsAppMessageStatus

logger = logging.getLogger(__name__)


class WhatsAppChannelAPI(WhatsAppChannelBase):
    """Implementation of WhatsApp channel using Meta's Business API."""

    def __init__(
        self,
        access_token: str,
        phone_number_id: str,
    ) -> None:
        """Initialize WhatsApp Business API channel.

        Args:
            access_token: WhatsApp Business API access token.
            phone_number_id: WhatsApp Business phone number ID.
        """
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.base_url = "https://graph.facebook.com/v18.0"
        self.message_queue: dict[str, asyncio.Future] = {}
        self._webhook_callback: Optional[Callable[[Any], Any]] = None
        logger.info("Using Business API mode (Meta WhatsApp Business API)")

    async def initialize(self) -> None:
        """Initialize the channel (no-op for API)."""
        pass

    async def shutdown(self) -> None:
        """Shutdown the channel (no-op for API)."""
        pass

    async def listen(self, callback: Callable[[Any], Any]) -> None:
        """Set up a callback for webhook messages."""
        self._webhook_callback = callback

    async def send_message(self, to_number: str, message: Union[str, BaseWhatsAppMessage]) -> str:
        """Send message using Business API."""
        if isinstance(message, str):
            # In Python 3.12+ we avoid get_event_loop() but here keeping existing logic
            message_id = f"msg_{datetime.now().timestamp()}"
            message = TextMessage(
                message_id=message_id,
                from_number=self.phone_number_id,
                to_number=to_number,
                text=message,
                timestamp=datetime.now(),
            )

        payload = self._build_message_payload(message)

        try:
            # In a real implementation, this would make an HTTP request to WhatsApp API
            # For now, we'll simulate the response
            msg_id = message.message_id
            await self._simulate_api_call(payload)

            # Create a future for tracking message status
            future: asyncio.Future[str] = asyncio.Future()
            self.message_queue[msg_id] = future
            asyncio.create_task(self._track_message_status(msg_id, future))

            return msg_id
        except Exception as e:
            raise Exception(f"Failed to send message: {str(e)}")

    def _build_message_payload(self, message: BaseWhatsAppMessage) -> dict[str, Any]:
        """Build API payload for sending message."""
        payload = {
            "messaging_product": "whatsapp",
            "to": message.to_number,
            "type": message.get_message_type().value,
        }

        if isinstance(message, TextMessage):
            payload["text"] = {"body": message.text}  # type: ignore

        return payload

    async def receive_message(self, message_data: dict[str, Any]) -> Optional[BaseWhatsAppMessage]:
        """Process incoming webhook message (Business API mode)."""
        try:
            entry = message_data.get("entry", [{}])[0] if isinstance(message_data.get("entry"), list) else {}
            changes = entry.get("changes", [{}])[0] if isinstance(entry.get("changes"), list) else {}
            value = changes.get("value", {})
            messages = value.get("messages", [])

            if not messages:
                return None

            message_info = messages[0]
            message_id = message_info.get("id")
            from_number = message_info.get("from")
            timestamp = datetime.fromtimestamp(int(message_info.get("timestamp", 0)))
            message_type = message_info.get("type")

            if message_type == "text":
                text = message_info.get("text", {}).get("body", "")
                msg = TextMessage(
                    message_id=message_id,
                    from_number=from_number,
                    to_number=self.phone_number_id,
                    text=text,
                    timestamp=timestamp,
                )
                if self._webhook_callback:
                    # In a real app we might wrap this, but here matching old logic
                    pass
                return msg

            # Handle other message types as needed
            return None
        except Exception as e:
            logger.error(f"Error processing incoming message: {e}")
            return None

    async def get_message_status(self, message_id: str) -> Optional[WhatsAppMessageStatus]:
        """Get the status of a message."""
        future = self.message_queue.get(message_id)
        if future and future.done():
            result = future.result()
            if isinstance(result, WhatsAppMessageStatus):
                return result
        return WhatsAppMessageStatus.SENDING

    async def _simulate_api_call(self, payload: dict[str, Any]) -> None:
        """Simulate API call to WhatsApp."""
        await asyncio.sleep(0.1)  # Simulate network delay

    async def _track_message_status(self, message_id: str, future: asyncio.Future) -> None:
        """Simulate tracking message status updates."""
        try:
            # Simulate status updates over time
            await asyncio.sleep(1)
            future.set_result(WhatsAppMessageStatus.SENT)  # type: ignore

            # Remove from queue after completion
            await asyncio.sleep(5)
            if message_id in self.message_queue:
                del self.message_queue[message_id]
        except Exception as e:
            logger.error(f"Error tracking message status: {e}")
            if not future.done():
                future.set_exception(e)
