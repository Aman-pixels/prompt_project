"""ChromaDB vector store adapter for dense semantic retrieval."""
from pathlib import Path
from typing import List, Optional
import chromadb
from chromadb.config import Settings
from ipdpo.config import PROJECT_ROOT
from ipdpo.rag.chunker import DocumentChunk

DEFAULT_CHROMA_DIR = PROJECT_ROOT / ".chroma_db"


class VectorStore:
    """Manages dense semantic embeddings and vector queries using local ChromaDB."""

    def __init__(self, persist_dir: Optional[Path] = None):
        self.persist_dir = persist_dir if persist_dir else DEFAULT_CHROMA_DIR
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(name="ipdpo_rag")

    def add_chunks(self, chunks: List[DocumentChunk]) -> None:
        if not chunks:
            return

        ids = [c.chunk_id for c in chunks]
        documents = [c.content for c in chunks]
        metadatas = [
            {
                "project_id": c.project_id,
                "source_file": c.source_file,
                "chunk_index": c.chunk_index,
            }
            for c in chunks
        ]

        # Chroma's default sentence transformer embedding handles text locally
        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

    def delete_by_project(self, project_id: str) -> None:
        try:
            self.collection.delete(where={"project_id": project_id})
        except Exception:
            pass

    def search(self, project_id: str, query: str, limit: int = 5) -> List[dict]:
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=limit,
                where={"project_id": project_id},
            )

            if not results or not results["documents"] or not results["documents"][0]:
                return []

            docs = results["documents"][0]
            metas = results["metadatas"][0]
            ids = results["ids"][0]
            distances = results["distances"][0] if "distances" in results and results["distances"] else [0.0] * len(docs)

            formatted = []
            for doc, meta, cid, dist in zip(docs, metas, ids, distances):
                formatted.append(
                    {
                        "chunk_id": cid,
                        "project_id": meta.get("project_id", project_id),
                        "source_file": meta.get("source_file", "unknown"),
                        "content": doc,
                        "score": round(1.0 - float(dist), 4) if dist is not None else 1.0,
                        "engine": "chroma_vector",
                    }
                )
            return formatted
        except Exception:
            return []
