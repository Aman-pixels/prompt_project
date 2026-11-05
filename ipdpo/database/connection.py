"""Database connection and initialization module."""
import sqlite3
from pathlib import Path
from typing import Optional
from ipdpo.config import DEFAULT_DB_PATH

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


class Database:
    """Encapsulates SQLite connection management and initialization."""

    def __init__(self, db_path: Optional[Path] = None):
        from ipdpo import config
        self.db_path = Path(db_path) if db_path else config.DEFAULT_DB_PATH

    def get_connection(self) -> sqlite3.Connection:
        """Create and configure a SQLite connection with foreign keys and row factory."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def initialize_schema(self) -> None:
        """Execute schema.sql to ensure all tables and indexes exist."""
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            ddl = f.read()

        with self.get_connection() as conn:
            conn.executescript(ddl)
            conn.commit()
