"""Tests for WhatsApp channel bridge (channel_bridge.py).

All neonize interactions are mocked so these tests run without system packages.
"""

import asyncio
import os
import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Phone-number normalisation
# ---------------------------------------------------------------------------


def test_normalize_phone_number_strips_spaces() -> None:
    """Phone number with spaces is stripped to digits only."""
    from agntrick_whatsapp.channel_bridge import WhatsAppChannel

    assert WhatsAppChannel._normalize_phone_number("+34 666 666 666") == "34666666666"


def test_normalize_phone_number_strips_jid_domain() -> None:
    """JID domain (@s.whatsapp.net) is removed and digits returned."""
    from agntrick_whatsapp.channel_bridge import WhatsAppChannel

    assert WhatsAppChannel._normalize_phone_number("34666666666@s.whatsapp.net") == "34666666666"


def test_normalize_phone_number_handles_parens() -> None:
    """Parentheses are removed from phone numbers."""
    from agntrick_whatsapp.channel_bridge import WhatsAppChannel

    assert WhatsAppChannel._normalize_phone_number("+1(555)1234567") == "15551234567"


def test_normalize_phone_number_plain_digits() -> None:
    """Plain digit string passes through unchanged."""
    from agntrick_whatsapp.channel_bridge import WhatsAppChannel

    assert WhatsAppChannel._normalize_phone_number("34666666666") == "34666666666"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def channel(tmp_path: Path) -> "WhatsAppChannel":  # type: ignore[name-defined]
    """Create a WhatsAppChannel with neonize client mocked out."""
    from agntrick_whatsapp.channel_bridge import WhatsAppChannel

    with patch("agntrick_whatsapp.channel_bridge.NewClient"):
        ch = WhatsAppChannel(storage_path=tmp_path, allowed_contact="+34666666666")
    return ch


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


def test_channel_init_normalizes_allowed_contact(tmp_path: Path) -> None:
    """Allowed contact should be normalised (spaces and + removed) on init."""
    from agntrick_whatsapp.channel_bridge import WhatsAppChannel

    with patch("agntrick_whatsapp.channel_bridge.NewClient"):
        ch = WhatsAppChannel(storage_path=tmp_path, allowed_contact="+34 666 666 666")
    assert ch.allowed_contact == "34666666666"


def test_channel_init_creates_storage_path(tmp_path: Path) -> None:
    """Storage path (including nested parents) is created on init."""
    from agntrick_whatsapp.channel_bridge import WhatsAppChannel

    nested = tmp_path / "deep" / "nested" / "dir"
    with patch("agntrick_whatsapp.channel_bridge.NewClient"):
        ch = WhatsAppChannel(storage_path=nested, allowed_contact="+34666666666")
    assert ch.storage_path.exists()


def test_channel_init_invalid_storage_path_raises(tmp_path: Path) -> None:
    """ConfigurationError is raised when storage path cannot be created."""
    from agntrick_whatsapp.channel_bridge import ConfigurationError, WhatsAppChannel

    # Point at an existing file so mkdir() will fail
    not_a_dir = tmp_path / "file.txt"
    not_a_dir.write_text("data")

    with patch("agntrick_whatsapp.channel_bridge.NewClient"):
        with pytest.raises(ConfigurationError):
            WhatsAppChannel(storage_path=not_a_dir / "subdir", allowed_contact="+34666666666")


# ---------------------------------------------------------------------------
# Thread-safety: class-level CWD lock
# ---------------------------------------------------------------------------


def test_cwd_lock_is_class_level() -> None:
    """_cwd_lock must be a threading.Lock defined on the class (not per-instance)."""
    from agntrick_whatsapp.channel_bridge import WhatsAppChannel

    assert isinstance(WhatsAppChannel._cwd_lock, type(threading.Lock()))


