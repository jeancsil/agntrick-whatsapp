"""WhatsApp channel implementation with dual support for both Business API and Bridge (neonize/whatsmeow).

This module conditionally imports the appropriate implementation based on availability:
- Business API (access_token, phone_number_id) when using Meta's WhatsApp Business API
- Bridge/QR Code (storage_path, allowed_contact) when using personal WhatsApp accounts with whatsmeow
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional, Union

from .base import BaseWhatsAppMessage, TextMessage, WhatsAppChannelBase, WhatsAppMessageStatus

logger = logging.getLogger(__name__)

# Try to import bridge implementation (whatsmeow/QR code login)
# If available, use it for personal WhatsApp accounts
try:
    from . import channel_bridge as bridge_impl

    _BRIDGE_AVAILABLE = True
except ImportError:
    # Bridge not available, only Business API
    _BRIDGE_AVAILABLE = False


class WhatsAppChannel(WhatsAppChannelBase):
    """Implementation of WhatsApp channel with dual support.

    Supports both:
    1. Business API (WhatsApp Business API with access_token, phone_number_id)
    2. Bridge/QR Code (neonize/whatsmeow with storage_path, allowed_contact)
    """

    def __init__(
        self,
        # Business API parameters
        access_token: Optional[str] = None,
        phone_number_id: Optional[str] = None,
        # Bridge parameters
        storage_path: Optional[str] = None,
        allowed_contact: Optional[str] = None,
        # Optional bridge-specific parameters
        log_filtered_messages: bool = False,
        poll_interval: float = 1.0,
        typing_indicators: bool = True,
        min_typing_duration: float = 2.0,
        dedup_window: float = 10.0,
    ) -> None:
        """Initialize WhatsApp channel with appropriate implementation.

        The implementation is selected based on which parameters are provided:
        - If access_token and phone_number_id are provided → Business API
        - If storage_path is provided → Bridge/QR Code

        Args:
            access_token: WhatsApp Business API access token (for Business API mode).
            phone_number_id: WhatsApp Business phone number ID (for Business API mode).
            storage_path: Directory for bridge session storage (for Bridge mode).
            allowed_contact: Phone number to filter messages (for Bridge mode).
            log_filtered_messages: Log filtered messages (for Bridge mode).
            poll_interval: Polling interval in seconds (for Bridge mode, not used in event mode).
            typing_indicators: Send typing indicators (for Bridge mode).
            min_typing_duration: Minimum typing duration in seconds (for Bridge mode).
            dedup_window: Duplicate detection window in seconds (for Bridge mode).

        Note: At least one set of parameters must be provided for each mode.
        """
        self._validate_initialization(access_token, phone_number_id, storage_path)

        # Business API mode
        if access_token and phone_number_id:
            self._mode = "business_api"
            self.access_token = access_token
            self.phone_number_id = phone_number_id
            self.base_url = "https://graph.facebook.com/v18.0"
            self.message_queue: dict[str, asyncio.Future] = {}
            logger.info("Using Business API mode (Meta WhatsApp Business API)")
            return

        # Bridge mode
        if storage_path:
            self._mode = "bridge"
            if _BRIDGE_AVAILABLE:
                self._bridge = bridge_impl.WhatsAppChannel(
                    storage_path=storage_path,
                    allowed_contact=allowed_contact or "",
                    log_filtered_messages=log_filtered_messages,
                    poll_interval=poll_interval,
                    typing_indicators=typing_indicators,
                    min_typing_duration=min_typing_duration,
                    dedup_window=dedup_window,
                )
                logger.info(f"Using Bridge/QR Code mode with storage={storage_path}, allowed_contact={allowed_contact}")
            else:
                raise RuntimeError(
                    "Bridge mode requested but neonize library is not available. "
                    "Install system dependencies (e.g., libmagic) and ensure neonize extras are installed."
                )

    def _validate_initialization(
        self,
        access_token: Optional[str],
        phone_number_id: Optional[str],
        storage_path: Optional[str],
    ) -> None:
        """Validate that at least one mode's parameters are provided."""
        has_business_api = access_token is not None and phone_number_id is not None
        has_bridge_mode = storage_path is not None

        if not has_business_api and not has_bridge_mode:
            raise ValueError(
                "At least one set of parameters must be provided:\n"
                "  - access_token and phone_number_id (for Business API mode), OR\n"
                "  - storage_path (for Bridge/QR Code mode)"
            )

    async def send_message(self, to_number: str, message: Union[str, BaseWhatsAppMessage]) -> str:
        """Send a message to a WhatsApp number.

        Delegates to the appropriate implementation based on mode.
        """
        if self._mode == "business_api":
            return await self._send_business_api_message(to_number, message)
        elif self._mode == "bridge":
            return await self._send_bridge_message(to_number, message)
        else:
            raise RuntimeError(f"Unknown mode: {self._mode}")

    async def _send_business_api_message(self, to_number: str, message: Union[str, BaseWhatsAppMessage]) -> str:
        """Send message using Business API."""
        if isinstance(message, str):
            message = TextMessage(
                message_id=f"msg_{asyncio.get_event_loop().time()}",
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

    async def _send_bridge_message(self, to_number: str, message: Union[str, Any]) -> str:
        """Send message using Bridge/QR Code (neonize)."""
        # The bridge's send() method returns a jid string
        # We need to pass a dict with appropriate keys
        if isinstance(message, str):
            message_dict = {"text": message, "recipient_id": to_number}
        elif isinstance(message, dict) and "text" in message:
            message_dict = message
        else:
            raise ValueError(f"Unsupported message type: {type(message)}")

        # The bridge send() returns a jid (string), not a dict
        return await self._bridge.send(message_dict)

    async def receive_message(self, message_data: dict[str, Any]) -> Optional[BaseWhatsAppMessage]:
        """Process incoming message data.

        Delegates to the appropriate implementation based on mode.
        """
        if self._mode == "business_api":
            return await self._receive_business_api_message(message_data)
        elif self._mode == "bridge":
            return await self._receive_bridge_message(message_data)
        else:
            raise RuntimeError(f"Unknown mode: {self._mode}")

    async def _receive_business_api_message(self, message_data: dict[str, Any]) -> Optional[BaseWhatsAppMessage]:
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

    async def _receive_bridge_message(self, message_data: dict[str, Any]) -> Optional[BaseWhatsAppMessage]:
        """Process incoming message from Bridge/QR Code (delegated to bridge implementation)."""
        # The bridge implementation has its own message handling logic
        # We just return None here - the bridge will handle filtering and callback invocation
        # This method exists for API compatibility but is not used in bridge mode
        return None

    async def get_message_status(self, message_id: str) -> Optional[WhatsAppMessageStatus]:
        """Get the status of a message.

        Delegates to the appropriate implementation based on mode.
        """
        if self._mode == "business_api":
            future = self.message_queue.get(message_id)
            if future and future.done():
                result = future.result()
                if isinstance(result, WhatsAppMessageStatus):
                    return result
            return WhatsAppMessageStatus.SENDING
        elif self._mode == "bridge":
            # Bridge doesn't track message status
            return None
        else:
            raise RuntimeError(f"Unknown mode: {self._mode}")

    async def initialize(self) -> None:
        """Initialize the channel.

        Delegates to the appropriate implementation based on mode.
        """
        if self._mode == "bridge" and hasattr(self, "_bridge") and hasattr(self._bridge, "initialize"):
            await self._bridge.initialize()
        # Business API mode doesn't need initialization

    async def listen(self, callback: Any) -> None:
        """Start listening for incoming messages.

        This method handles both modes:
        - Bridge mode: Starts listening via the bridge implementation
        - Business API mode: Sets up a callback for webhook messages

        Args:
            callback: A function to call when a new message arrives.
        """
        if self._mode == "bridge" and hasattr(self, "_bridge") and hasattr(self._bridge, "listen"):
            await self._bridge.listen(callback)
        else:
            # For Business API mode, we set the callback but don't start listening
            # because webhooks are handled externally
            self._webhook_callback = callback

    async def shutdown(self) -> None:
        """Shutdown the channel.

        Delegates to the appropriate implementation based on mode.
        """
        if self._mode == "bridge" and hasattr(self, "_bridge") and hasattr(self._bridge, "shutdown"):
            await self._bridge.shutdown()
        # Business API mode doesn't need explicit shutdown

    async def _simulate_api_call(self, payload: dict[str, Any]) -> None:
        """Simulate API call to WhatsApp."""
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
