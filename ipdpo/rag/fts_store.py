"""SQLite FTS5 full-text search index for fast, 100% offline BM25 retrieval."""
import sqlite3
from typing import List, Optional
from ipdpo.database.connection import Database
from ipdpo.rag.chunker import DocumentChunk


class FTS5Store:
    """Manages SQLite FTS5 virtual table for local BM25 ranking and search."""

    def __init__(self, db: Database):
        self.db = db
        self._init_fts()

    def _init_fts(self) -> None:
        with self.db.get_connection() as conn:
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS rag_fts USING fts5(
                    chunk_id UNINDEXED,
                    project_id UNINDEXED,
                    source_file UNINDEXED,
                    content,
                    tokenize='porter unicode61'
                );
                """
            )
            conn.commit()

    def add_chunks(self, chunks: List[DocumentChunk]) -> None:
        if not chunks:
            return
        with self.db.get_connection() as conn:
            for c in chunks:
                conn.execute(
                    """
                    INSERT INTO rag_fts (chunk_id, project_id, source_file, content)
                    VALUES (?, ?, ?, ?)
                    """,
                    (c.chunk_id, c.project_id, c.source_file, c.content),
                )
            conn.commit()

    def delete_by_project(self, project_id: str) -> None:
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM rag_fts WHERE project_id = ?", (project_id,))
            conn.commit()

    def search(self, project_id: str, query: str, limit: int = 5) -> List[dict]:
        """
        Executes a BM25 ranked search using SQLite FTS5 MATCH.
        """
        # Strip special SQLite FTS syntax chars except alphanumeric and underscores
        clean_tokens = [t.strip("\"'*") for t in query.split() if t.strip("\"'*")]
        if not clean_tokens:
            return []

        # Enclose each token in quotes for literal prefix matching
        match_query = " OR ".join([f'"{t}"' for t in clean_tokens])

        with self.db.get_connection() as conn:
            try:
                rows = conn.execute(
                    """
                    SELECT chunk_id, project_id, source_file, content, rank
                    FROM rag_fts
                    WHERE rag_fts MATCH ? AND project_id = ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (match_query, project_id, limit),
                ).fetchall()

                return [
                    {
                        "chunk_id": r["chunk_id"],
                        "project_id": r["project_id"],
                        "source_file": r["source_file"],
                        "content": r["content"],
                        "score": -float(r["rank"]),  # FTS5 rank is negative (lower = better)
                        "engine": "sqlite_fts5",
                    }
                    for r in rows
                ]
            except Exception as e:
                return []