def test_cwd_lock_shared_between_instances(tmp_path: Path) -> None:
    """Two different channel instances share the same lock object."""
    from agntrick_whatsapp.channel_bridge import WhatsAppChannel

    with patch("agntrick_whatsapp.channel_bridge.NewClient"):
        ch1 = WhatsAppChannel(storage_path=tmp_path / "a", allowed_contact="+34666666666")
        ch2 = WhatsAppChannel(storage_path=tmp_path / "b", allowed_contact="+34666666666")

    assert ch1._cwd_lock is ch2._cwd_lock


# ---------------------------------------------------------------------------
# initialize()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_initialize_does_not_change_cwd(tmp_path: Path) -> None:
    """initialize() must NOT change the process CWD (os.chdir moved to thread)."""
    from agntrick_whatsapp.channel_bridge import WhatsAppChannel

    original_cwd = Path.cwd()

    mock_client = MagicMock()
    mock_client.event.return_value = lambda fn: fn  # decorator noop
    with patch("agntrick_whatsapp.channel_bridge.NewClient", return_value=mock_client):
        ch = WhatsAppChannel(storage_path=tmp_path, allowed_contact="+34666666666")
        with patch.object(ch, "_init_deduplication_db"):
            await ch.initialize()

    assert Path.cwd() == original_cwd, "initialize() must not change the process CWD"


@pytest.mark.asyncio
async def test_initialize_registers_event_handler(tmp_path: Path) -> None:
    """initialize() registers the message event handler on the client."""
    from agntrick_whatsapp.channel_bridge import WhatsAppChannel

    mock_client = MagicMock()
    decorator_fn: list = []

    def capture_event(event_type: object):  # type: ignore[no-untyped-def]
        def register(fn: object) -> object:
            decorator_fn.append(fn)
            return fn

        return register

    mock_client.event.side_effect = capture_event

    with patch("agntrick_whatsapp.channel_bridge.NewClient", return_value=mock_client):
        ch = WhatsAppChannel(storage_path=tmp_path, allowed_contact="+34666666666")
        with patch.object(ch, "_init_deduplication_db"):
            await ch.initialize()

    assert len(decorator_fn) == 1, "Expected exactly one event handler to be registered"


@pytest.mark.asyncio
async def test_initialize_raises_channel_error_on_failure(tmp_path: Path) -> None:
    """ChannelError is raised when NewClient raises during initialization."""
    from agntrick_whatsapp.channel_bridge import ChannelError, WhatsAppChannel

    with patch(
        "agntrick_whatsapp.channel_bridge.NewClient",
        side_effect=RuntimeError("neonize exploded"),
    ):
        ch = WhatsAppChannel.__new__(WhatsAppChannel)
        ch.storage_path = tmp_path
        ch.allowed_contact = "34666666666"
        ch._client = None
        ch._db_lock = threading.Lock()
        ch._db_path = tmp_path / "dedup.db"

        with pytest.raises(ChannelError, match="Failed to initialize neonize client"):
            with patch.object(ch, "_init_deduplication_db"):
                await ch.initialize()


# ---------------------------------------------------------------------------
# send() — media_url guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_text_message_without_media_url_attr(tmp_path: Path) -> None:
    """send() works when message object has no media_url attribute."""
    import agntrick_whatsapp.channel_bridge as bridge_mod
    from agntrick_whatsapp.channel_bridge import WhatsAppChannel

    mock_client = MagicMock()
    mock_client.event.return_value = lambda fn: fn
    mock_jid = "34666@s.whatsapp.net"

    with patch("agntrick_whatsapp.channel_bridge.NewClient", return_value=mock_client):
        ch = WhatsAppChannel(storage_path=tmp_path, allowed_contact="+34666666666")
        ch._client = mock_client

    # Inject build_jid into the module namespace so send() can find it
    # (neonize may not be installed on this system)
    with patch.object(bridge_mod, "build_jid", create=True, return_value=mock_jid):
        # Message object without media_url
        msg = MagicMock(spec=["recipient_id", "text"])
        msg.recipient_id = "+34666666666"
        msg.text = "Hello"

        loop = asyncio.get_event_loop()
        with patch.object(loop, "run_in_executor", new_callable=AsyncMock) as mock_exec:
            await ch.send(msg)

        mock_exec.assert_called_once()


