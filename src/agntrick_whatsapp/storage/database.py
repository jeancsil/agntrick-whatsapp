"""Database setup and configuration for WhatsApp storage."""

import sqlite3
from pathlib import Path
from typing import cast

from agntrick.storage.database import Database  # type: ignore[import-untyped]

from ..constants import DATA_DIR


class DatabaseManager:
    """Manages SQLite database connections and setup for WhatsApp integration."""

    def __init__(self, db_path: Path | None = None):
        """Initialize database manager.

        Args:
            db_path: Path to the database file. If None, uses default location in DATA_DIR.
        """
        self.db_path = db_path or DATA_DIR / "whatsapp.db"
        self._db = Database(self.db_path)

    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        return cast(sqlite3.Connection, self._db.connection)  # type: ignore[return-value]

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a SQL query.

        Args:
            query: SQL query string.
            params: Query parameters.

        Returns:
            Database cursor.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor

    def close(self) -> None:
        """Close database connection and clean up resources."""
        self._db.close()

    def init_database(self) -> None:
        """Initialize database and create all necessary tables."""
        self.create_tables()

    def create_tables(self) -> None:
        """Create all necessary database tables."""
        queries = [
            """CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                due_date TIMESTAMP,
                is_completed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                task_id INTEGER,
                cron_expression TEXT NOT NULL,
                next_run TIMESTAMP NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks (id)
            )""",
        ]

        for query in queries:
            self.execute(query)


# Global database instance
db_manager = DatabaseManager()
