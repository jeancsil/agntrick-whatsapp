"""Conversation history management for WhatsApp integration."""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ConversationManager:
    """Manages conversation threading and history for WhatsApp.

    Provides thread ID generation and checkpointer access for
    persistent conversation history across agents.

    Thread IDs are scoped to both the user (sender_id) and the
    agent they're talking to, ensuring /news conversations are
    separate from /ollama conversations.

    Attributes:
        _db: The database instance for checkpoint storage.
        _async_checkpointer: The LangGraph AsyncSqliteSaver instance.

    Example:
        ```python
        from agntrick_whatsapp.conversation import ConversationManager

        manager = ConversationManager(Path("~/whatsapp.db"))
        thread_id = manager.get_thread_id("123@s.whatsapp.net", "news")
        # thread_id = "123@s.whatsapp.net:news"
        ```
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize the conversation manager.

        Args:
            db_path: Path to the SQLite database for storage.
                This database will be used by LangGraph to store
                conversation checkpoints and blobs.
        """
        from agntrick.storage.database import Database  # type: ignore[import-untyped]

        self._db = Database(db_path)
        self._async_checkpointer = self._db.get_checkpointer(is_async=True)

    def get_thread_id(self, sender_id: str, agent_name: str) -> str:
        """Generate a thread ID for a sender-agent pair.

        Thread IDs uniquely identify conversations between a specific
        user and a specific agent. This ensures that:
        - Each user's conversations are isolated from other users
        - Different agents have separate conversation histories
        - The same user talking to the same agent gets the same history

        Args:
            sender_id: The WhatsApp sender ID (e.g., "12345@s.whatsapp.net").
            agent_name: The agent name (e.g., "news", "ollama", or "default").

        Returns:
            A thread ID string in format "sender_id:agent_name".
        """
        return f"{sender_id}:{agent_name}"

    @property
    def checkpointer(self) -> Any:
        """Get the async checkpointer for LangGraph.

        The checkpointer is used by LangGraph to store and retrieve
        conversation history. It implements the async checkpoint saver
        interface.

        Returns:
            A LangGraph AsyncSqliteSaver instance.
        """
        return self._async_checkpointer
