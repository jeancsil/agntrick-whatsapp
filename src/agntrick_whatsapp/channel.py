"""WhatsApp channel implementation."""

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional, Union

from .base import BaseWhatsAppMessage, TextMessage, WhatsAppChannelBase, WhatsAppMessageStatus


class WhatsAppChannel(WhatsAppChannelBase):
    """Implementation of WhatsApp channel using official WhatsApp Business API."""

    def __init__(self, access_token: str, phone_number_id: str):
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.base_url = "https://graph.facebook.com/v18.0"
        self.message_queue: Dict[str, asyncio.Future] = {}

    async def send_message(self, to_number: str, message: Union[str, BaseWhatsAppMessage]) -> str:
        """Send a message to a WhatsApp number."""
        if isinstance(message, str):
            message = TextMessage(
                message_id=f"msg_{datetime.now().timestamp()}",
                from_number=self.phone_number_id,
                to_number=to_number,
                text=message,
                timestamp=datetime.now(),
            )

        payload = self._build_message_payload(message)

        try:
            # In a real implementation, this would make an HTTP request to WhatsApp API
            # For now, we'll simulate the response
            message_id = message.message_id
            await self._simulate_api_call(payload)

            # Create a future for tracking message status
            future: asyncio.Future[str] = asyncio.Future()
            self.message_queue[message_id] = future
            asyncio.create_task(self._track_message_status(message_id, future))

            return message_id
        except Exception as e:
            raise Exception(f"Failed to send message: {str(e)}")

    def _build_message_payload(self, message: BaseWhatsAppMessage) -> Dict[str, Any]:
        """Build API payload for sending message."""
        payload = {
            "messaging_product": "whatsapp",
            "to": message.to_number,
            "type": message.get_message_type().value,
        }

        if isinstance(message, TextMessage):
            payload["text"] = {"body": message.text}  # type: ignore

        return payload

    async def receive_message(self, message_data: Dict[str, Any]) -> Optional[BaseWhatsAppMessage]:
        """Process incoming message data from webhook."""
        try:
            entry = message_data.get("entry", [{}])[0] if isinstance(message_data.get("entry"), list) else {}
            changes = entry.get("changes", [{}])[0] if isinstance(entry.get("changes"), list) else {}
            value = changes.get("value", {})
            messages = value.get("messages", [])

            if not messages:
                return None

            message = messages[0]
            message_id = message.get("id")
            from_number = message.get("from")
            timestamp = datetime.fromtimestamp(int(message.get("timestamp", 0)))
            message_type = message.get("type")

            if message_type == "text":
                text = message.get("text", {}).get("body", "")
                return TextMessage(
                    message_id=message_id,
                    from_number=from_number,
                    to_number=self.phone_number_id,
                    text=text,
                    timestamp=timestamp,
                )

            # Handle other message types as needed
            return None

        except Exception as e:
            print(f"Error processing incoming message: {e}")
            return None

    async def get_message_status(self, message_id: str) -> Optional[WhatsAppMessageStatus]:
        """Get the status of a message."""
        # Check if we have a future for this message
        future = self.message_queue.get(message_id)
        if future and future.done():
            result = future.result()
            if isinstance(result, WhatsAppMessageStatus):
                return result
        return WhatsAppMessageStatus.SENDING

    async def _simulate_api_call(self, payload: Dict[str, Any]) -> None:
        """Simulate API call to WhatsApp."""
        # In a real implementation, this would make an HTTP request
        await asyncio.sleep(0.1)  # Simulate network delay

    async def _track_message_status(self, message_id: str, future: asyncio.Future) -> None:
        """Simulate tracking message status updates."""
        try:
            # Simulate status updates over time
            await asyncio.sleep(1)
            future.set_result(WhatsAppMessageStatus.SENT)

            # Remove from queue after completion
            await asyncio.sleep(5)
            if message_id in self.message_queue:
                del self.message_queue[message_id]
        except Exception as e:
            print(f"Error tracking message status: {e}")
            if not future.done():
                future.set_exception(e)
