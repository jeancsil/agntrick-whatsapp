"""Repository for managing tasks and schedules."""

from datetime import datetime
from typing import Any, List, Optional

from ..database import db_manager
from ..models import Task
from ..scheduler import TimeParser


class TaskRepository:
    """Repository for task operations."""

    def create(
        self, thread_id: str, title: str, description: Optional[str] = None, due_date: Optional[str] = None
    ) -> Task:
        """Create a new task."""
        if due_date:
            parsed_time, _ = TimeParser.parse_time_input(due_date)
            due_dt = parsed_time
        else:
            due_dt = None

        return Task.create(thread_id, title, description, due_dt)

    def get_by_thread(self, thread_id: str) -> List[Task]:
        """Get all tasks for a thread."""
        return Task.get_by_thread(thread_id)

    def get_by_id(self, task_id: int) -> Optional[Task]:
        """Get a task by ID."""
        return Task.get_by_id(task_id)

    def delete(self, task_id: int) -> bool:
        """Delete a task.

        Args:
            task_id: Task ID.

        Returns:
            True if task was deleted, False if not found.
        """
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        return cursor.rowcount > 0

    def complete(self, task_id: int) -> Optional[Task]:
        """Mark a task as completed."""
        task = Task.get_by_id(task_id)
        if task:
            task.complete()
            return task
        return None

    def update(self, task_id: int, **kwargs: dict[str, Any]) -> Optional[Task]:
        """Update a task."""
        task = Task.get_by_id(task_id)
        if task:
            title: str | None = None
            description: str | None = None
            due_date: datetime | None = None

            if kwargs.get("title") is not None and isinstance(kwargs["title"], str):
                title = kwargs["title"]

            if kwargs.get("description") is not None and isinstance(kwargs["description"], str):
                description = kwargs["description"]

            if kwargs.get("due_date") is not None:
                due_date_input = kwargs["due_date"]
                if isinstance(due_date_input, str):
                    parsed_time, _ = TimeParser.parse_time_input(due_date_input)
                    due_date = parsed_time
                elif due_date_input is not None:
                    due_date = due_date_input  # type: ignore[assignment]

            # Write changes to database
            task._write_to_db()

            # Update in-memory task object
            if title is not None:
                task.title = title
            if description is not None:
                task.description = description
            if due_date is not None:
                task.due_date = due_date

            return task
        return None

    def get_active_schedules(self) -> List[dict]:
        """Get all active schedules."""
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, t.title, t.description, t.thread_id
            FROM schedules s
            JOIN tasks t ON s.task_id = t.id
            WHERE s.is_active = TRUE
            ORDER BY s.next_run ASC
        """)
        rows = cursor.fetchall()
        return [
            {
                "id": row["id"],
                "thread_id": row["thread_id"],
                "task_id": row["task_id"],
                "title": row["title"],
                "description": row["description"],
                "cron_expression": row["cron_expression"],
                "next_run": row["next_run"],
                "is_active": row["is_active"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def create_schedule(self, thread_id: str, task_id: int, cron_expression: str) -> Optional[dict]:
        """Create a new schedule for a task."""
        if not TimeParser.validate_cron_expression(cron_expression):
            return None

        next_run = TimeParser.get_next_run_time(cron_expression)
        if not next_run:
            return None

        conn = db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO schedules (thread_id, task_id, cron_expression, next_run)
            VALUES (?, ?, ?, ?)
            """,
            (thread_id, task_id, cron_expression, next_run.isoformat()),
        )
        conn.commit()

        return {
            "id": cursor.lastrowid,
            "thread_id": thread_id,
            "task_id": task_id,
            "cron_expression": cron_expression,
            "next_run": next_run,
            "is_active": True,
            "created_at": next_run,
        }

    def update_schedule(self, schedule_id: int, cron_expression: str) -> Optional[dict]:
        """Update a schedule's cron expression."""
        if not TimeParser.validate_cron_expression(cron_expression):
            return None

        next_run = TimeParser.get_next_run_time(cron_expression)
        if not next_run:
            return None

        conn = db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE schedules
            SET cron_expression = ?, next_run = ?
            WHERE id = ?
            """,
            (cron_expression, next_run.isoformat(), schedule_id),
        )
        conn.commit()

        if cursor.rowcount > 0:
            cursor.execute("SELECT * FROM schedules WHERE id = ?", (schedule_id,))
            row = cursor.fetchone()
            return {
                "id": row["id"],
                "thread_id": row["thread_id"],
                "task_id": row["task_id"],
                "cron_expression": row["cron_expression"],
                "next_run": row["next_run"],
                "is_active": row["is_active"],
                "created_at": row["created_at"],
            }
        return None

    def deactivate_schedule(self, schedule_id: int) -> bool:
        """Deactivate a schedule."""
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE schedules SET is_active = FALSE WHERE id = ?", (schedule_id,))
        conn.commit()
        return cursor.rowcount > 0
