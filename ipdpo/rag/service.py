"""RAG orchestrator service: indexing, hybrid search, and context enrichment."""
import os
from pathlib import Path
from typing import Dict, List, Optional, Set
from ipdpo.database.connection import Database
from ipdpo.rag.chunker import DocumentChunk, DocumentChunker
from ipdpo.rag.fts_store import FTS5Store
from ipdpo.rag.vector_store import VectorStore

SUPPORTED_EXTENSIONS = {
    ".py", ".md", ".txt", ".sql", ".json", ".yaml", ".yml",
    ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".go", ".rs"
}

IGNORE_DIRS = {
    ".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules",
    ".chroma_db", "exports", "build", "dist", ".idea", ".vscode"
}


class RAGService:
    """
    Coordinates file discovery, chunking, dual indexing (SQLite FTS5 + ChromaDB),
    and hybrid retrieval.
    """

    def __init__(
        self,
        db: Database,
        vector_store: Optional[VectorStore] = None,
        chunker: Optional[DocumentChunker] = None,
    ):
        self.db = db
        self.fts_store = FTS5Store(db)
        self.vector_store = vector_store or VectorStore()
        self.chunker = chunker or DocumentChunker()

    def index_path(self, project_id: str, target_path: Path) -> int:
        """
        Indexes a file or recursively indexes a directory.
        Returns the total number of document chunks indexed.
        """
        path = Path(target_path)
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        files_to_index: List[Path] = []
        if path.is_file():
            if path.suffix.lower() in SUPPORTED_EXTENSIONS:
                files_to_index.append(path)
        else:
            for root, dirs, files in os.walk(path):
                # Filter out ignored dirs in-place
                dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
                for f in files:
                    file_p = Path(root) / f
                    if file_p.suffix.lower() in SUPPORTED_EXTENSIONS:
                        files_to_index.append(file_p)

        all_chunks: List[DocumentChunk] = []
        for file_p in files_to_index:
            chunks = self.chunker.chunk_file(project_id, file_p)
            all_chunks.extend(chunks)

        if all_chunks:
            # 1. Index into local SQLite FTS5 (BM25)
            self.fts_store.add_chunks(all_chunks)

            # 2. Index into ChromaDB Vector Store
            try:
                self.vector_store.add_chunks(all_chunks)
            except Exception:
                # If vector store fails, FTS5 still guarantees search functionality
                pass

        return len(all_chunks)

    def hybrid_search(self, project_id: str, query: str, limit: int = 4) -> List[dict]:
        """
        Executes dual search (FTS5 BM25 + Vector), deduplicates by chunk_id/content,
        and returns top-K ranked chunks.
        """
        fts_results = self.fts_store.search(project_id, query, limit=limit)
        try:
            vector_results = self.vector_store.search(project_id, query, limit=limit)
        except Exception:
            vector_results = []

        combined: List[dict] = []
        seen_contents: Set[str] = set()

        # Interleave vector results and FTS results (hybrid reciprocal ranking)
        max_len = max(len(vector_results), len(fts_results))
        for i in range(max_len):
            if i < len(vector_results):
                vr = vector_results[i]
                c_hash = vr["content"][:100]
                if c_hash not in seen_contents:
                    seen_contents.add(c_hash)
                    combined.append(vr)

            if i < len(fts_results):
                fr = fts_results[i]
                c_hash = fr["content"][:100]
                if c_hash not in seen_contents:
                    seen_contents.add(c_hash)
                    combined.append(fr)

            if len(combined) >= limit:
                break

        return combined[:limit]

    def clear_project_index(self, project_id: str) -> None:
        self.fts_store.delete_by_project(project_id)
        try:
            self.vector_store.delete_by_project(project_id)
        except Exception:
            pass
