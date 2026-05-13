from __future__ import annotations

from dataclasses import dataclass

from utils.loader import LoadedDocument


@dataclass
class TextChunk:
    id: str
    file_name: str
    source_path: str
    content: str
    chunk_index: int


def _normalize_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join([line for line in lines if line])


def split_documents(
    docs: list[LoadedDocument],
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    for doc in docs:
        content = _normalize_text(doc.text)
        if not content:
            continue
        start = 0
        idx = 0
        while start < len(content):
            end = min(start + chunk_size, len(content))
            piece = content[start:end].strip()
            if piece:
                chunks.append(
                    TextChunk(
                        id=f"{doc.file_name}-{idx}-{start}",
                        file_name=doc.file_name,
                        source_path=doc.source_path,
                        content=piece,
                        chunk_index=idx,
                    )
                )
            if end >= len(content):
                break
            start = max(0, end - chunk_overlap)
            idx += 1
    return chunks
