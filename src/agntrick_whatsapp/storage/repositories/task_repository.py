"""Repository for managing tasks and schedules."""

from datetime import datetime
from typing import List, Optional, Any

from ..database import db_manager
from ..models import Task
from ..scheduler import TimeParser


class TaskRepository:
    """Repository for task operations."""

    def create(self, thread_id: str, title: str, description: Optional[str] = None, due_date: Optional[str] = None) -> Task:
        """Create a new task.

        Args:
            thread_id: WhatsApp thread ID.
            title: Task title.
            description: Task description.
            due_date: Due date as string (will be parsed).

        Returns:
            Created Task instance.
        """
        if due_date:
            parsed_time, _ = TimeParser.parse_time_input(due_date)
            due_dt = parsed_time
        else:
            due_dt = None

        return Task.create(thread_id, title, description, due_dt)

    def get_by_thread(self, thread_id: str) -> List[Task]:
        """Get all tasks for a thread.

        Args:
            thread_id: WhatsApp thread ID.

        Returns:
            List of Task instances.
        """
        return Task.get_by_thread(thread_id)

    def get_by_id(self, task_id: int) -> Optional[Task]:
        """Get a task by ID.

        Args:
            task_id: Task ID.

        Returns:
            Task instance if found, None otherwise.
        """
        return Task.get_by_id(task_id)

    def delete(self, task_id: int) -> bool:
        """Delete a task.

        Args:
            task_id: Task ID.

        Returns:
            True if task was deleted, False if not found.
        """
        conn = db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def complete(self, task_id: int) -> Optional[Task]:
        """Mark a task as completed.

        Args:
            task_id: Task ID.

        Returns:
            Updated Task instance if found, None otherwise.
        """
        task = Task.get_by_id(task_id)
        if task:
            task.complete()
            return task
        return None

    def update(self, task_id: int, **kwargs: dict[str, Any]) -> Optional[Task]:
        """Update a task.

        Args:
            task_id: Task ID.
            **kwargs: Fields to update (title, description, due_date).

        Returns:
            Updated Task instance if found, None otherwise.
        """
        task = Task.get_by_id(task_id)
        if task:
            # Parse due_date if provided
            due_date = kwargs.get('due_date')
            if isinstance(due_date, str):
                parsed_time, _ = TimeParser.parse_time_input(due_date)
                task.update(due_date=parsed_time)
            elif isinstance(due_date, str):
                task.update(due_date=due_date)
            elif 'title' in kwargs and isinstance(kwargs['title'], str):
                task.update(title=kwargs['title'])
            elif 'description' in kwargs and isinstance(kwargs['description'], str):
                task.update(description=kwargs['description'])
            return task
        return None

    def get_active_schedules(self) -> List[dict]:
        """Get all active schedules.

        Returns:
            List of schedule dictionaries with task details.
        """
        conn = db_manager.get_connection()
        try:
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
                    "created_at": row["created_at"]
                }
                for row in rows
            ]
        finally:
            conn.close()

    def create_schedule(self, thread_id: str, task_id: int, cron_expression: str) -> Optional[dict]:
        """Create a new schedule for a task.

        Args:
            thread_id: WhatsApp thread ID.
            task_id: Task ID to schedule.
            cron_expression: Cron expression.

        Returns:
            Created schedule dictionary if successful, None otherwise.
        """
        if not TimeParser.validate_cron_expression(cron_expression):
            return None

        next_run = TimeParser.get_next_run_time(cron_expression)
        if not next_run:
            return None

        conn = db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO schedules (thread_id, task_id, cron_expression, next_run)
                VALUES (?, ?, ?, ?)
                """,
                (thread_id, task_id, cron_expression, next_run.isoformat())
            )
            conn.commit()

            return {
                "id": cursor.lastrowid,
                "thread_id": thread_id,
                "task_id": task_id,
                "cron_expression": cron_expression,
                "next_run": next_run,
                "is_active": True,
                "created_at": next_run
            }
        finally:
            conn.close()

    def update_schedule(self, schedule_id: int, cron_expression: str) -> Optional[dict]:
        """Update a schedule's cron expression.

        Args:
            schedule_id: Schedule ID.
            cron_expression: New cron expression.

        Returns:
            Updated schedule dictionary if successful, None otherwise.
        """
        if not TimeParser.validate_cron_expression(cron_expression):
            return None

        next_run = TimeParser.get_next_run_time(cron_expression)
        if not next_run:
            return None

        conn = db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE schedules
                SET cron_expression = ?, next_run = ?
                WHERE id = ?
                """,
                (cron_expression, next_run.isoformat(), schedule_id)
            )
            conn.commit()

            if cursor.rowcount > 0:
                # Get the updated schedule
                cursor.execute("SELECT * FROM schedules WHERE id = ?", (schedule_id,))
                row = cursor.fetchone()
                return {
                    "id": row["id"],
                    "thread_id": row["thread_id"],
                    "task_id": row["task_id"],
                    "cron_expression": row["cron_expression"],
                    "next_run": row["next_run"],
                    "is_active": row["is_active"],
                    "created_at": row["created_at"]
                }
            return None
        finally:
            conn.close()

    def deactivate_schedule(self, schedule_id: int) -> bool:
        """Deactivate a schedule.

        Args:
            schedule_id: Schedule ID.

        Returns:
            True if schedule was deactivated, False if not found.
        """
        conn = db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE schedules SET is_active = FALSE WHERE id = ?", (schedule_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()