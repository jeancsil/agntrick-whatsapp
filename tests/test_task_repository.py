"""Test cases for task repository operations."""

from datetime import datetime

import pytest

# Skip tests if agntrick.storage is not available (CI environment)
agntrick_storage = pytest.importorskip("agntrick.storage")

from agntrick_whatsapp.storage.database import db_manager
from agntrick_whatsapp.storage.models import Task
from agntrick_whatsapp.storage.repositories.task_repository import TaskRepository


@pytest.fixture(scope="function", autouse=True)
def setup_database():
    """Initialize database before each test."""
    # Initialize database
    db_manager.init_database()
    yield
    # Clean up after test
    db_manager.close()


class TestTask:
    """Test cases for Task class."""

    def test_task_creation(self):
        """Test creating a task."""
        task = Task(
            id=1,
            thread_id="test_thread",
            title="Test Task",
            description="A test task",
            due_date=None,
            is_completed=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert task.id == 1
        assert task.title == "Test Task"
        assert not task.is_completed

    def test_task_status_transition(self):
        """Test task status transitions."""
        task = Task(
            id=1,
            thread_id="test_thread",
            title="Test Task",
            description="A test task",
            due_date=None,
            is_completed=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        task.complete()
        assert task.is_completed


class TestTaskRepository:
    """Test cases for TaskRepository class."""

    def test_init(self):
        """Test repository initialization."""
        repository = TaskRepository()
        assert repository is not None

    def test_create_task(self):
        """Test creating a new task."""
        repository = TaskRepository()
        task = repository.create("test_thread", "Test Task", "A test task")
        assert task.id is not None
        assert task.title == "Test Task"
        assert not task.is_completed

    def test_get_task(self):
        """Test retrieving a task by ID."""
        repository = TaskRepository()
        created_task = repository.create("test_thread", "Test Task", "A test task")

        retrieved_task = repository.get_by_id(created_task.id)
        assert retrieved_task.id == created_task.id
        assert retrieved_task.title == "Test Task"

    def test_get_nonexistent_task(self):
        """Test retrieving a non-existent task."""
        repository = TaskRepository()
        result = repository.get_by_id(99999)
        assert result is None

    def test_update_task(self):
        """Test updating a task."""
        repository = TaskRepository()
        task = repository.create("test_thread", "Test Task", "A test task")

        updated_task = repository.update(task.id, title="Updated Task", description="Updated description")
        assert updated_task.title == "Updated Task"
        assert updated_task.description == "Updated description"

    def test_delete_task(self):
        """Test deleting a task."""
        repository = TaskRepository()
        task = repository.create("test_thread", "Test Task", "A test task")

        result = repository.delete(task.id)
        assert result is True

        # Verify task is deleted
        retrieved_task = repository.get_by_id(task.id)
        assert retrieved_task is None
