"""Thin storage wrapper for agntrick-whatsapp.

Delegates to agntrick.storage for all persistence operations.
Provides WhatsApp-specific helpers on top of the base repositories.
"""

from pathlib import Path

from agntrick.storage import (  # type: ignore[import-untyped]
    Database,
    Note,
    NoteRepository,
    ScheduledTask,
    TaskRepository,
    TaskStatus,
    TaskType,
    calculate_next_run,
    parse_natural_time,
)

from agntrick_whatsapp.constants import DATA_DIR

__all__ = [
    "Database",
    "Note",
    "ScheduledTask",
    "NoteRepository",
    "TaskRepository",
    "TaskStatus",
    "TaskType",
    "WhatsAppNoteRepository",
    "calculate_next_run",
    "get_default_db",
    "parse_natural_time",
]


class WhatsAppNoteRepository(NoteRepository):
    """NoteRepository extended with WhatsApp context filtering."""

    def list_by_context(self, context_id: str) -> list[Note]:
        """List all notes for a given context (e.g., sender_id).

        Args:
            context_id: The context ID to filter by (e.g., WhatsApp sender_id).

        Returns:
            List of notes for the given context, ordered by creation time.
        """
        conn = self._db.connection
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM notes WHERE context_id = ? ORDER BY created_at ASC",
            (context_id,),
        )
        return [self._row_to_note(dict(row)) for row in cursor.fetchall()]


def get_default_db(db_path: Path | None = None) -> Database:
    """Return a Database instance at the default WhatsApp data location.

    Args:
        db_path: Optional override path. Defaults to DATA_DIR / "whatsapp.db".

    Returns:
        Initialised Database instance.
    """
    resolved_path = db_path or DATA_DIR / "whatsapp.db"
    return Database(resolved_path)
