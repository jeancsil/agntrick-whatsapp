"""Test cases for agntrick.storage repositories used by agntrick-whatsapp."""

# ruff: noqa: E402

from pathlib import Path

import pytest

# Skip tests if agntrick.storage is not available (CI environment)
pytest.importorskip("agntrick.storage")

from agntrick.storage import (  # type: ignore[import-untyped]
    Database,
    Note,
    NoteRepository,
    ScheduledTask,
    TaskRepository,
    TaskStatus,
    TaskType,
)


@pytest.fixture
def db(tmp_path: Path) -> Database:
    """Create a temporary Database for testing.

    Args:
        tmp_path: Pytest temporary directory fixture.

    Returns:
        Initialised Database instance backed by a temp file.
    """
    return Database(tmp_path / "test.db")


class TestNoteRepository:
    """Test cases for NoteRepository."""

    def test_save_and_retrieve_note(self, db: Database) -> None:
        """Test saving a note and retrieving it by ID."""
        repo = NoteRepository(db)
        note = Note(content="hello", context_id="user1")
        repo.save(note)
        retrieved = repo.get_by_id(note.id)
        assert retrieved is not None
        assert retrieved.content == "hello"
        assert retrieved.context_id == "user1"

    def test_list_all_notes(self, db: Database) -> None:
        """Test listing all notes."""
        repo = NoteRepository(db)
        note1 = Note(content="first", context_id="user1")
        note2 = Note(content="second", context_id="user2")
        repo.save(note1)
        repo.save(note2)
        all_notes = repo.list_all()
        assert len(all_notes) == 2

    def test_delete_note(self, db: Database) -> None:
        """Test deleting a note."""
        repo = NoteRepository(db)
        note = Note(content="to delete", context_id="user1")
        repo.save(note)
        deleted = repo.delete(note.id)
        assert deleted is True
        assert repo.get_by_id(note.id) is None

    def test_get_nonexistent_note(self, db: Database) -> None:
        """Test retrieving a non-existent note returns None."""
        repo = NoteRepository(db)
        result = repo.get_by_id("nonexistent-id-12345")
        assert result is None


class TestTaskRepository:
    """Test cases for TaskRepository."""

    def test_save_and_retrieve_task(self, db: Database) -> None:
        """Test saving a ScheduledTask and retrieving it by ID."""
        from datetime import UTC, datetime

        repo = TaskRepository(db)
        task = ScheduledTask(
            action_type=TaskType.SEND_MESSAGE,
            action_prompt="Hello!",
            context_id="user1",
            execute_at=datetime.now(UTC).timestamp() + 3600,
        )
        repo.save(task)
        retrieved = repo.get_by_id(task.id)
        assert retrieved is not None
        assert retrieved.action_type == TaskType.SEND_MESSAGE
        assert retrieved.context_id == "user1"

    def test_get_all_pending(self, db: Database) -> None:
        """Test retrieving all pending tasks."""
        from datetime import UTC, datetime

        repo = TaskRepository(db)
        task = ScheduledTask(
            action_type=TaskType.RUN_AGENT,
            action_agent="chef",
            action_prompt="What can I cook?",
            execute_at=datetime.now(UTC).timestamp() + 3600,
        )
        repo.save(task)
        pending = repo.get_all_pending()
        assert any(t.id == task.id for t in pending)

    def test_update_status(self, db: Database) -> None:
        """Test updating task status."""
        from datetime import UTC, datetime

        repo = TaskRepository(db)
        task = ScheduledTask(
            action_type=TaskType.SEND_MESSAGE,
            action_prompt="Test",
            execute_at=datetime.now(UTC).timestamp() + 60,
        )
        repo.save(task)
        updated = repo.update_status(task.id, TaskStatus.COMPLETED)
        assert updated is True
        retrieved = repo.get_by_id(task.id)
        assert retrieved is not None
        assert retrieved.status == TaskStatus.COMPLETED

    def test_get_nonexistent_task(self, db: Database) -> None:
        """Test retrieving a non-existent task returns None."""
        repo = TaskRepository(db)
        result = repo.get_by_id("nonexistent-id-99999")
        assert result is None
