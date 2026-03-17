"""Integration tests for the agntrick_whatsapp.storage thin wrapper."""

# ruff: noqa: E402

from pathlib import Path

import pytest

# Skip tests if agntrick.storage is not available (CI environment)
pytest.importorskip("agntrick.storage")

from agntrick.storage import Database, Note, ScheduledTask, TaskType  # type: ignore[import-untyped]

from agntrick_whatsapp.storage import WhatsAppNoteRepository, get_default_db


class TestGetDefaultDb:
    """Tests for get_default_db helper."""

    def test_returns_database_instance(self, tmp_path: Path) -> None:
        """Test that get_default_db returns a Database instance."""
        db = get_default_db(tmp_path / "test.db")
        assert isinstance(db, Database)

    def test_database_is_usable(self, tmp_path: Path) -> None:
        """Test that the returned Database is immediately usable."""
        db = get_default_db(tmp_path / "test.db")
        # Should be able to create a connection without errors
        conn = db.connection
        assert conn is not None


class TestWhatsAppNoteRepository:
    """Tests for WhatsAppNoteRepository context filtering."""

    @pytest.fixture
    def db(self, tmp_path: Path) -> Database:
        """Create a temporary Database for testing.

        Args:
            tmp_path: Pytest temporary directory fixture.

        Returns:
            Initialised Database instance.
        """
        return Database(tmp_path / "notes_test.db")

    def test_list_by_context_filters_correctly(self, db: Database) -> None:
        """Test that list_by_context returns only notes for the given context."""
        repo = WhatsAppNoteRepository(db)
        note_user1_a = Note(content="user1 note A", context_id="user1")
        note_user1_b = Note(content="user1 note B", context_id="user1")
        note_user2 = Note(content="user2 note", context_id="user2")
        repo.save(note_user1_a)
        repo.save(note_user1_b)
        repo.save(note_user2)

        user1_notes = repo.list_by_context("user1")
        assert len(user1_notes) == 2
        assert all(n.context_id == "user1" for n in user1_notes)

    def test_list_by_context_empty_for_unknown(self, db: Database) -> None:
        """Test that list_by_context returns empty list for unknown context."""
        repo = WhatsAppNoteRepository(db)
        note = Note(content="some note", context_id="user1")
        repo.save(note)

        result = repo.list_by_context("unknown_user")
        assert result == []

    def test_list_by_context_ordered_by_creation(self, db: Database) -> None:
        """Test that list_by_context returns notes ordered by created_at ascending."""
        repo = WhatsAppNoteRepository(db)
        note_a = Note(content="first", context_id="user1", created_at=1000.0)
        note_b = Note(content="second", context_id="user1", created_at=2000.0)
        repo.save(note_a)
        repo.save(note_b)

        notes = repo.list_by_context("user1")
        assert len(notes) == 2
        assert notes[0].created_at <= notes[1].created_at

    def test_note_model_is_agntrick_note(self, db: Database) -> None:
        """Test that Note from wrapper is the same class as agntrick.storage.Note."""
        repo = WhatsAppNoteRepository(db)
        note = Note(content="test", context_id="ctx")
        repo.save(note)
        retrieved = repo.get_by_id(note.id)
        assert isinstance(retrieved, Note)

    def test_scheduled_task_with_send_message(self, db: Database) -> None:
        """Test that ScheduledTask with SEND_MESSAGE action type can be saved."""
        from datetime import UTC, datetime

        from agntrick.storage import TaskRepository

        repo = TaskRepository(db)
        task = ScheduledTask(
            action_type=TaskType.SEND_MESSAGE,
            action_prompt="Good morning!",
            context_id="user1",
            execute_at=datetime.now(UTC).timestamp() + 3600,
        )
        saved = repo.save(task)
        assert saved.id == task.id
        retrieved = repo.get_by_id(task.id)
        assert retrieved is not None
        assert retrieved.action_type == TaskType.SEND_MESSAGE
