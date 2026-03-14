"""Test cases for task repository operations."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from agntrick_whatsapp.task_repository import TaskRepository, Task


class TestTask:
    """Test cases for Task class."""

    def test_task_creation(self):
        """Test creating a task."""
        task = Task(
            id="1",
            title="Test Task",
            description="A test task",
            status="pending",
            priority="medium",
            created_at=datetime.now(),
            due_date=None
        )
        assert task.id == "1"
        assert task.title == "Test Task"
        assert task.status == "pending"

    def test_task_status_transition(self):
        """Test task status transitions."""
        task = Task(
            id="1",
            title="Test Task",
            description="A test task",
            status="pending",
            priority="medium",
            created_at=datetime.now(),
            due_date=None
        )

        task.mark_in_progress()
        assert task.status == "in_progress"

        task.mark_completed()
        assert task.status == "completed"

        task.mark_cancelled()
        assert task.status == "cancelled"


class TestTaskRepository:
    """Test cases for TaskRepository class."""

    def test_init(self):
        """Test repository initialization."""
        repository = TaskRepository()
        assert repository is not None

    def test_create_task(self):
        """Test creating a new task."""
        repository = TaskRepository()
        task = repository.create_task(
            title="Test Task",
            description="A test task",
            priority="medium"
        )
        assert task.id is not None
        assert task.title == "Test Task"
        assert task.status == "pending"

    def test_get_task(self):
        """Test retrieving a task by ID."""
        repository = TaskRepository()
        created_task = repository.create_task(
            title="Test Task",
            description="A test task",
            priority="medium"
        )

        retrieved_task = repository.get_task(created_task.id)
        assert retrieved_task.id == created_task.id
        assert retrieved_task.title == "Test Task"

    def test_get_nonexistent_task(self):
        """Test retrieving a non-existent task."""
        repository = TaskRepository()
        with pytest.raises(ValueError):
            repository.get_task("nonexistent")

    def test_update_task(self):
        """Test updating a task."""
        repository = TaskRepository()
        task = repository.create_task(
            title="Test Task",
            description="A test task",
            priority="medium"
        )

        updated_task = repository.update_task(
            task.id,
            title="Updated Task",
            description="Updated description"
        )
        assert updated_task.title == "Updated Task"
        assert updated_task.description == "Updated description"

    def test_delete_task(self):
        """Test deleting a task."""
        repository = TaskRepository()
        task = repository.create_task(
            title="Test Task",
            description="A test task",
            priority="medium"
        )

        repository.delete_task(task.id)
        with pytest.raises(ValueError):
            repository.get_task(task.id)

    def test_list_tasks(self):
        """Test listing all tasks."""
        repository = TaskRepository()
        repository.create_task(
            title="Task 1",
            description="First task",
            priority="high"
        )
        repository.create_task(
            title="Task 2",
            description="Second task",
            priority="low"
        )

        tasks = repository.list_tasks()
        assert len(tasks) == 2

    def test_list_tasks_by_status(self):
        """Test listing tasks by status."""
        repository = TaskRepository()
        task1 = repository.create_task(
            title="Task 1",
            description="First task",
            priority="high"
        )
        task2 = repository.create_task(
            title="Task 2",
            description="Second task",
            priority="low"
        )

        # Update one task to completed
        repository.update_task(task1.id, status="completed")

        pending_tasks = repository.list_tasks(status="pending")
        completed_tasks = repository.list_tasks(status="completed")

        assert len(pending_tasks) == 1
        assert len(completed_tasks) == 1
        assert pending_tasks[0].id == task2.id
        assert completed_tasks[0].id == task1.id

    def test_list_tasks_by_priority(self):
        """Test listing tasks by priority."""
        repository = TaskRepository()
        repository.create_task(
            title="High Priority",
            description="High priority task",
            priority="high"
        )
        repository.create_task(
            title="Low Priority",
            description="Low priority task",
            priority="low"
        )

        high_priority_tasks = repository.list_tasks(priority="high")
        assert len(high_priority_tasks) == 1
        assert high_priority_tasks[0].title == "High Priority"

    @patch('agntrick_whatsapp.task_repository.TaskStorage')
    def test_persistence(self, mock_storage):
        """Test task persistence."""
        mock_storage_instance = Mock()
        mock_storage.return_value = mock_storage_instance

        repository = TaskRepository()
        repository.create_task(
            title="Test Task",
            description="A test task",
            priority="medium"
        )

        # Verify storage was called
        mock_storage_instance.save_tasks.assert_called_once()