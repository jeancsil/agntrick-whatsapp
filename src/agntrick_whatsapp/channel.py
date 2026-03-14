"""WhatsApp channel implementation with dual support for both Business API and Bridge (neonize/whatsmeow).

This module conditionally imports the appropriate implementation based on availability:
- Business API (access_token, phone_number_id) when using Meta's WhatsApp Business API
- Bridge/QR Code (storage_path, allowed_contact) when using personal WhatsApp accounts with whatsmeow
"""

import logging
from typing import Any, Optional, Union

from .base import BaseWhatsAppMessage, WhatsAppChannelBase, WhatsAppMessageStatus

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
        """Initialize WhatsApp channel with appropriate strategy."""

        from .channel_api import WhatsAppChannelAPI

        has_business_api = access_token is not None and phone_number_id is not None
        has_bridge_mode = storage_path is not None

        if not has_business_api and not has_bridge_mode:
            raise ValueError(
                "At least one set of parameters must be provided:\n"
                "  - access_token and phone_number_id (for Business API mode), OR\n"
                "  - storage_path (for Bridge/QR Code mode)"
            )

        self._strategy: WhatsAppChannelBase

        if access_token and phone_number_id:
            self._mode = "business_api"
            self._strategy = WhatsAppChannelAPI(
                access_token=access_token,
                phone_number_id=phone_number_id,
            )
        elif storage_path:
            self._mode = "bridge"
            if _BRIDGE_AVAILABLE:
                self._strategy = bridge_impl.WhatsAppChannel(  # type: ignore[assignment]
                    storage_path=storage_path,
                    allowed_contact=allowed_contact or "",
                    log_filtered_messages=log_filtered_messages,
                    poll_interval=poll_interval,
                    typing_indicators=typing_indicators,
                    min_typing_duration=min_typing_duration,
                    dedup_window=dedup_window,
                )
            else:
                raise RuntimeError(
                    "Bridge mode requested but neonize library is not available. "
                    "Install system dependencies (e.g., libmagic) and ensure neonize extras are installed."
                )

    async def initialize(self) -> None:
        """Initialize the channel strategy."""
        await self._strategy.initialize()

    async def shutdown(self) -> None:
        """Shutdown the channel strategy."""
        await self._strategy.shutdown()

    async def listen(self, callback: Any) -> None:
        """Start listening for incoming messages strategy."""
        await self._strategy.listen(callback)

    async def send_message(self, to_number: str, message: Union[str, BaseWhatsAppMessage]) -> str:
        """Send a message using the selected strategy."""
        return await self._strategy.send_message(to_number, message)

    async def receive_message(self, message_data: dict[str, Any]) -> Optional[BaseWhatsAppMessage]:
        """Receive message via the selected strategy."""
        return await self._strategy.receive_message(message_data)

    async def get_message_status(self, message_id: str) -> Optional[WhatsAppMessageStatus]:
        """Get the status of a message."""
        return await self._strategy.get_message_status(message_id)
