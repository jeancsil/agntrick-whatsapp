"""Test cases for WhatsAppChannelAPI (Business API implementation)."""

import asyncio
from unittest.mock import patch

import pytest

from agntrick_whatsapp.base import TextMessage, WhatsAppMessageStatus
from agntrick_whatsapp.channel_api import WhatsAppChannelAPI


class TestWhatsAppChannelAPI:
    """Test cases for WhatsAppChannelAPI class."""

    def test_init(self):
        """Test initialization of WhatsAppChannelAPI."""
        api = WhatsAppChannelAPI(access_token="EAAxxx", phone_number_id="1234567890")
        assert api.access_token == "EAAxxx"
        assert api.phone_number_id == "1234567890"
        assert api.base_url == "https://graph.facebook.com/v18.0"
        assert api.message_queue == {}
        assert api._webhook_callback is None

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test initialize is a no-op for API mode."""
        api = WhatsAppChannelAPI("EAAxxx", "1234567890")
        await api.initialize()
        # Should not raise any errors

    @pytest.mark.asyncio
    async def test_shutdown(self):
        """Test shutdown is a no-op for API mode."""
        api = WhatsAppChannelAPI("EAAxxx", "1234567890")
        await api.shutdown()
        # Should not raise any errors

    @pytest.mark.asyncio
    async def test_listen_sets_callback(self):
        """Test listen sets the webhook callback."""
        api = WhatsAppChannelAPI("EAAxxx", "1234567890")

        async def dummy_callback(msg):
            pass

        await api.listen(dummy_callback)
        assert api._webhook_callback is dummy_callback

    @pytest.mark.asyncio
    async def test_send_message_with_string(self):
        """Test sending a message with string text."""
        api = WhatsAppChannelAPI("EAAxxx", "1234567890")
        message_id = await api.send_message("+1234567890", "Hello world")
        assert message_id.startswith("msg_")
        # Check that future was created and added to queue
        assert message_id in api.message_queue

    @pytest.mark.asyncio
    async def test_send_message_with_text_message_object(self):
        """Test sending a message with TextMessage object."""
        from datetime import datetime

        api = WhatsAppChannelAPI("EAAxxx", "1234567890")
        msg = TextMessage(
            message_id="test_msg_123",
            from_number="1234567890",
            to_number="+9876543210",
            text="Test message",
            timestamp=datetime.now(),
        )
        message_id = await api.send_message("+9876543210", msg)
        assert message_id == "test_msg_123"

    @pytest.mark.asyncio
    async def test_send_message_raises_on_error(self):
        """Test send_message raises exception on error."""
        api = WhatsAppChannelAPI("EAAxxx", "1234567890")

        with patch.object(api, "_simulate_api_call", side_effect=Exception("API error")):
            with pytest.raises(Exception, match="Failed to send message"):
                await api.send_message("+1234567890", "Hello")

    def test_build_message_payload_text(self):
        """Test building payload for text message."""
        from datetime import datetime

        api = WhatsAppChannelAPI("EAAxxx", "1234567890")
        msg = TextMessage(
            message_id="msg_123",
            from_number="1234567890",
            to_number="+9876543210",
            text="Test payload",
            timestamp=datetime.now(),
        )
        payload = api._build_message_payload(msg)
        assert payload["messaging_product"] == "whatsapp"
        assert payload["to"] == "+9876543210"
        assert payload["type"] == "text"
        assert payload["text"] == {"body": "Test payload"}

    @pytest.mark.asyncio
    async def test_receive_message_with_valid_text_message(self):
        """Test receiving a valid text message."""
        api = WhatsAppChannelAPI("EAAxxx", "1234567890")

        message_data = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "wamid.123",
                                        "from": "+9876543210",
                                        "timestamp": "1700000000",
                                        "type": "text",
                                        "text": {"body": "Hello there"},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        result = await api.receive_message(message_data)
        assert result is not None
        assert result.message_id == "wamid.123"
        assert result.from_number == "+9876543210"
        assert result.text == "Hello there"

    @pytest.mark.asyncio
    async def test_receive_message_with_no_messages(self):
        """Test receiving message data with no messages."""
        api = WhatsAppChannelAPI("EAAxxx", "1234567890")

        message_data = {"entry": [{"changes": [{"value": {"messages": []}}]}]}

        result = await api.receive_message(message_data)
        assert result is None

    @pytest.mark.asyncio
    async def test_receive_message_with_non_text_type(self):
        """Test receiving non-text message type."""
        api = WhatsAppChannelAPI("EAAxxx", "1234567890")

        message_data = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "wamid.123",
                                        "from": "+9876543210",
                                        "timestamp": "1700000000",
                                        "type": "image",
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        result = await api.receive_message(message_data)
        assert result is None  # Non-text types not yet supported

    @pytest.mark.asyncio
    async def test_receive_message_with_invalid_data(self):
        """Test receiving invalid message data returns None."""
        api = WhatsAppChannelAPI("EAAxxx", "1234567890")

        result = await api.receive_message({})
        assert result is None

    @pytest.mark.asyncio
    async def test_get_message_status_when_sending(self):
        """Test getting status of a message that's still sending."""
        api = WhatsAppChannelAPI("EAAxxx", "1234567890")
        status = await api.get_message_status("unknown_msg")
        assert status == WhatsAppMessageStatus.SENDING

    @pytest.mark.asyncio
    async def test_get_message_status_when_sent(self):
        """Test getting status of a sent message."""
        api = WhatsAppChannelAPI("EAAxxx", "1234567890")

        # Create a future and add to queue
        future = asyncio.Future()
        future.set_result(WhatsAppMessageStatus.SENT)
        api.message_queue["msg_123"] = future

        status = await api.get_message_status("msg_123")
        assert status == WhatsAppMessageStatus.SENT

    @pytest.mark.asyncio
    async def test_simulate_api_call(self):
        """Test API call simulation."""
        api = WhatsAppChannelAPI("EAAxxx", "1234567890")
        await api._simulate_api_call({})
        # Should complete without error

    @pytest.mark.asyncio
    async def test_track_message_status(self):
        """Test tracking message status over time."""
        api = WhatsAppChannelAPI("EAAxxx", "1234567890")

        future = asyncio.Future()
        api.message_queue["test_msg"] = future

        # Start tracking in background
        task = asyncio.create_task(api._track_message_status("test_msg", future))

        # Wait a bit for the first status update
        await asyncio.sleep(1.5)

        # Future should be done with SENT status
        assert future.done()
        assert future.result() == WhatsAppMessageStatus.SENT

        # Wait for cleanup
        await task

        # Message should be removed from queue after delay
        assert "test_msg" not in api.message_queue

    @pytest.mark.asyncio
    async def test_track_message_status_with_error(self):
        """Test tracking message status when an error occurs."""
        api = WhatsAppChannelAPI("EAAxxx", "1234567890")

        future = asyncio.Future()
        api.message_queue["test_msg"] = future

        # Simulate error in tracking by mocking sleep
        with patch("agntrick_whatsapp.channel_api.asyncio.sleep", side_effect=Exception("Network error")):
            await api._track_message_status("test_msg", future)

        # Future should have exception
        assert future.done()
        with pytest.raises(Exception, match="Network error"):
            future.result()
