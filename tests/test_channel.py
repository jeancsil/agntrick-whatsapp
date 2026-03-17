"""Tests for WhatsApp channel strategy selection and delegation."""

from unittest.mock import AsyncMock, patch

import pytest

from agntrick_whatsapp.channel import WhatsAppChannel


class TestWhatsAppChannelInit:
    """Test cases for WhatsAppChannel initialization."""

    def test_channel_requires_at_least_one_config(self) -> None:
        """Channel raises ValueError if no config provided."""
        with pytest.raises(ValueError, match="At least one set"):
            WhatsAppChannel()

    def test_channel_business_api_mode(self) -> None:
        """Channel selects business API mode when access_token + phone_number_id provided."""
        ch = WhatsAppChannel(access_token="EAtest", phone_number_id="123")
        assert ch._mode == "business_api"

    def test_channel_bridge_mode_without_neonize_raises(self) -> None:
        """Channel raises RuntimeError for bridge mode when neonize is unavailable."""
        # channel_bridge's NewClient fallback raises RuntimeError
        # depending on environment, this may or may not be available
        # We patch _BRIDGE_AVAILABLE to False to test the error path
        with patch("agntrick_whatsapp.channel._BRIDGE_AVAILABLE", False):
            with pytest.raises(RuntimeError, match="Bridge mode requested"):
                WhatsAppChannel(storage_path="/tmp/test_wa")

    def test_channel_bridge_mode_with_neonize(self) -> None:
        """Channel selects bridge mode when storage_path provided and neonize available."""
        with patch("agntrick_whatsapp.channel._BRIDGE_AVAILABLE", True):
            mock_bridge_channel = AsyncMock()
            with patch("agntrick_whatsapp.channel.bridge_impl") as mock_bridge:
                mock_bridge.WhatsAppChannel.return_value = mock_bridge_channel
                ch = WhatsAppChannel(storage_path="/tmp/test_wa_bridge")
                assert ch._mode == "bridge"

    def test_channel_business_api_has_strategy(self) -> None:
        """Business API channel has an internal strategy object."""
        ch = WhatsAppChannel(access_token="EAtest", phone_number_id="123")
        assert ch._strategy is not None


@pytest.mark.asyncio
class TestWhatsAppChannelDelegation:
    """Test that WhatsAppChannel delegates all methods to its strategy."""

    @pytest.fixture
    def api_channel(self) -> WhatsAppChannel:
        """Create a business API channel for testing."""
        return WhatsAppChannel(access_token="EAtest", phone_number_id="123")

    async def test_initialize_delegates(self, api_channel: WhatsAppChannel) -> None:
        """Channel.initialize() delegates to strategy.initialize()."""
        api_channel._strategy.initialize = AsyncMock()  # type: ignore[method-assign]
        await api_channel.initialize()
        api_channel._strategy.initialize.assert_called_once()

    async def test_shutdown_delegates(self, api_channel: WhatsAppChannel) -> None:
        """Channel.shutdown() delegates to strategy.shutdown()."""
        api_channel._strategy.shutdown = AsyncMock()  # type: ignore[method-assign]
        await api_channel.shutdown()
        api_channel._strategy.shutdown.assert_called_once()

    async def test_listen_delegates(self, api_channel: WhatsAppChannel) -> None:
        """Channel.listen() delegates to strategy.listen()."""
        callback = AsyncMock()
        api_channel._strategy.listen = AsyncMock()  # type: ignore[method-assign]
        await api_channel.listen(callback)
        api_channel._strategy.listen.assert_called_once_with(callback)

    async def test_send_message_delegates(self, api_channel: WhatsAppChannel) -> None:
        """Channel.send_message() delegates to strategy.send_message()."""
        api_channel._strategy.send_message = AsyncMock(return_value="msg_id")  # type: ignore[method-assign]
        result = await api_channel.send_message("+1234567890", "hello")
        assert result == "msg_id"
        api_channel._strategy.send_message.assert_called_once_with("+1234567890", "hello")

    async def test_receive_message_delegates(self, api_channel: WhatsAppChannel) -> None:
        """Channel.receive_message() delegates to strategy.receive_message()."""
        api_channel._strategy.receive_message = AsyncMock(return_value=None)  # type: ignore[method-assign]
        result = await api_channel.receive_message({})
        assert result is None
        api_channel._strategy.receive_message.assert_called_once_with({})

    async def test_get_message_status_delegates(self, api_channel: WhatsAppChannel) -> None:
        """Channel.get_message_status() delegates to strategy.get_message_status()."""
        api_channel._strategy.get_message_status = AsyncMock(return_value=None)  # type: ignore[method-assign]
        result = await api_channel.get_message_status("msg_123")
        assert result is None
        api_channel._strategy.get_message_status.assert_called_once_with("msg_123")
