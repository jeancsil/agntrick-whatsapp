"""Data models for WhatsApp storage."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .database import db_manager


@dataclass
class Note:
    """Represents a note in the storage system."""

    id: int
    thread_id: str
    content: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(cls, thread_id: str, content: str) -> "Note":
        """Create a new note.

        Args:
            thread_id: WhatsApp thread ID.
            content: Note content.

        Returns:
            Created Note instance.
        """
        query = """
        INSERT INTO notes (thread_id, content)
        VALUES (?, ?)
        """
        conn = db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, (thread_id, content))
            conn.commit()
            return cls(
                id=int(cursor.lastrowid) if cursor.lastrowid else 0,
                thread_id=thread_id,
                content=content,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        finally:
            conn.close()

    @classmethod
    def get_by_thread(cls, thread_id: str) -> list["Note"]:
        """Get all notes for a thread.

        Args:
            thread_id: WhatsApp thread ID.

        Returns:
            List of Note instances.
        """
        query = "SELECT * FROM notes WHERE thread_id = ? ORDER BY created_at DESC"
        conn = db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, (thread_id,))
            rows = cursor.fetchall()
            return [
                cls(
                    id=row["id"],
                    thread_id=row["thread_id"],
                    content=row["content"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
                for row in rows
            ]
        finally:
            conn.close()

    @classmethod
    def get_by_id(cls, note_id: int) -> Optional["Note"]:
        """Get a note by ID.

        Args:
            note_id: Note ID.

        Returns:
            Note instance if found, None otherwise.
        """
        query = "SELECT * FROM notes WHERE id = ?"
        conn = db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, (note_id,))
            row = cursor.fetchone()
            if row:
                return cls(
                    id=row["id"],
                    thread_id=row["thread_id"],
                    content=row["content"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
            return None
        finally:
            conn.close()


@dataclass
class Task:
    """Represents a task in the storage system."""

    id: int
    thread_id: str
    title: str
    description: Optional[str]
    due_date: Optional[datetime]
    is_completed: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls, thread_id: str, title: str, description: Optional[str] = None, due_date: Optional[datetime] = None
    ) -> "Task":
        """Create a new task.

        Args:
            thread_id: WhatsApp thread ID.
            title: Task title.
            description: Task description.
            due_date: Task due date.

        Returns:
            Created Task instance.
        """
        query = """
        INSERT INTO tasks (thread_id, title, description, due_date)
        VALUES (?, ?, ?, ?)
        """
        conn = db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, (thread_id, title, description, due_date.isoformat() if due_date else None))
            conn.commit()
            return cls(
                id=int(cursor.lastrowid) if cursor.lastrowid else 0,
                thread_id=thread_id,
                title=title,
                description=description,
                due_date=due_date,
                is_completed=False,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        finally:
            conn.close()

    @classmethod
    def get_by_thread(cls, thread_id: str) -> list["Task"]:
        """Get all tasks for a thread.

        Args:
            thread_id: WhatsApp thread ID.

        Returns:
            List of Task instances.
        """
        query = "SELECT * FROM tasks WHERE thread_id = ? ORDER BY created_at DESC"
        conn = db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, (thread_id,))
            rows = cursor.fetchall()
            return [
                cls(
                    id=row["id"],
                    thread_id=row["thread_id"],
                    title=row["title"],
                    description=row["description"],
                    due_date=datetime.fromisoformat(row["due_date"]) if row["due_date"] else None,
                    is_completed=bool(row["is_completed"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
                for row in rows
            ]
        finally:
            conn.close()

    @classmethod
    def get_by_id(cls, task_id: int) -> Optional["Task"]:
        """Get a task by ID.

        Args:
            task_id: Task ID.

        Returns:
            Task instance if found, None otherwise.
        """
        query = "SELECT * FROM tasks WHERE id = ?"
        conn = db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, (task_id,))
            row = cursor.fetchone()
            if row:
                return cls(
                    id=row["id"],
                    thread_id=row["thread_id"],
                    title=row["title"],
                    description=row["description"],
                    due_date=datetime.fromisoformat(row["due_date"]) if row["due_date"] else None,
                    is_completed=bool(row["is_completed"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
            return None
        finally:
            conn.close()

    def complete(self) -> None:
        """Mark the task as completed."""
        query = "UPDATE tasks SET is_completed = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
        conn = db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, (self.id,))
            conn.commit()
            self.is_completed = True
            self.updated_at = datetime.now()
        finally:
            conn.close()

    def update(
        self, title: Optional[str] = None, description: Optional[str] = None, due_date: Optional[datetime] = None
    ) -> None:
        """Update task details.

        Args:
            title: New task title.
            description: New task description.
            due_date: New due date.
        """
        updates = []
        params = []

        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if due_date is not None:
            updates.append("due_date = ?")
            params.append(due_date.isoformat())

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
            params.append(str(self.id))

            conn = db_manager.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                conn.commit()
            finally:
                conn.close()

            if title is not None:
                self.title = title
            if description is not None:
                self.description = description
            if due_date is not None:
                self.due_date = due_date
            self.updated_at = datetime.now()

    def _write_to_db(self) -> None:
        """Write current in-memory state to database."""
        updates = []
        params = []
        if self.title is not None:
            updates.append("title = ?")
            params.append(self.title)
        if self.description is not None:
            updates.append("description = ?")
            params.append(self.description)
        if self.due_date is not None:
            updates.append("due_date = ?")
            params.append(self.due_date.isoformat())
        if self.is_completed:
            updates.append("is_completed = 1")
        else:
            updates.append("is_completed = 0")

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
            params.append(str(self.id))

            conn = db_manager.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                conn.commit()
            finally:
                conn.close()
        self.updated_at = datetime.now()
