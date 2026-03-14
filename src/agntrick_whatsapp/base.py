"""Base classes and message types for WhatsApp integration."""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class WhatsAppMessageType(Enum):
    """Types of WhatsApp messages."""
    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"
    LOCATION = "location"
    CONTACT = "contact"
    BUTTON = "button"
    INTERACTIVE = "interactive"


class WhatsAppMessageStatus(Enum):
    """Message status enums."""
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class BaseWhatsAppMessage(ABC):
    """Base class for all WhatsApp messages."""

    def __init__(
        self,
        message_id: str,
        from_number: str,
        to_number: str,
        timestamp: datetime,
        status: WhatsAppMessageStatus = WhatsAppMessageStatus.SENDING,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.message_id = message_id
        self.from_number = from_number
        self.to_number = to_number
        self.timestamp = timestamp
        self.status = status
        self.metadata = metadata or {}

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary representation."""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseWhatsAppMessage":
        """Create message from dictionary representation."""
        pass


class TextMessage(BaseWhatsAppMessage):
    """Text message implementation."""

    def __init__(
        self,
        message_id: str,
        from_number: str,
        to_number: str,
        text: str,
        timestamp: datetime,
        status: WhatsAppMessageStatus = WhatsAppMessageStatus.SENDING,
        metadata: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message_id, from_number, to_number, timestamp, status, metadata)
        self.text = text
        self.message_type = WhatsAppMessageType.TEXT

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "from_number": self.from_number,
            "to_number": self.to_number,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "message_type": self.message_type.value,
            "text": self.text,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TextMessage":
        return cls(
            message_id=data["message_id"],
            from_number=data["from_number"],
            to_number=data["to_number"],
            text=data["text"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            status=WhatsAppMessageStatus(data.get("status", "sending")),
            metadata=data.get("metadata", {})
        )


class WhatsAppChannelBase(ABC):
    """Base class for WhatsApp channel implementations."""

    @abstractmethod
    async def send_message(self, to_number: str, message: Union[str, BaseWhatsAppMessage]) -> str:
        """Send a message to a WhatsApp number."""
        pass

    @abstractmethod
    async def receive_message(self, message_data: Dict[str, Any]) -> Optional[BaseWhatsAppMessage]:
        """Process incoming message data."""
        pass

    @abstractmethod
    async def get_message_status(self, message_id: str) -> Optional[WhatsAppMessageStatus]:
        """Get the status of a message."""
        pass