"""Unit and integration tests for IPDPO RAG subsystem."""
import pytest
from pathlib import Path
from ipdpo.database.connection import Database
from ipdpo.rag.chunker import DocumentChunker
from ipdpo.rag.fts_store import FTS5Store
from ipdpo.rag.service import RAGService
from ipdpo.rag.vector_store import VectorStore


@pytest.fixture
def rag_test_env(tmp_path):
    db_file = tmp_path / "test_rag.db"
    db = Database(db_file)
    db.initialize_schema()

    chroma_dir = tmp_path / "test_chroma"
    vector_store = VectorStore(persist_dir=chroma_dir)
    chunker = DocumentChunker(chunk_size=100, chunk_overlap=10)
    service = RAGService(db=db, vector_store=vector_store, chunker=chunker)

    return {
        "db": db,
        "vector_store": vector_store,
        "chunker": chunker,
        "service": service,
        "tmp_path": tmp_path,
    }


def test_document_chunker_markdown_and_code(rag_test_env):
    chunker = rag_test_env["chunker"]
    tmp_path = rag_test_env["tmp_path"]

    # Test Markdown chunking
    md_file = tmp_path / "doc.md"
    md_file.write_text(
        "# Heading 1\nSome detailed introduction.\n\n## Heading 2\nAuthentication policies and tokens.",
        encoding="utf-8",
    )
    chunks = chunker.chunk_file("p1", md_file)
    assert len(chunks) >= 2
    assert any("Authentication policies" in c.content for c in chunks)

    # Test Code chunking
    py_file = tmp_path / "auth.py"
    py_file.write_text(
        "class TokenManager:\n    def generate_jwt(self, user_id):\n        return 'jwt_token'\n\ndef verify_token(t):\n    return True\n",
        encoding="utf-8",
    )
    code_chunks = chunker.chunk_file("p1", py_file)
    assert len(code_chunks) >= 1
    assert "class TokenManager" in code_chunks[0].content


def test_fts5_indexing_and_search(rag_test_env):
    service = rag_test_env["service"]
    tmp_path = rag_test_env["tmp_path"]

    source_file = tmp_path / "config.py"
    source_file.write_text("DATABASE_POOL_SIZE = 25\nMAX_CONCURRENCY = 100\n", encoding="utf-8")

    indexed_count = service.index_path("test_proj_1", source_file)
    assert indexed_count >= 1

    # Search via FTS5
    hits = service.fts_store.search("test_proj_1", "DATABASE_POOL_SIZE", limit=3)
    assert len(hits) == 1
    assert "DATABASE_POOL_SIZE" in hits[0]["content"]

    # Test Project Isolation
    other_proj_hits = service.fts_store.search("test_proj_2", "DATABASE_POOL_SIZE", limit=3)
    assert len(other_proj_hits) == 0


def test_hybrid_search_deduplication(rag_test_env):
    service = rag_test_env["service"]
    tmp_path = rag_test_env["tmp_path"]

    spec_file = tmp_path / "spec.txt"
    spec_file.write_text("All passwords must be hashed using bcrypt with salt rounds 12.", encoding="utf-8")

    service.index_path("proj_sec", spec_file)

    results = service.hybrid_search("proj_sec", "bcrypt passwords salt", limit=2)
    assert len(results) >= 1
    assert "bcrypt" in results[0]["content"]


def test_rag_clear_index(rag_test_env):
    service = rag_test_env["service"]
    tmp_path = rag_test_env["tmp_path"]

    doc_file = tmp_path / "notes.md"
    doc_file.write_text("Secret architecture plan.", encoding="utf-8")

    service.index_path("proj_clear", doc_file)
    assert len(service.fts_store.search("proj_clear", "architecture")) > 0

    service.clear_project_index("proj_clear")
    assert len(service.fts_store.search("proj_clear", "architecture")) == 0
