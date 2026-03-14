"""Repository for managing notes."""

from typing import List

from ..database import db_manager
from ..models import Note


class NoteRepository:
    """Repository for note operations."""

    def create(self, thread_id: str, content: str) -> Note:
        """Create a new note.

        Args:
            thread_id: WhatsApp thread ID.
            content: Note content.

        Returns:
            Created Note instance.
        """
        return Note.create(thread_id, content)

    def get_by_thread(self, thread_id: str) -> List[Note]:
        """Get all notes for a thread.

        Args:
            thread_id: WhatsApp thread ID.

        Returns:
            List of Note instances.
        """
        return Note.get_by_thread(thread_id)

    def get_by_id(self, note_id: int) -> Note | None:
        """Get a note by ID.

        Args:
            note_id: Note ID.

        Returns:
            Note instance if found, None otherwise.
        """
        return Note.get_by_id(note_id)

    def delete(self, note_id: int) -> bool:
        """Delete a note.

        Args:
            note_id: Note ID.

        Returns:
            True if note was deleted, False if not found.
        """
        conn = db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def update(self, note_id: int, content: str) -> Note | None:
        """Update a note's content.

        Args:
            note_id: Note ID.
            content: New note content.

        Returns:
            Updated Note instance if found, None otherwise.
        """
        conn = db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE notes
                SET content = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (content, note_id),
            )
            conn.commit()
            if cursor.rowcount > 0:
                return Note.get_by_id(note_id)
            return None
        finally:
            conn.close()