@pytest.mark.asyncio
async def test_send_text_message_with_falsy_media_url(tmp_path: Path) -> None:
    """send() sends text when media_url is falsy (None or empty string)."""
    import agntrick_whatsapp.channel_bridge as bridge_mod
    from agntrick_whatsapp.channel_bridge import WhatsAppChannel

    mock_client = MagicMock()
    mock_client.event.return_value = lambda fn: fn
    mock_jid = "34666@s.whatsapp.net"

    with patch("agntrick_whatsapp.channel_bridge.NewClient", return_value=mock_client):
        ch = WhatsAppChannel(storage_path=tmp_path, allowed_contact="+34666666666")
        ch._client = mock_client

    with patch.object(bridge_mod, "build_jid", create=True, return_value=mock_jid):
        msg = MagicMock()
        msg.recipient_id = "+34666666666"
        msg.text = "Hello"
        msg.media_url = None

        loop = asyncio.get_event_loop()
        with patch.object(loop, "run_in_executor", new_callable=AsyncMock) as mock_exec:
            await ch.send(msg)

        mock_exec.assert_called_once()


# ---------------------------------------------------------------------------
# send_message()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_message_raises_when_not_initialized(tmp_path: Path) -> None:
    """send_message() raises ChannelError when client is None."""
    from agntrick_whatsapp.channel_bridge import ChannelError, WhatsAppChannel

    with patch("agntrick_whatsapp.channel_bridge.NewClient"):
        ch = WhatsAppChannel(storage_path=tmp_path, allowed_contact="+34666666666")

    ch._client = None
    with pytest.raises(ChannelError, match="Channel not initialized"):
        await ch.send_message("+34666666666", "Hello")


@pytest.mark.asyncio
async def test_send_message_calls_client_send(tmp_path: Path) -> None:
    """send_message() calls the underlying client send_message via executor."""
    import agntrick_whatsapp.channel_bridge as bridge_mod
    from agntrick_whatsapp.channel_bridge import WhatsAppChannel

    mock_client = MagicMock()
    mock_client.event.return_value = lambda fn: fn
    mock_jid = "34666@s.whatsapp.net"

    with patch("agntrick_whatsapp.channel_bridge.NewClient", return_value=mock_client):
        ch = WhatsAppChannel(storage_path=tmp_path, allowed_contact="+34666666666")
        ch._client = mock_client

    with patch.object(bridge_mod, "build_jid", create=True, return_value=mock_jid):
        loop = asyncio.get_event_loop()
        with patch.object(loop, "run_in_executor", new_callable=AsyncMock) as mock_exec:
            await ch.send_message("+34666666666", "Test message")

        mock_exec.assert_called_once()


# ---------------------------------------------------------------------------
# shutdown()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shutdown_clears_listening_state(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """shutdown() sets _is_listening to False."""
    channel._is_listening = True
    await channel.shutdown()
    assert not channel._is_listening


@pytest.mark.asyncio
async def test_shutdown_sets_stop_event(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """shutdown() signals the stop event so the background thread can exit."""
    await channel.shutdown()
    assert channel._stop_event.is_set()


@pytest.mark.asyncio
async def test_shutdown_does_not_change_cwd(tmp_path: Path) -> None:
    """shutdown() must not change the process CWD."""
    from agntrick_whatsapp.channel_bridge import WhatsAppChannel

    original_cwd = Path.cwd()

    with patch("agntrick_whatsapp.channel_bridge.NewClient"):
        ch = WhatsAppChannel(storage_path=tmp_path, allowed_contact="+34666666666")

    await ch.shutdown()

    assert Path.cwd() == original_cwd, "shutdown() must not change the process CWD"
