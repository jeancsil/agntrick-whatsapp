"""Tests for WhatsApp channel bridge (channel_bridge.py).

All neonize interactions are mocked so these tests run without system packages.
"""

import asyncio
import os
import threading
import time
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


def test_on_message_event_processes_self_chat(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """Self-chat messages (IsFromMe=True, Chat==Sender) are processed."""
    callback = AsyncMock()
    channel._message_callback = callback
    loop = asyncio.new_event_loop()
    channel._loop = loop

    sender = MagicMock(User="118657162162293", Server="lid")
    source = MagicMock(IsFromMe=True, IsGroup=False, Sender=sender, Chat=sender)
    info = MagicMock(MessageSource=source, Timestamp=100, Pushname="Me")
    msg = MagicMock()
    msg.HasField.side_effect = lambda f: f == "conversation"
    msg.conversation = "Hello"
    event = MagicMock(Info=info, Message=msg)

    with patch("agntrick_whatsapp.channel_bridge.asyncio.run_coroutine_threadsafe") as mock_schedule:
        channel._on_message_event(MagicMock(), event)
        mock_schedule.assert_called_once()

    loop.close()


def test_on_message_event_ignores_outgoing_dm(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """Outgoing DMs (IsFromMe=True, Chat!=Sender) must be ignored."""
    callback = AsyncMock()
    channel._message_callback = callback
    channel._loop = MagicMock()

    sender = MagicMock(User="118657162162293", Server="lid")
    other_person = MagicMock(User="999888777666", Server="s.whatsapp.net")
    source = MagicMock(IsFromMe=True, IsGroup=False, Sender=sender, Chat=other_person)
    info = MagicMock(MessageSource=source, Timestamp=100, Pushname="Me")
    msg = MagicMock()
    msg.HasField.side_effect = lambda f: f == "conversation"
    msg.conversation = "Hey friend"
    event = MagicMock(Info=info, Message=msg)

    channel._on_message_event(MagicMock(), event)
    assert callback.call_count == 0


def test_on_message_event_ignores_group_messages(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """Group messages (IsGroup=True) must be ignored regardless of IsFromMe."""
    callback = AsyncMock()
    channel._message_callback = callback
    channel._loop = MagicMock()

    sender = MagicMock(User="118657162162293", Server="lid")
    group = MagicMock(User="120363000000000000", Server="g.us")
    source = MagicMock(IsFromMe=True, IsGroup=True, Sender=sender, Chat=group)
    info = MagicMock(MessageSource=source, Timestamp=100, Pushname="Me")
    msg = MagicMock()
    msg.HasField.side_effect = lambda f: f == "conversation"
    msg.conversation = "Hello group"
    event = MagicMock(Info=info, Message=msg)

    channel._on_message_event(MagicMock(), event)
    assert callback.call_count == 0


def test_on_message_event_filters_contact(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """Messages from non-allowed contacts are filtered out."""
    callback = AsyncMock()
    channel._message_callback = callback
    channel._loop = MagicMock()

    # Neither Sender nor Chat matches the allowed contact
    sender = MagicMock(User="11111111111", Server="s.whatsapp.net")
    chat = MagicMock(User="11111111111", Server="s.whatsapp.net")
    source = MagicMock(
        IsFromMe=False,
        IsGroup=False,
        Sender=sender,
        Chat=chat,
        spec=["IsFromMe", "IsGroup", "Sender", "Chat"],
    )
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
    source = MagicMock(IsFromMe=False, IsGroup=False, Sender=sender, Chat=sender)
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
    source = MagicMock(IsFromMe=False, IsGroup=False, Sender=sender, Chat=chat)
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


# ---------------------------------------------------------------------------
# _send_typing()
# ---------------------------------------------------------------------------


def test_send_typing_sends_indicator(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_send_typing sends typing indicator when client is available."""
    import agntrick_whatsapp.channel_bridge as bridge_mod

    mock_client = MagicMock()
    channel._client = mock_client
    channel.typing_indicators = True

    mock_jid = MagicMock()
    with patch.object(bridge_mod, "build_jid", create=True, return_value=mock_jid):
        with patch.object(bridge_mod, "ChatPresence", create=True, CHAT_PRESENCE_COMPOSING="composing"):
            with patch.object(bridge_mod, "ChatPresenceMedia", create=True, CHAT_PRESENCE_MEDIA_TEXT="text"):
                channel._send_typing("34666666666@s.whatsapp.net")

    mock_client.send_chat_presence.assert_called_once()
    assert "34666666666@s.whatsapp.net" in channel._typing_jids


def test_send_typing_skips_when_disabled(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_send_typing does nothing when typing_indicators is False."""
    channel._client = MagicMock()
    channel.typing_indicators = False

    channel._send_typing("34666666666@s.whatsapp.net")

    assert len(channel._typing_jids) == 0


def test_send_typing_skips_when_no_client(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_send_typing does nothing when client is None."""
    channel._client = None
    channel.typing_indicators = True

    channel._send_typing("34666666666@s.whatsapp.net")

    assert len(channel._typing_jids) == 0


def test_send_typing_handles_exception(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_send_typing logs warning but does not raise on exception."""
    import agntrick_whatsapp.channel_bridge as bridge_mod

    mock_client = MagicMock()
    mock_client.send_chat_presence.side_effect = RuntimeError("Failed to send")
    channel._client = mock_client
    channel.typing_indicators = True

    mock_jid = MagicMock()
    with patch.object(bridge_mod, "build_jid", create=True, return_value=mock_jid):
        with patch.object(bridge_mod, "ChatPresence", create=True, CHAT_PRESENCE_COMPOSING="composing"):
            with patch.object(bridge_mod, "ChatPresenceMedia", create=True, CHAT_PRESENCE_MEDIA_TEXT="text"):
                # Should not raise
                channel._send_typing("34666666666@s.whatsapp.net")

    # JID should not be added since it failed
    assert "34666666666@s.whatsapp.net" not in channel._typing_jids


# ---------------------------------------------------------------------------
# _stop_typing()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_typing_sends_paused(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_stop_typing sends paused indicator when typing was active."""
    import agntrick_whatsapp.channel_bridge as bridge_mod

    mock_client = MagicMock()
    channel._client = mock_client
    channel.typing_indicators = True
    jid = "34666666666@s.whatsapp.net"
    channel._typing_jids.add(jid)
    channel._typing_start_times[jid] = time.time() - 5  # Started 5 seconds ago

    mock_jid = MagicMock()
    with patch.object(bridge_mod, "build_jid", create=True, return_value=mock_jid):
        with patch.object(bridge_mod, "ChatPresence", create=True, CHAT_PRESENCE_PAUSED="paused"):
            with patch.object(bridge_mod, "ChatPresenceMedia", create=True, CHAT_PRESENCE_MEDIA_TEXT="text"):
                await channel._stop_typing(jid)

    mock_client.send_chat_presence.assert_called_once()
    assert jid not in channel._typing_jids


@pytest.mark.asyncio
async def test_stop_typing_waits_for_min_duration(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_stop_typing waits for min_typing_duration before sending paused."""
    import agntrick_whatsapp.channel_bridge as bridge_mod

    mock_client = MagicMock()
    channel._client = mock_client
    channel.typing_indicators = True
    channel._min_typing_duration = 0.1  # Short duration for test
    jid = "34666666666@s.whatsapp.net"
    channel._typing_jids.add(jid)
    channel._typing_start_times[jid] = time.time()  # Just started

    mock_jid = MagicMock()
    with patch.object(bridge_mod, "build_jid", create=True, return_value=mock_jid):
        with patch.object(bridge_mod, "ChatPresence", create=True, CHAT_PRESENCE_PAUSED="paused"):
            with patch.object(bridge_mod, "ChatPresenceMedia", create=True, CHAT_PRESENCE_MEDIA_TEXT="text"):
                start = time.time()
                await channel._stop_typing(jid)
                elapsed = time.time() - start

    # Should have waited for min duration
    assert elapsed >= 0.1


@pytest.mark.asyncio
async def test_stop_typing_skips_when_not_in_jids(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_stop_typing does nothing when JID not in _typing_jids."""
    channel._client = MagicMock()
    channel.typing_indicators = True

    await channel._stop_typing("34666666666@s.whatsapp.net")

    channel._client.send_chat_presence.assert_not_called()


@pytest.mark.asyncio
async def test_stop_typing_handles_exception(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_stop_typing logs warning but does not raise on exception."""
    import agntrick_whatsapp.channel_bridge as bridge_mod

    mock_client = MagicMock()
    mock_client.send_chat_presence.side_effect = RuntimeError("Failed to stop")
    channel._client = mock_client
    channel.typing_indicators = True
    jid = "34666666666@s.whatsapp.net"
    channel._typing_jids.add(jid)
    channel._typing_start_times[jid] = time.time() - 5

    mock_jid = MagicMock()
    with patch.object(bridge_mod, "build_jid", create=True, return_value=mock_jid):
        with patch.object(bridge_mod, "ChatPresence", create=True, CHAT_PRESENCE_PAUSED="paused"):
            with patch.object(bridge_mod, "ChatPresenceMedia", create=True, CHAT_PRESENCE_MEDIA_TEXT="text"):
                # Should not raise
                await channel._stop_typing(jid)


# ---------------------------------------------------------------------------
# _on_message_event() - stop_event guard
# ---------------------------------------------------------------------------


def test_on_message_event_skips_when_stop_event_set(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_on_message_event skips processing when stop_event is set."""
    callback = AsyncMock()
    channel._message_callback = callback
    channel._loop = asyncio.new_event_loop()
    channel._stop_event.set()

    sender = MagicMock(User="34666666666", Server="s.whatsapp.net")
    source = MagicMock(IsFromMe=False, IsGroup=False, Sender=sender, Chat=sender)
    info = MagicMock(MessageSource=source, Timestamp=100, Pushname="Test")
    msg = MagicMock()
    msg.HasField.side_effect = lambda f: f == "conversation"
    msg.conversation = "Hello"
    event = MagicMock(Info=info, Message=msg)

    channel._on_message_event(MagicMock(), event)

    # Callback should not have been scheduled
    assert callback.call_count == 0
    channel._loop.close()


# ---------------------------------------------------------------------------
# _on_message_event() - no callback/loop
# ---------------------------------------------------------------------------


def test_on_message_event_skips_when_no_callback(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_on_message_event returns early when no callback is set."""
    channel._message_callback = None
    channel._loop = asyncio.new_event_loop()

    event = MagicMock(Info=MagicMock(), Message=MagicMock())

    channel._on_message_event(MagicMock(), event)

    channel._loop.close()


def test_on_message_event_skips_when_no_loop(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_on_message_event returns early when no loop is set."""
    channel._message_callback = AsyncMock()
    channel._loop = None

    event = MagicMock(Info=MagicMock(), Message=MagicMock())

    channel._on_message_event(MagicMock(), event)


# ---------------------------------------------------------------------------
# _collect_candidate_numbers() - edge cases
# ---------------------------------------------------------------------------


def test_collect_candidate_numbers_handles_missing_info(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_collect_candidate_numbers returns empty set when Info is missing."""
    event = MagicMock(spec=[])  # No Info attribute

    candidates = channel._collect_candidate_numbers(event)

    assert candidates == set()


def test_collect_candidate_numbers_handles_missing_source(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_collect_candidate_numbers returns empty set when MessageSource is missing."""
    info = MagicMock(spec=["MessageSource"])
    info.MessageSource = None
    event = MagicMock(Info=info)

    candidates = channel._collect_candidate_numbers(event)

    assert candidates == set()


def test_collect_candidate_numbers_handles_exception(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_collect_candidate_numbers returns empty set on exception."""

    # Create an event where accessing Info raises an exception
    class BrokenEvent:
        @property
        def Info(self) -> None:  # type: ignore[override]
            raise RuntimeError("broken")

    event = BrokenEvent()

    # Should not raise, returns empty set
    candidates = channel._collect_candidate_numbers(event)

    assert isinstance(candidates, set)


# ---------------------------------------------------------------------------
# _extract_sender_jid() - exception handling
# ---------------------------------------------------------------------------


def test_extract_sender_jid_handles_exception(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_extract_sender_jid returns 'unknown' on exception."""

    # Create an event where accessing Info raises an exception
    class BrokenEvent:
        @property
        def Info(self) -> None:  # type: ignore[override]
            raise RuntimeError("broken")

    event = BrokenEvent()

    result = channel._extract_sender_jid(event)

    assert result == "unknown"


# ---------------------------------------------------------------------------
# _extract_text() - exception handling
# ---------------------------------------------------------------------------


def test_extract_text_handles_exception(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_extract_text returns None on exception."""

    # Create an event where accessing Message raises an exception
    class BrokenEvent:
        @property
        def Message(self) -> None:  # type: ignore[override]
            raise RuntimeError("broken")

    event = BrokenEvent()

    result = channel._extract_text(event)

    assert result is None


def test_extract_text_handles_value_error_on_has_field(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_extract_text handles ValueError from HasField and still returns text."""
    msg = MagicMock()
    # HasField raises ValueError, but conversation attr exists
    msg.HasField.side_effect = ValueError("no such field")
    msg.conversation = "Fallback text"
    event = MagicMock(Message=msg)

    result = channel._extract_text(event)

    assert result == "Fallback text"


def test_extract_text_extended_text_fallback(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_extract_text handles ValueError for extendedTextMessage with fallback."""
    msg = MagicMock()
    msg.HasField.side_effect = lambda f: f == "extendedTextMessage"
    msg.extendedTextMessage = MagicMock()
    msg.extendedTextMessage.text = ""
    # Make extendedTextMessage.text return empty, then use fallback
    event = MagicMock(Message=msg)

    result = channel._extract_text(event)

    # Should return None since text is empty
    assert result is None


# ---------------------------------------------------------------------------
# _restore_working_directory()
# ---------------------------------------------------------------------------


def test_restore_working_directory(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_restore_working_directory restores original directory when changed."""
    original = Path.cwd()
    channel._original_dir = original

    # Method should work even if CWD hasn't changed
    channel._restore_working_directory()

    assert Path.cwd() == original


# ---------------------------------------------------------------------------
# _close_deduplication_db()
# ---------------------------------------------------------------------------


def test_close_deduplication_db(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_close_deduplication_db closes and removes _db attribute."""
    mock_db = MagicMock()
    channel._db = mock_db

    channel._close_deduplication_db()

    mock_db.close.assert_called_once()
    assert not hasattr(channel, "_db")


def test_close_deduplication_db_when_no_db(channel: "WhatsAppChannel") -> None:  # type: ignore[name-defined]
    """_close_deduplication_db does nothing when _db doesn't exist."""
    # Should not raise
    channel._close_deduplication_db()


# ---------------------------------------------------------------------------
# ConfigurationError and ChannelError
# ---------------------------------------------------------------------------


def test_configuration_error() -> None:
    """ConfigurationError can be raised and caught."""
    from agntrick_whatsapp.channel_bridge import ConfigurationError

    with pytest.raises(ConfigurationError):
        raise ConfigurationError("Test error")


def test_channel_error() -> None:
    """ChannelError can be raised and caught."""
    from agntrick_whatsapp.channel_bridge import ChannelError

    with pytest.raises(ChannelError):
        raise ChannelError("Test error")


# ---------------------------------------------------------------------------
# shutdown() - client disconnect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shutdown_disconnects_client(tmp_path: Path) -> None:
    """shutdown() disconnects the client if it exists."""
    from agntrick_whatsapp.channel_bridge import WhatsAppChannel

    mock_client = MagicMock()
    with patch("agntrick_whatsapp.channel_bridge.NewClient"):
        ch = WhatsAppChannel(storage_path=tmp_path, allowed_contact="+34666666666")
    ch._client = mock_client

    await ch.shutdown()

    mock_client.disconnect.assert_called_once()
    assert ch._client is None


@pytest.mark.asyncio
async def test_shutdown_handles_disconnect_error(tmp_path: Path) -> None:
    """shutdown() handles errors during client disconnect."""
    from agntrick_whatsapp.channel_bridge import WhatsAppChannel

    mock_client = MagicMock()
    mock_client.disconnect.side_effect = RuntimeError("Disconnect failed")
    with patch("agntrick_whatsapp.channel_bridge.NewClient"):
        ch = WhatsAppChannel(storage_path=tmp_path, allowed_contact="+34666666666")
    ch._client = mock_client

    # Should not raise
    await ch.shutdown()

    assert ch._client is None


@pytest.mark.asyncio
async def test_shutdown_waits_for_thread(tmp_path: Path) -> None:
    """shutdown() waits for worker thread with timeout when thread is alive."""
    from agntrick_whatsapp.channel_bridge import WhatsAppChannel

    mock_client = MagicMock()
    mock_client.disconnect = MagicMock()  # Non-blocking disconnect
    with patch("agntrick_whatsapp.channel_bridge.NewClient"):
        ch = WhatsAppChannel(storage_path=tmp_path, allowed_contact="+34666666666")

    ch._client = mock_client
    mock_thread = MagicMock()
    mock_thread.is_alive.return_value = True  # Thread is alive, so join should be called
    ch._thread = mock_thread

    await ch.shutdown()

    mock_thread.join.assert_called_once()


# ---------------------------------------------------------------------------
# send() - error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_raises_when_not_initialized(tmp_path: Path) -> None:
    """send() raises ChannelError when client is None."""
    from agntrick_whatsapp.channel_bridge import ChannelError, WhatsAppChannel

    with patch("agntrick_whatsapp.channel_bridge.NewClient"):
        ch = WhatsAppChannel(storage_path=tmp_path, allowed_contact="+34666666666")

    ch._client = None
    msg = MagicMock()
    msg.recipient_id = "+34666666666"
    msg.text = "Hello"

    with pytest.raises(ChannelError, match="Channel not initialized"):
        await ch.send(msg)


# ---------------------------------------------------------------------------
# listen() - error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_listen_raises_when_not_initialized(tmp_path: Path) -> None:
    """listen() raises ChannelError when client is None."""
    from agntrick_whatsapp.channel_bridge import ChannelError, WhatsAppChannel

    with patch("agntrick_whatsapp.channel_bridge.NewClient"):
        ch = WhatsAppChannel(storage_path=tmp_path, allowed_contact="+34666666666")

    ch._client = None

    with pytest.raises(ChannelError, match="Channel not initialized"):
        await ch.listen(AsyncMock())


@pytest.mark.asyncio
async def test_listen_warns_when_already_listening(tmp_path: Path) -> None:
    """listen() warns and returns when already listening."""
    from agntrick_whatsapp.channel_bridge import WhatsAppChannel

    mock_client = MagicMock()
    mock_client.event.return_value = lambda fn: fn
    with patch("agntrick_whatsapp.channel_bridge.NewClient", return_value=mock_client):
        ch = WhatsAppChannel(storage_path=tmp_path, allowed_contact="+34666666666")
    ch._client = mock_client
    ch._is_listening = True

    # Should return immediately without error
    await ch.listen(AsyncMock())

    assert ch._is_listening
