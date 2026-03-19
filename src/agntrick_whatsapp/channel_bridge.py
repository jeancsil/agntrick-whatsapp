"""WhatsApp channel implementation using neonize library (Bridge/QR Code version).

This module provides WhatsApp communication capabilities for agents using
the neonize library, which provides a Python API built on top of
whatsmeow Go library for WhatsApp Web protocol.

This is the original implementation that uses QR code authentication
and personal WhatsApp accounts (not Business API).
"""

import asyncio
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable, cast

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when channel configuration is invalid."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args)


class ChannelError(Exception):
    """Raised when channel operations fail."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args)


try:
    from neonize.client import NewClient  # type: ignore
    from neonize.events import MessageEv  # type: ignore
    from neonize.utils import ChatPresence, ChatPresenceMedia  # type: ignore
    from neonize.utils.jid import build_jid  # type: ignore

    _NEONIZE_IMPORT_ERROR: Exception | None = None
except Exception as import_error:  # pragma: no cover - depends on system packages
    _NEONIZE_IMPORT_ERROR = import_error

    class NewClient:  # type: ignore[no-redef]
        """Fallback client that raises a clear error when neonize is unavailable."""

        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError(
                "neonize dependency is unavailable. Install system dependencies (e.g., libmagic) and neonize extras."
            ) from _NEONIZE_IMPORT_ERROR

    MessageEv = Any  # type: ignore[misc,assignment]

    class _ChatPresenceFallback:
        CHAT_PRESENCE_COMPOSING = "composing"
        CHAT_PRESENCE_PAUSED = "paused"

    class _ChatPresenceMediaFallback:
        CHAT_PRESENCE_MEDIA_TEXT = "text"


class WhatsAppChannel:
    """WhatsApp communication channel using neonize/whatsmeow bridge.

    This implementation uses QR code-based authentication and supports:
    - Text and media messages
    - Contact filtering for privacy
    - Local storage for session data
    - Message deduplication
    - Typing indicators

    Args:
        storage_path: Directory where neonize will store data
                      (sessions, media, database).
        allowed_contact: Phone number to allow messages from (e.g., "+34 666 666 666").
                         Messages from other numbers are ignored.
        log_filtered_messages: If True, log filtered messages without processing.
        poll_interval: Seconds between message polling checks (not used in event mode).
        typing_indicators: bool = True, Send typing indicators when processing.
        min_typing_duration: float = 2.0, Minimum time (seconds) to show typing indicator.
        dedup_window: float = 10.0, Time window (seconds) for duplicate detection.

    Raises:
        ConfigurationError: If storage_path is invalid or not writable.
    """

    # Class-level lock for CWD changes (os.chdir is a process-global resource).
    # Serializes CWD mutations across all WhatsAppChannel instances so that
    # concurrent initialize() calls do not stomp each other's working directory.
    _cwd_lock: threading.Lock = threading.Lock()

    def __init__(
        self,
        storage_path: str | Path,
        allowed_contact: str,
        log_filtered_messages: bool = False,
        poll_interval: float = 1.0,
        typing_indicators: bool = True,
        min_typing_duration: float = 2.0,
        dedup_window: float = 10.0,
    ) -> None:
        self.storage_path = Path(storage_path).expanduser().resolve()
        self.allowed_contact = self._normalize_phone_number(allowed_contact)
        self.log_filtered_messages = log_filtered_messages
        self.typing_indicators = typing_indicators
        self._min_typing_duration = min_typing_duration
        self._dedup_window = dedup_window

        self._client: NewClient | None = None
        self._is_listening: bool = False
        self._message_callback: Callable[[Any], Any] | None = None
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event = threading.Event()
        self._original_dir = Path.cwd()
        self._typing_jids: set[str] = set()
        self._typing_start_times: dict[str, float] = {}

        # Message deduplication using SQLite
        self._db_path = self.storage_path / "processed_messages.db"
        self._db_lock = threading.Lock()

        # Validate storage path
        self._validate_storage_path()

        logger.info(
            f"WhatsAppChannel (bridge) initialized with storage={self.storage_path}, "
            f"allowed_contact={self.allowed_contact}, "
            f"typing_indicators={self.typing_indicators}, "
            f"min_typing_duration={self._min_typing_duration}, "
            f"dedup_window={self._dedup_window}"
        )

    @staticmethod
    def _normalize_phone_number(phone: str) -> str:
        """Normalize a phone number to a consistent format.

        Args:
            phone: Phone number in any format or JID (e.g., "1234567890@s.whatsapp.net").

        Returns:
            Normalized phone number with spaces, special chars, and JID domain removed.
        """
        # Remove JID domain if present (e.g., "1234567890@s.whatsapp.net" -> "1234567890")
        if "@" in phone:
            phone = phone.split("@")[0]
        # Remove all non-digit characters (except + at start)
        cleaned = phone.replace(" ", "").replace("(", "").replace(")", "")
        # Remove + if present (whatsapp expects format without +)
        return cleaned.lstrip("+")

    @staticmethod
    def _extract_server(jid_str: str) -> str:
        """Extract the server component from a JID string.

        Args:
            jid_str: A JID string like ``"34666666666@s.whatsapp.net"`` or
                     ``"118657162162293@lid"``.

        Returns:
            The server portion (e.g. ``"s.whatsapp.net"``, ``"lid"``).
            Defaults to ``"s.whatsapp.net"`` when no ``@`` is present.
        """
        if "@" in jid_str:
            return jid_str.split("@", 1)[1]
        return "s.whatsapp.net"

    def _send_typing(self, jid: str) -> None:
        """Send typing indicator to a JID.

        Args:
            jid: The full JID string (e.g. ``"34666@s.whatsapp.net"``
                 or ``"118657162162293@lid"``).
        """
        if not self.typing_indicators or self._client is None:
            logger.debug(
                f"Skipping typing indicator for {jid}: "
                f"indicators={self.typing_indicators}, client={self._client is not None}"
            )
            return

        try:
            user = self._normalize_phone_number(jid)
            server = self._extract_server(jid)
            jid_obj = build_jid(user, server=server)
            self._client.send_chat_presence(
                jid_obj,
                ChatPresence.CHAT_PRESENCE_COMPOSING,
                ChatPresenceMedia.CHAT_PRESENCE_MEDIA_TEXT,
            )
            self._typing_jids.add(jid)
            self._typing_start_times[jid] = time.time()
            logger.info(f"Sent typing indicator to {jid} (active: {len(self._typing_jids)})")
        except Exception as e:
            logger.warning(f"Failed to send typing indicator: {e}")

    async def _stop_typing(self, jid: str) -> None:
        """Stop typing indicator for a JID.

        Args:
            jid: The JID to stop typing indicator for.
        """
        if not self.typing_indicators or self._client is None or jid not in self._typing_jids:
            logger.debug(f"Skipping stop typing for {jid}: in_jids={jid in self._typing_jids}")
            return

        # Enforce minimum typing duration
        if jid in self._typing_start_times:
            elapsed = time.time() - self._typing_start_times[jid]
            if elapsed < self._min_typing_duration:
                # Wait for minimum duration to pass
                wait_time = self._min_typing_duration - elapsed
                logger.info(
                    f"Waiting {wait_time:.1f}s before stopping typing indicator for {jid} (elapsed: {elapsed:.1f}s)"
                )
                await asyncio.sleep(wait_time)

        try:
            user = self._normalize_phone_number(jid)
            server = self._extract_server(jid)
            jid_obj = build_jid(user, server=server)
            self._client.send_chat_presence(
                jid_obj,
                ChatPresence.CHAT_PRESENCE_PAUSED,
                ChatPresenceMedia.CHAT_PRESENCE_MEDIA_TEXT,
            )
            self._typing_jids.discard(jid)
            self._typing_start_times.pop(jid, None)
            logger.info(f"Stopped typing indicator for {jid} (remaining active: {len(self._typing_jids)})")
        except Exception as e:
            logger.warning(f"Failed to stop typing indicator: {e}")

    def _validate_storage_path(self) -> None:
        """Validate that storage_path is a writable directory.

        Raises:
            ConfigurationError: If storage_path is invalid or not writable.
        """
        try:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            # Test writability
            test_file = self.storage_path / ".write_test"
            test_file.touch()
            test_file.unlink()
        except (OSError, IOError) as e:
            raise ConfigurationError(
                f"Cannot write to storage path '{self.storage_path}': {e}",
                channel_name="whatsapp",
            ) from e

    async def initialize(self) -> None:
        """Initialize neonize client.

        Creates the neonize client and registers event handlers. The working
        directory change required by neonize happens inside the background
        thread (_run_client) to avoid blocking the main thread and to
        serialize concurrent channel instances via the class-level _cwd_lock.

        Raises:
            ChannelError: If neonize fails to initialize.
        """
        logger.info("Initializing neonize client...")

        # Initialize deduplication database for persistent duplicate prevention
        self._init_deduplication_db()

        try:
            # Create neonize sync client — CWD change happens inside _run_client() thread
            self._client = NewClient("agntrick-whatsapp")
            logger.info("Neonize client created")

            # Set up event handler for incoming messages
            if self._client:
                self._client.event(MessageEv)(self._on_message_event)
                logger.info("Neonize client initialized successfully")
            else:
                raise ChannelError(
                    "Failed to initialize neonize client",
                    channel_name="whatsapp",
                )
        except Exception as e:
            self._client = None
            raise ChannelError(
                f"Failed to initialize neonize client: {e}",
                channel_name="whatsapp",
            ) from e

    def _init_deduplication_db(self) -> None:
        """Initialize the deduplication database."""
        with self._db_lock:
            conn = self._get_db_connection()
            conn.execute("VACUUM")
            conn.commit()

    def _extract_text(self, event: Any) -> str | None:
        """Extract the text content from a neonize MessageEv protobuf.

        Tries multiple paths since protobuf structure varies by message type.

        Args:
            event: A ``Neonize_pb2.Message`` protobuf instance.

        Returns:
            The plain-text string, or ``None`` if the message has no text.
        """
        try:
            msg = getattr(event, "Message", None)
            if msg is None:
                return None

            # Plain text message
            try:
                if msg.HasField("conversation") and msg.conversation:
                    return str(msg.conversation)
            except ValueError:
                if getattr(msg, "conversation", None):
                    return str(msg.conversation)

            # Extended text (messages with link previews, quotes, etc.)
            try:
                if msg.HasField("extendedTextMessage") and msg.extendedTextMessage.text:
                    return str(msg.extendedTextMessage.text)
            except ValueError:
                ext = getattr(msg, "extendedTextMessage", None)
                if ext and getattr(ext, "text", None):
                    return str(ext.text)

            return None
        except Exception as exc:
            logger.warning("Failed to extract text from event: %s", exc)
            return None

    def _extract_sender_jid(self, event: Any) -> str:
        """Return the raw sender JID string from a neonize MessageEv.

        For 1-to-1 chats the sender equals the chat JID.  For groups the
        ``Sender`` field identifies the individual participant.

        Args:
            event: A ``Neonize_pb2.Message`` protobuf instance.

        Returns:
            A JID string like ``"34666666666@s.whatsapp.net"``.
        """
        try:
            info = getattr(event, "Info", None)
            if info is None:
                return "unknown"
            source = getattr(info, "MessageSource", None)
            if source is None:
                return "unknown"

            sender = getattr(source, "Sender", None)
            if sender and getattr(sender, "User", None):
                server = getattr(sender, "Server", "s.whatsapp.net")
                return f"{sender.User}@{server}"

            chat = getattr(source, "Chat", None)
            if chat and getattr(chat, "User", None):
                server = getattr(chat, "Server", "s.whatsapp.net")
                return f"{chat.User}@{server}"

            return "unknown"
        except Exception as exc:
            logger.warning("Failed to extract sender JID: %s", exc)
            return "unknown"

    def _collect_candidate_numbers(self, event: Any) -> set[str]:
        """Collect all phone-number candidates from a message event.

        WhatsApp may identify senders via LID (Linked ID) instead of a
        phone-number-based JID.  To reliably match ``allowed_contact`` we
        gather numbers from every JID field in the ``MessageSource``
        (Sender, SenderAlt, Chat) and return the normalised set.

        Args:
            event: A ``Neonize_pb2.Message`` protobuf instance.

        Returns:
            A set of normalised phone-number strings (digits only).
        """
        numbers: set[str] = set()
        try:
            info = getattr(event, "Info", None)
            if info is None:
                return numbers
            source = getattr(info, "MessageSource", None)
            if source is None:
                return numbers

            for field in ("Sender", "SenderAlt", "Chat"):
                jid = getattr(source, field, None)
                if jid and getattr(jid, "User", None):
                    server = getattr(jid, "Server", "")
                    full = f"{jid.User}@{server}"
                    normalised = self._normalize_phone_number(full)
                    if normalised:
                        numbers.add(normalised)
        except Exception as exc:
            logger.warning("Failed to collect candidate numbers: %s", exc)
        return numbers

    def _on_message_event(self, client: Any, event: Any) -> None:
        """Handle incoming message events from neonize.

        Runs on a neonize C-callback thread, so we:
        1. Extract text and sender from the protobuf event.
        2. Filter by ``allowed_contact``.
        3. Fire typing indicator.
        4. Schedule the async callback on the main event loop.

        Args:
            client: The neonize client instance (passed by the event system).
            event: The ``Neonize_pb2.Message`` protobuf payload.
        """
        if not self._message_callback or not self._loop:
            logger.debug(
                "Event ignored: callback=%s, loop=%s",
                self._message_callback is not None,
                self._loop is not None,
            )
            return

        info = getattr(event, "Info", None)

        text = self._extract_text(event)
        if not text:
            msg_type = getattr(info, "Type", "?") if info else "?"
            media_type = getattr(info, "MediaType", "") if info else ""
            logger.debug("No text in event (type=%s, media=%s) — skipping", msg_type, media_type)
            return

        sender_jid = self._extract_sender_jid(event)
        sender_number = self._normalize_phone_number(sender_jid)
        push_name = getattr(info, "Pushname", "") if info else ""

        logger.info("Incoming message from %s (%s): %s", push_name or sender_number, sender_jid, text[:80])

        # Contact filter — collect all candidate numbers (Sender, SenderAlt,
        # Chat) because the primary Sender may be a LID that doesn't match
        # a phone number.
        if self.allowed_contact:
            candidates = self._collect_candidate_numbers(event)
            if self.allowed_contact not in candidates:
                logger.info(
                    "Filtered message from %s (candidates=%s, allowed=%s)",
                    push_name or "unknown",
                    candidates,
                    self.allowed_contact,
                )
                return

        # Send typing indicator (sync, runs on this thread)
        self._send_typing(sender_jid)

        # Build a normalised dict the router already understands
        normalized: dict[str, Any] = {
            "text": text,
            "sender_id": sender_jid,
            "sender_number": sender_number,
            "timestamp": getattr(info, "Timestamp", 0) if info else 0,
            "push_name": push_name,
            "raw_event": event,
        }

        async def _dispatch() -> None:
            try:
                assert self._message_callback is not None
                await self._message_callback(normalized)
            except Exception as exc:
                logger.error("Error in message callback: %s", exc, exc_info=True)
            finally:
                await self._stop_typing(sender_jid)

        asyncio.run_coroutine_threadsafe(_dispatch(), self._loop)

    def _restore_working_directory(self) -> None:
        """Restore the original working directory."""
        if self._original_dir and Path.cwd() != self._original_dir:
            try:
                os.chdir(self._original_dir)
                logger.debug(f"Restored working directory to: {self._original_dir}")
            except OSError as e:
                logger.error(f"Failed to restore working directory: {e}")

    def _close_deduplication_db(self) -> None:
        """Close the deduplication database connection."""
        if hasattr(self, "_db"):
            self._db.close()
            del self._db

    def _get_db_connection(self) -> sqlite3.Connection:
        """Get or create a thread-local SQLite connection via agntrick.storage."""
        if not hasattr(self, "_db"):
            from agntrick.storage.database import Database  # type: ignore[import-untyped]

            self._db = Database(self._db_path)

            # Initialize table for this new connection
            cursor = self._db.connection.cursor()  # type: ignore[union-attr]
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processed_messages (
                    message_hash TEXT PRIMARY KEY,
                    sender_id TEXT NOT NULL,
                    first_seen_at REAL NOT NULL,
                    last_seen_at REAL NOT NULL
                )
            """)
            # Check if last_seen_at column exists, add if missing (schema migration)
            cursor.execute("PRAGMA table_info(processed_messages)")
            columns = [row[1] for row in cursor.fetchall()]
            if "last_seen_at" not in columns:
                cursor.execute("ALTER TABLE processed_messages ADD COLUMN last_seen_at REAL NOT NULL DEFAULT 0")
                logger.info("Migrated database schema: added last_seen_at column")
            self._db.connection.commit()  # type: ignore[union-attr]

        return cast(sqlite3.Connection, self._db.connection)  # type: ignore[return-value]

    async def listen(self, callback: Callable[[Any], Any]) -> None:
        """Start listening for incoming WhatsApp messages.

        This method starts an event loop for receiving messages from neonize.
        The callback will be invoked for each message from allowed contact.

        Args:
            callback: Async callable to invoke with each incoming message.

        Raises:
            ChannelError: If listening cannot be started.
        """
        if self._client is None:
            raise ChannelError(
                "Channel not initialized. Call initialize() first.",
                channel_name="whatsapp",
            )

        if self._is_listening:
            logger.warning("Already listening for messages")
            return

        self._is_listening = True
        self._message_callback = callback
        self._loop = asyncio.get_running_loop()

        logger.info("Starting to listen for WhatsApp messages...")

        # Start neonize client in a separate thread to avoid blocking event loop
        def _run_client() -> None:
            try:
                assert self._client is not None
                # Check if session file exists and its size
                session_file_name = "agntrick-whatsapp"
                if self._client.device_props is not None:
                    session_file_name = self._client.device_props.name
                session_file = self.storage_path / session_file_name
                if session_file.exists():
                    session_size = session_file.stat().st_size
                    session_age = time.time() - session_file.stat().st_mtime
                    age_hours = session_age / 3600
                    logger.info(
                        f"Found existing session file: {session_file.name} "
                        f"(size={session_size / 1024 / 1024:.1f}MB, age={age_hours:.1f}h)"
                    )
                else:
                    logger.warning("No existing session file found - QR code scan will be required")

                # Serialize CWD changes across all channel instances.
                # neonize uses the process CWD during connect() to locate its
                # session database, so we must hold the lock for the duration of
                # that call and then restore before releasing.
                with WhatsAppChannel._cwd_lock:
                    os.chdir(self.storage_path)
                    logger.debug(f"Changed working directory to: {self.storage_path}")
                    try:
                        # Connect to WhatsApp (may require QR code scan on first run)
                        logger.info("Connecting to WhatsApp (scan QR code if prompted)...")
                        self._client.connect()
                        logger.info("WhatsApp client connected")
                    finally:
                        # Restore CWD before releasing lock so other threads
                        # see a clean state when they acquire it.
                        self._restore_working_directory()

                # Wait for stop signal (outside lock — neonize only needs CWD during connect)
                logger.info("Waiting for messages...")
                while not self._stop_event.is_set():
                    # Small sleep to avoid busy-waiting
                    self._stop_event.wait(timeout=0.1)

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error in neonize client thread: {error_msg}")
                # Provide helpful guidance based on error type
                if "401" in error_msg or "logged out" in error_msg:
                    logger.error(
                        "WhatsApp session was rejected (401). This could mean:\n"
                        "  1. Session expired (WhatsApp sessions expire after ~14 days of inactivity)\n"
                        "  2. Another device logged out this session\n"
                        "  3. Password/2FA changed on WhatsApp account\n"
                        "To fix: Delete session file and scan QR code again.\n"
                        f"Session location: {self.storage_path}"
                    )
                elif "EOF" in error_msg:
                    logger.error(
                        "Connection closed unexpectedly (EOF). This could be:\n"
                        "  1. Network connectivity issue\n"
                        "  2. WhatsApp server unavailable\n"
                        "  3. Session was invalidated mid-connection\n"
                    )

        self._thread = threading.Thread(target=_run_client, daemon=True)
        self._thread.start()

        # Wait for stop signal
        try:
            while self._is_listening and (self._thread is None or self._thread.is_alive()):
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Listening cancelled")
        finally:
            # Clear typing indicators
            self._typing_jids.clear()
            self._typing_start_times.clear()

    async def send(self, message: Any) -> str:
        """Send a message through WhatsApp.

        Args:
            message: The message to send. Can be a string (text message)
                    or an OutgoingMessage-like object with recipient_id.

        Raises:
            MessageError: If message cannot be sent.
        """
        if self._client is None:
            raise ChannelError(
                "Channel not initialized. Call initialize() first.",
                channel_name="whatsapp",
            )

        try:
            # Handle both string messages and OutgoingMessage objects
            recipient_id = message.recipient_id if hasattr(message, "recipient_id") else message

            user = self._normalize_phone_number(recipient_id)
            server = self._extract_server(recipient_id)
            jid = build_jid(user, server=server)

            if hasattr(message, "media_url") and message.media_url:
                # Send media message
                await self._send_media(jid, message.media_url, message.text, message.media_type)
            else:
                # Send text message - run in thread pool to avoid blocking
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self._client.send_message, jid, message.text)

            logger.info("Message sent")
            return jid  # type: ignore[no-any-return]

        except Exception as e:
            raise ChannelError(
                f"Failed to send message: {e}",
                channel_name="whatsapp",
            ) from e

    async def send_message(self, recipient_id: str, text: str) -> None:
        """Send a text message to a recipient.

        Convenience method that satisfies the WhatsAppChannelBase ABC and is
        called by the router when sending plain-text responses.

        Args:
            recipient_id: The WhatsApp JID (e.g. ``"34666@s.whatsapp.net"``
                          or ``"118657@lid"``) or a bare phone number.
            text: The text message to send.

        Raises:
            ChannelError: If the channel is not initialized or sending fails.
        """
        if self._client is None:
            raise ChannelError(
                "Channel not initialized. Call initialize() first.",
                channel_name="whatsapp",
            )

        try:
            user = self._normalize_phone_number(recipient_id)
            server = self._extract_server(recipient_id)
            jid = build_jid(user, server=server)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._client.send_message, jid, text)
            logger.info(f"Message sent to {recipient_id}")
        except Exception as e:
            raise ChannelError(
                f"Failed to send message: {e}",
                channel_name="whatsapp",
            ) from e

    async def _send_media(self, jid: str, media_url: str, caption: str, media_type: str) -> None:
        """Send a media message."""
        if self._client is None:
            raise ChannelError("Client not initialized", channel_name="whatsapp")

        # Download media from URL
        import httpx

        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(media_url)
            response.raise_for_status()
            media_data = response.content

        # Use Content-Type from response header for accurate mime type
        mime_type = response.headers.get("content-type", "image/jpeg")
        if "content-type" not in response.headers:
            # Fallback mapping if content-type is not provided
            mime_types = {
                "image": "image/jpeg",
                "video": "video/mp4",
                "document": "application/pdf",
                "audio": "audio/mpeg",
            }
            mime_type = mime_types.get(media_type, "image/jpeg")

        # Build and send media message based on type - run in thread pool
        def _build_and_send() -> None:
            assert self._client is not None
            if media_type == "image":
                msg = self._client.build_image_message(media_data, caption=caption, mime_type=mime_type)
            elif media_type == "video":
                msg = self._client.build_video_message(media_data, caption=caption, mime_type=mime_type)
            elif media_type == "document":
                filename = media_url.split("/")[-1]
                msg = self._client.build_document_message(
                    media_data, filename=filename, caption=caption, mime_type=mime_type
                )
            elif media_type == "audio":
                msg = self._client.build_audio_message(media_data, mime_type=mime_type)
            else:
                # Default to image
                msg = self._client.build_image_message(media_data, caption=caption, mime_type=mime_type)
            self._client.send_message(jid, message=msg)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _build_and_send)

    async def shutdown(self) -> None:
        """Gracefully shutdown the WhatsApp channel.

        This stops listening for messages and closes connections.
        """
        logger.info("Shutting down WhatsApp channel...")
        self._is_listening = False
        self._message_callback = None
        self._stop_event.set()

        # Clear typing indicators
        self._typing_jids.clear()
        self._typing_start_times.clear()

        # Close deduplication database
        self._close_deduplication_db()

        # Disconnect client and clear reference
        if self._client:
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self._client.disconnect)
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
            finally:
                self._client = None

        # Wait for thread to finish, and warn if it outlives timeout
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                logger.warning("Worker thread did not stop within timeout — possible resource leak")

        logger.info("WhatsApp channel shutdown complete")
