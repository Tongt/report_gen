from __future__ import annotations

from pathlib import Path

from config import KB_DIR
from utils.loader import list_knowledge_base_files, load_documents
from utils.splitter import split_documents
from utils.vector_store import ChromaKnowledgeBase


def _list_kb_files() -> list[Path]:
    return list_knowledge_base_files(base_dir=KB_DIR)


def list_saved_files() -> list[str]:
    return [path.name for path in _list_kb_files()]


def index_new_files(kb: ChromaKnowledgeBase) -> dict[str, int]:
    indexed_paths = set(kb.list_indexed_source_paths())
    candidates = [path for path in _list_kb_files() if str(path) not in indexed_paths]
    if not candidates:
        return {"new_files": 0, "parsed_files": 0, "chunks": 0}

    docs = load_documents(candidates)
    chunks = split_documents(docs)
    kb.upsert_chunks(chunks)
    return {"new_files": len(candidates), "parsed_files": len(docs), "chunks": len(chunks)}


def rebuild_all(kb: ChromaKnowledgeBase) -> dict[str, int]:
    kb.clear()
    candidates = _list_kb_files()
    if not candidates:
        return {"files": 0, "parsed_files": 0, "chunks": 0}

    docs = load_documents(candidates)
    chunks = split_documents(docs)
    kb.upsert_chunks(chunks)
    return {"files": len(candidates), "parsed_files": len(docs), "chunks": len(chunks)}


def delete_file(kb: ChromaKnowledgeBase, filename: str) -> bool:
    candidates = [path for path in _list_kb_files() if path.name == filename]
    if not candidates:
        return False
    path = candidates[0]
    path.unlink()
    kb.delete_by_source_path(str(path))
    return True
