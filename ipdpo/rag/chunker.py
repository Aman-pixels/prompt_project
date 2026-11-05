"""Text and code chunking utilities for RAG ingestion."""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from uuid import uuid4


@dataclass
class DocumentChunk:
    chunk_id: str
    project_id: str
    source_file: str
    chunk_index: int
    content: str
    token_count_approx: int
    metadata: dict


class DocumentChunker:
    """Splits text, markdown, and source code files into semantically coherent chunks."""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size  # approx words
        self.chunk_overlap = chunk_overlap

    def chunk_file(self, project_id: str, file_path: Path) -> List[DocumentChunk]:
        path = Path(file_path)
        if not path.is_file():
            return []

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return []

        clean_text = text.strip()
        if not clean_text:
            return []

        suffix = path.suffix.lower()
        if suffix in [".py", ".sql", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs"]:
            return self._chunk_code(project_id, str(path), clean_text)
        elif suffix in [".md", ".markdown", ".txt", ".rst"]:
            return self._chunk_markdown(project_id, str(path), clean_text)
        else:
            return self._chunk_generic(project_id, str(path), clean_text)

    def _chunk_markdown(self, project_id: str, file_path: str, text: str) -> List[DocumentChunk]:
        # Split by markdown headers (#, ##, ###)
        sections = re.split(r"(?m)(?=^#{1,4}\s+)", text)
        chunks: List[DocumentChunk] = []
        idx = 0

        for section in sections:
            section_clean = section.strip()
            if not section_clean:
                continue

            words = section_clean.split()
            if len(words) <= self.chunk_size:
                chunks.append(
                    DocumentChunk(
                        chunk_id=str(uuid4()),
                        project_id=project_id,
                        source_file=file_path,
                        chunk_index=idx,
                        content=section_clean,
                        token_count_approx=len(words),
                        metadata={"type": "markdown", "file": file_path},
                    )
                )
                idx += 1
            else:
                sub_chunks = self._sliding_window(words, self.chunk_size, self.chunk_overlap)
                for sc in sub_chunks:
                    chunks.append(
                        DocumentChunk(
                            chunk_id=str(uuid4()),
                            project_id=project_id,
                            source_file=file_path,
                            chunk_index=idx,
                            content=" ".join(sc),
                            token_count_approx=len(sc),
                            metadata={"type": "markdown_subchunk", "file": file_path},
                        )
                    )
                    idx += 1

        return chunks

    def _chunk_code(self, project_id: str, file_path: str, text: str) -> List[DocumentChunk]:
        # Split code by class or top-level function definitions if possible
        lines = text.splitlines(keepends=True)
        chunks: List[DocumentChunk] = []
        current_block: List[str] = []
        current_words = 0
        idx = 0

        for line in lines:
            line_words = len(line.split())
            is_def = bool(re.match(r"^(def |class |CREATE |ALTER |func |function )", line))

            if is_def and current_words >= (self.chunk_size // 2):
                block_content = "".join(current_block).strip()
                if block_content:
                    chunks.append(
                        DocumentChunk(
                            chunk_id=str(uuid4()),
                            project_id=project_id,
                            source_file=file_path,
                            chunk_index=idx,
                            content=block_content,
                            token_count_approx=current_words,
                            metadata={"type": "code", "file": file_path},
                        )
                    )
                    idx += 1
                current_block = [line]
                current_words = line_words
            else:
                current_block.append(line)
                current_words += line_words

            if current_words >= self.chunk_size:
                block_content = "".join(current_block).strip()
                if block_content:
                    chunks.append(
                        DocumentChunk(
                            chunk_id=str(uuid4()),
                            project_id=project_id,
                            source_file=file_path,
                            chunk_index=idx,
                            content=block_content,
                            token_count_approx=current_words,
                            metadata={"type": "code", "file": file_path},
                        )
                    )
                    idx += 1
                current_block = []
                current_words = 0

        if current_block:
            block_content = "".join(current_block).strip()
            if block_content:
                chunks.append(
                    DocumentChunk(
                        chunk_id=str(uuid4()),
                        project_id=project_id,
                        source_file=file_path,
                        chunk_index=idx,
                        content=block_content,
                        token_count_approx=current_words,
                        metadata={"type": "code", "file": file_path},
                    )
                )

        return chunks

    def _chunk_generic(self, project_id: str, file_path: str, text: str) -> List[DocumentChunk]:
        words = text.split()
        sub_chunks = self._sliding_window(words, self.chunk_size, self.chunk_overlap)
        chunks = []
        for idx, sc in enumerate(sub_chunks):
            chunks.append(
                DocumentChunk(
                    chunk_id=str(uuid4()),
                    project_id=project_id,
                    source_file=file_path,
                    chunk_index=idx,
                    content=" ".join(sc),
                    token_count_approx=len(sc),
                    metadata={"type": "generic", "file": file_path},
                )
            )
        return chunks

    def _sliding_window(self, words: List[str], size: int, overlap: int) -> List[List[str]]:
        if not words:
            return []
        if len(words) <= size:
            return [words]

        step = max(1, size - overlap)
        chunks = []
        for i in range(0, len(words), step):
            window = words[i : i + size]
            if window:
                chunks.append(window)
            if i + size >= len(words):
                break
        return chunks
