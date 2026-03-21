"""Test cases for conversation history management."""

from pathlib import Path

import pytest

from agntrick_whatsapp.conversation import ConversationManager


class TestConversationManager:
    """Test cases for ConversationManager class."""

    def test_thread_id_generation(self):
        """Test that thread IDs are generated correctly for sender-agent pairs."""
        # Create a temporary database for testing
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = ConversationManager(db_path)

            # Test basic thread ID generation
            thread_id = manager.get_thread_id("123@s.whatsapp.net", "news")
            assert thread_id == "123@s.whatsapp.net:news"

            # Test different agent names produce different thread IDs
            thread_id2 = manager.get_thread_id("123@s.whatsapp.net", "ollama")
            assert thread_id2 == "123@s.whatsapp.net:ollama"
            assert thread_id != thread_id2

            # Test different sender IDs produce different thread IDs
            thread_id3 = manager.get_thread_id("456@s.whatsapp.net", "news")
            assert thread_id3 == "456@s.whatsapp.net:news"
            assert thread_id != thread_id3

            # Test same sender-agent pair produces same thread ID
            thread_id4 = manager.get_thread_id("123@s.whatsapp.net", "news")
            assert thread_id4 == thread_id

    def test_conversation_manager_init(self):
        """Test that ConversationManager initializes correctly with a database."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = ConversationManager(db_path)

            # Verify checkpointer is created (has async methods)
            assert manager.checkpointer is not None
            # AsyncSqliteSaver has methods like aput, aget_tuple, alist
            assert hasattr(manager.checkpointer, "aput") or hasattr(manager.checkpointer, "__aenter__")

    def test_conversation_manager_with_default_agent(self):
        """Test thread ID generation with default agent name."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = ConversationManager(db_path)

            # Test with "default" agent name
            thread_id = manager.get_thread_id("123@s.whatsapp.net", "default")
            assert thread_id == "123@s.whatsapp.net:default"

    def test_conversation_manager_checkpointer_property(self):
        """Test that the checkpointer property returns the correct instance."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            manager = ConversationManager(db_path)

            # Checkpointer should be the same instance on multiple accesses
            checkpointer1 = manager.checkpointer
            checkpointer2 = manager.checkpointer
            assert checkpointer1 is checkpointer2


class TestConversationConfig:
    """Test cases for conversation configuration."""

    def test_max_conversation_tokens_config(self):
        """Test that max_conversation_tokens is configurable."""
        from agntrick_whatsapp.config import StorageConfig, WhatsAppConfig, WhatsAppRouterConfig

        config = WhatsAppRouterConfig(
            whatsapp=WhatsAppConfig(
                access_token="EAA TESTING",
                phone_number_id="123456789",
                verify_token="test_token",
            ),
            storage=StorageConfig(type="sqlite", path=":memory:"),
            max_conversation_tokens=8000,
        )

        assert config.max_conversation_tokens == 8000

    def test_conversation_enabled_config(self):
        """Test that conversation_enabled can be configured."""
        from agntrick_whatsapp.config import StorageConfig, WhatsAppConfig, WhatsAppRouterConfig

        config = WhatsAppRouterConfig(
            whatsapp=WhatsAppConfig(
                access_token="EAA TESTING",
                phone_number_id="123456789",
                verify_token="test_token",
            ),
            storage=StorageConfig(type="sqlite", path=":memory:"),
            conversation_enabled=False,
        )

        assert config.conversation_enabled is False

    def test_default_conversation_config(self):
        """Test that default conversation config values are applied."""
        from agntrick_whatsapp.config import StorageConfig, WhatsAppConfig, WhatsAppRouterConfig

        config = WhatsAppRouterConfig(
            whatsapp=WhatsAppConfig(
                access_token="EAA TESTING",
                phone_number_id="123456789",
                verify_token="test_token",
            ),
            storage=StorageConfig(type="sqlite", path=":memory:"),
        )

        assert config.conversation_enabled is True
        assert config.max_conversation_tokens == 4000
