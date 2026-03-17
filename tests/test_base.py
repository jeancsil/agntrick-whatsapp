"""Tests for base WhatsApp message classes."""

from datetime import datetime

import pytest

from agntrick_whatsapp.base import (
    BaseWhatsAppMessage,
    TextMessage,
    WhatsAppChannelBase,
    WhatsAppMessageStatus,
    WhatsAppMessageType,
)


class TestWhatsAppMessageType:
    """Test cases for WhatsAppMessageType enum."""

    def test_text_type_value(self) -> None:
        """TEXT enum value is 'text'."""
        assert WhatsAppMessageType.TEXT.value == "text"

    def test_image_type_value(self) -> None:
        """IMAGE enum value is 'image'."""
        assert WhatsAppMessageType.IMAGE.value == "image"

    def test_audio_type_value(self) -> None:
        """AUDIO enum value is 'audio'."""
        assert WhatsAppMessageType.AUDIO.value == "audio"


class TestWhatsAppMessageStatus:
    """Test cases for WhatsAppMessageStatus enum."""

    def test_sending_status(self) -> None:
        """SENDING status value is 'sending'."""
        assert WhatsAppMessageStatus.SENDING.value == "sending"

    def test_sent_status(self) -> None:
        """SENT status value is 'sent'."""
        assert WhatsAppMessageStatus.SENT.value == "sent"

    def test_delivered_status(self) -> None:
        """DELIVERED status value is 'delivered'."""
        assert WhatsAppMessageStatus.DELIVERED.value == "delivered"

    def test_read_status(self) -> None:
        """READ status value is 'read'."""
        assert WhatsAppMessageStatus.READ.value == "read"

    def test_failed_status(self) -> None:
        """FAILED status value is 'failed'."""
        assert WhatsAppMessageStatus.FAILED.value == "failed"


class TestTextMessage:
    """Test cases for TextMessage class."""

    def test_text_message_creation(self) -> None:
        """Test creating a TextMessage with all fields."""
        ts = datetime(2024, 1, 1, 12, 0, 0)
        msg = TextMessage("id1", "+1111", "+2222", "hello world", ts)
        assert msg.message_id == "id1"
        assert msg.from_number == "+1111"
        assert msg.to_number == "+2222"
        assert msg.text == "hello world"
        assert msg.timestamp == ts

    def test_text_message_default_status(self) -> None:
        """TextMessage has SENDING status by default."""
        msg = TextMessage("id1", "+1", "+2", "hello", datetime(2024, 1, 1))
        assert msg.status == WhatsAppMessageStatus.SENDING

    def test_text_message_custom_status(self) -> None:
        """TextMessage can be created with a custom status."""
        msg = TextMessage(
            "id1",
            "+1",
            "+2",
            "hello",
            datetime(2024, 1, 1),
            status=WhatsAppMessageStatus.SENT,
        )
        assert msg.status == WhatsAppMessageStatus.SENT

    def test_text_message_get_message_type(self) -> None:
        """TextMessage returns TEXT message type."""
        msg = TextMessage("id1", "+1", "+2", "hello", datetime(2024, 1, 1))
        assert msg.get_message_type() == WhatsAppMessageType.TEXT

    def test_text_message_to_dict(self) -> None:
        """TextMessage serialization produces expected dict."""
        ts = datetime(2024, 1, 1, 12, 0, 0)
        msg = TextMessage("id1", "+1", "+2", "hello", ts)
        d = msg.to_dict()
        assert d["message_id"] == "id1"
        assert d["from_number"] == "+1"
        assert d["to_number"] == "+2"
        assert d["text"] == "hello"
        assert d["timestamp"] == ts.isoformat()
        assert d["status"] == "sending"
        assert d["message_type"] == "text"
        assert d["metadata"] == {}

    def test_text_message_to_dict_with_metadata(self) -> None:
        """TextMessage with custom metadata serializes correctly."""
        msg = TextMessage(
            "id1",
            "+1",
            "+2",
            "hello",
            datetime(2024, 1, 1),
            metadata={"key": "value", "count": 42},
        )
        d = msg.to_dict()
        assert d["metadata"]["key"] == "value"
        assert d["metadata"]["count"] == 42

    def test_text_message_from_dict(self) -> None:
        """TextMessage can be restored from a dictionary."""
        ts = datetime(2024, 1, 1, 12, 0, 0)
        msg = TextMessage("id1", "+1", "+2", "hello", ts)
        d = msg.to_dict()
        restored = TextMessage.from_dict(d)
        assert restored.message_id == "id1"
        assert restored.from_number == "+1"
        assert restored.to_number == "+2"
        assert restored.text == "hello"
        assert restored.timestamp == ts

    def test_text_message_from_dict_round_trip(self) -> None:
        """TextMessage round-trip (to_dict -> from_dict) preserves all fields."""
        ts = datetime(2024, 6, 15, 8, 30, 0)
        original = TextMessage(
            "msg_100",
            "+1111",
            "+2222",
            "round trip test",
            ts,
            status=WhatsAppMessageStatus.DELIVERED,
            metadata={"source": "test"},
        )
        d = original.to_dict()
        restored = TextMessage.from_dict(d)
        assert restored.text == original.text
        assert restored.from_number == original.from_number
        assert restored.to_number == original.to_number
        assert restored.message_id == original.message_id
        assert restored.status == original.status
        assert restored.metadata == original.metadata

    def test_text_message_from_dict_default_status(self) -> None:
        """TextMessage.from_dict defaults to SENDING when status is missing."""
        d = {
            "message_id": "id1",
            "from_number": "+1",
            "to_number": "+2",
            "text": "hello",
            "timestamp": datetime(2024, 1, 1).isoformat(),
            "metadata": {},
        }
        restored = TextMessage.from_dict(d)
        assert restored.status == WhatsAppMessageStatus.SENDING

    def test_text_message_default_metadata(self) -> None:
        """TextMessage without metadata defaults to empty dict."""
        msg = TextMessage("id1", "+1", "+2", "hello", datetime(2024, 1, 1))
        assert msg.metadata == {}

    def test_text_message_message_type_attribute(self) -> None:
        """TextMessage has message_type attribute set to TEXT."""
        msg = TextMessage("id1", "+1", "+2", "hello", datetime(2024, 1, 1))
        assert msg.message_type == WhatsAppMessageType.TEXT

    def test_text_message_is_instance_of_base(self) -> None:
        """TextMessage is a subclass of BaseWhatsAppMessage."""
        msg = TextMessage("id1", "+1", "+2", "hello", datetime(2024, 1, 1))
        assert isinstance(msg, BaseWhatsAppMessage)


class TestWhatsAppChannelBase:
    """Test cases for WhatsAppChannelBase abstract class."""

    def test_cannot_instantiate_directly(self) -> None:
        """WhatsAppChannelBase cannot be instantiated directly."""
        with pytest.raises(TypeError):
            WhatsAppChannelBase()  # type: ignore[abstract]
