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


# ---------------------------------------------------------------------------
# _extract_text()
# ---------------------------------------------------------------------------


def test_extract_text_conversation(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_extract_text returns plain conversation text."""
    msg = MagicMock()
    msg.HasField.side_effect = lambda f: f == "conversation"
    msg.conversation = "Hello world"
    event = MagicMock(Message=msg)
    assert channel._extract_text(event) == "Hello world"


def test_extract_text_extended(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_extract_text returns extendedTextMessage.text when conversation is absent."""
    msg = MagicMock()
    msg.HasField.side_effect = lambda f: f == "extendedTextMessage"
    msg.extendedTextMessage.text = "Extended text"
    event = MagicMock(Message=msg)
    assert channel._extract_text(event) == "Extended text"


def test_extract_text_no_text(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_extract_text returns None for non-text messages (image, video, etc.)."""
    msg = MagicMock()
    msg.HasField.return_value = False
    event = MagicMock(Message=msg)
    assert channel._extract_text(event) is None


def test_extract_text_no_message(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_extract_text returns None when event has no Message attribute."""
    event = MagicMock(spec=[])
    assert channel._extract_text(event) is None


# ---------------------------------------------------------------------------
# _extract_sender_jid()
# ---------------------------------------------------------------------------


def test_extract_sender_jid_from_sender(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_extract_sender_jid returns Sender JID for direct messages."""
    sender = MagicMock(User="34666666666", Server="s.whatsapp.net")
    chat = MagicMock(User="34666666666", Server="s.whatsapp.net")
    source = MagicMock(Sender=sender, Chat=chat)
    info = MagicMock(MessageSource=source)
    event = MagicMock(Info=info)
    assert channel._extract_sender_jid(event) == "34666666666@s.whatsapp.net"


def test_extract_sender_jid_fallback_to_chat(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_extract_sender_jid falls back to Chat JID when Sender is empty."""
    sender = MagicMock(User="", Server="")
    chat = MagicMock(User="34999999999", Server="s.whatsapp.net")
    source = MagicMock(Sender=sender, Chat=chat)
    info = MagicMock(MessageSource=source)
    event = MagicMock(Info=info)
    assert channel._extract_sender_jid(event) == "34999999999@s.whatsapp.net"


def test_extract_sender_jid_unknown(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_extract_sender_jid returns 'unknown' when no Info present."""
    event = MagicMock(spec=[])
    assert channel._extract_sender_jid(event) == "unknown"


# ---------------------------------------------------------------------------
# _on_message_event()
# ---------------------------------------------------------------------------


def test_on_message_event_processes_own_messages(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """Messages from our own account (IsFromMe=True) bypass the contact filter.

    The user runs neonize on their own WhatsApp — messages they type on
    their phone arrive with IsFromMe=True via multi-device sync.  In LID
    addressing mode the Sender JID is a Linked ID that cannot be matched
    to the allowed phone number, so IsFromMe is the authoritative signal.
    """
    callback = AsyncMock()
    channel._message_callback = callback
    loop = asyncio.new_event_loop()
    channel._loop = loop

    # Sender is a LID — does NOT match the allowed_contact phone number.
    # IsFromMe=True signals that this is the account owner's message.
    sender = MagicMock(User="118657162162293", Server="lid")
    source = MagicMock(IsFromMe=True, Sender=sender, Chat=sender)
    info = MagicMock(MessageSource=source, Timestamp=100, Pushname="Me")
    msg = MagicMock()
    msg.HasField.side_effect = lambda f: f == "conversation"
    msg.conversation = "Hello"
    event = MagicMock(Info=info, Message=msg)

    with patch("agntrick_whatsapp.channel_bridge.asyncio.run_coroutine_threadsafe") as mock_schedule:
        channel._on_message_event(MagicMock(), event)
        mock_schedule.assert_called_once()

    loop.close()


def test_on_message_event_filters_contact(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """Messages from non-allowed contacts are filtered out."""
    callback = AsyncMock()
    channel._message_callback = callback
    channel._loop = MagicMock()

    # Neither Sender nor Chat matches the allowed contact
    sender = MagicMock(User="11111111111", Server="s.whatsapp.net")
    chat = MagicMock(User="11111111111", Server="s.whatsapp.net")
    source = MagicMock(IsFromMe=False, Sender=sender, Chat=chat, spec=["IsFromMe", "Sender", "Chat"])
    info = MagicMock(MessageSource=source, Timestamp=0, Pushname="Other")
    msg = MagicMock()
    msg.HasField.side_effect = lambda f: f == "conversation"
    msg.conversation = "Hi"
    event = MagicMock(Info=info, Message=msg)

    channel._on_message_event(MagicMock(), event)
    # Should not have scheduled anything on the loop
    assert not channel._loop.call_soon_threadsafe.called
    # run_coroutine_threadsafe should not have been called either
    assert callback.call_count == 0


def test_on_message_event_dispatches_allowed_contact(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """Messages from the allowed contact are dispatched to the callback."""
    callback = AsyncMock()
    channel._message_callback = callback
    loop = asyncio.new_event_loop()
    channel._loop = loop

    # Sender matches allowed contact (34666666666)
    sender = MagicMock(User="34666666666", Server="s.whatsapp.net")
    source = MagicMock(IsFromMe=False, Sender=sender, Chat=sender)
    info = MagicMock(MessageSource=source, Timestamp=1234567890, Pushname="Jean")
    msg = MagicMock()
    msg.HasField.side_effect = lambda f: f == "conversation"
    msg.conversation = "Hello bot"
    event = MagicMock(Info=info, Message=msg)

    with patch("agntrick_whatsapp.channel_bridge.asyncio.run_coroutine_threadsafe") as mock_schedule:
        channel._on_message_event(MagicMock(), event)
        mock_schedule.assert_called_once()
        # Verify the coroutine was scheduled on the correct loop
        assert mock_schedule.call_args[0][1] is loop

    loop.close()


def test_on_message_event_lid_sender_without_is_from_me_is_filtered(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """A LID sender without IsFromMe is filtered when no candidate matches.

    In full LID addressing mode all JIDs are Linked IDs.  If IsFromMe is
    False (message from another person) and no candidate phone number
    matches allowed_contact, the message must be filtered out.
    """
    callback = AsyncMock()
    channel._message_callback = callback
    channel._loop = MagicMock()

    sender = MagicMock(User="999999999999", Server="lid")
    chat = MagicMock(User="999999999999", Server="lid")
    source = MagicMock(IsFromMe=False, Sender=sender, Chat=chat)
    info = MagicMock(MessageSource=source, Timestamp=100, Pushname="Stranger")
    msg = MagicMock()
    msg.HasField.side_effect = lambda f: f == "conversation"
    msg.conversation = "/ollama hello"
    event = MagicMock(Info=info, Message=msg)

    channel._on_message_event(MagicMock(), event)
    assert callback.call_count == 0


def test_collect_candidate_numbers(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_collect_candidate_numbers gathers numbers from Sender, SenderAlt, Chat."""
    sender = MagicMock(User="118657162162293", Server="lid")
    sender_alt = MagicMock(User="34666666666", Server="s.whatsapp.net")
    chat = MagicMock(User="34666666666", Server="s.whatsapp.net")
    source = MagicMock(Sender=sender, SenderAlt=sender_alt, Chat=chat)
    info = MagicMock(MessageSource=source)
    event = MagicMock(Info=info)

    candidates = channel._collect_candidate_numbers(event)
    assert "34666666666" in candidates
    assert "118657162162293" in candidates


def test_extract_server_whatsapp_net(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_extract_server returns s.whatsapp.net for phone-based JIDs."""
    assert channel._extract_server("34666666666@s.whatsapp.net") == "s.whatsapp.net"


def test_extract_server_lid(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_extract_server returns lid for LID-based JIDs."""
    assert channel._extract_server("118657162162293@lid") == "lid"


def test_extract_server_bare_number(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_extract_server defaults to s.whatsapp.net for bare phone numbers."""
    assert channel._extract_server("34666666666") == "s.whatsapp.net"


@pytest.mark.asyncio
async def test_send_message_preserves_lid_server(tmp_path: Path) -> None:
    """send_message() must use the lid server when recipient is a LID JID."""
    import agntrick_whatsapp.channel_bridge as bridge_mod
    from agntrick_whatsapp.channel_bridge import WhatsAppChannel

    mock_client = MagicMock()
    mock_client.event.return_value = lambda fn: fn

    with patch("agntrick_whatsapp.channel_bridge.NewClient", return_value=mock_client):
        ch = WhatsAppChannel(storage_path=tmp_path, allowed_contact="+34666666666")
        ch._client = mock_client

    built_jids: list = []

    def capture_build_jid(user: str, server: str = "s.whatsapp.net") -> MagicMock:
        built_jids.append((user, server))
        return MagicMock()

    with patch.object(bridge_mod, "build_jid", create=True, side_effect=capture_build_jid):
        loop = asyncio.get_event_loop()
        with patch.object(loop, "run_in_executor", new_callable=AsyncMock):
            await ch.send_message("118657162162293@lid", "Hello LID")

    assert built_jids == [("118657162162293", "lid")]


@pytest.mark.asyncio
async def test_send_message_defaults_to_whatsapp_net(tmp_path: Path) -> None:
    """send_message() uses s.whatsapp.net for bare phone numbers."""
    import agntrick_whatsapp.channel_bridge as bridge_mod
    from agntrick_whatsapp.channel_bridge import WhatsAppChannel

    mock_client = MagicMock()
    mock_client.event.return_value = lambda fn: fn

    with patch("agntrick_whatsapp.channel_bridge.NewClient", return_value=mock_client):
        ch = WhatsAppChannel(storage_path=tmp_path, allowed_contact="+34666666666")
        ch._client = mock_client

    built_jids: list = []

    def capture_build_jid(user: str, server: str = "s.whatsapp.net") -> MagicMock:
        built_jids.append((user, server))
        return MagicMock()

    with patch.object(bridge_mod, "build_jid", create=True, side_effect=capture_build_jid):
        loop = asyncio.get_event_loop()
        with patch.object(loop, "run_in_executor", new_callable=AsyncMock):
            await ch.send_message("+34666666666", "Hello PN")

    assert built_jids == [("34666666666", "s.whatsapp.net")]


def test_on_message_event_skips_non_text(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """Non-text messages (images, etc.) are skipped."""
    channel._message_callback = AsyncMock()
    channel._loop = MagicMock()

    source = MagicMock(IsFromMe=False)
    info = MagicMock(MessageSource=source)
    msg = MagicMock()
    msg.HasField.return_value = False
    event = MagicMock(Info=info, Message=msg)

    channel._on_message_event(MagicMock(), event)
    assert not channel._loop.call_soon_threadsafe.called


# ---------------------------------------------------------------------------
# shutdown()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shutdown_does_not_change_cwd(tmp_path: Path) -> None:
    """shutdown() must not change the process CWD."""
    from agntrick_whatsapp.channel_bridge import WhatsAppChannel

    original_cwd = Path.cwd()

    with patch("agntrick_whatsapp.channel_bridge.NewClient"):
        ch = WhatsAppChannel(storage_path=tmp_path, allowed_contact="+34666666666")

    await ch.shutdown()

    assert Path.cwd() == original_cwd, "shutdown() must not change the process CWD"
